#!/usr/bin/env python3
"""Read-only job runner called by n8n over the internal Docker network. stdlib only.

Jobs are explicit functions; no arbitrary command execution. Auth: Bearer token (JOBS_TOKEN).
Logs are one JSON object per line on stdout; secrets are never logged.
"""
import hmac
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("JOBS_TOKEN", "")
ALLOWED = {r.strip() for r in os.environ.get("ALLOWED_REPOS", "").split(",") if r.strip()}
REPORT_DIR = os.environ.get("REPORT_DIR", "/data/reports")
REPO_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}$")  # no leading dot (blocks ".." segments)
MAX_BODY = 4096
HTTP_TIMEOUT = 10
MAX_TRIES = 3


def log(level, msg, **kw):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level, "msg": msg, **kw}), flush=True)


class JobError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def fetch_json(url):
    """GET with timeout and bounded exponential-backoff retry on transient errors only."""
    last = None
    for attempt in range(1, MAX_TRIES + 1):
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "home-ai-lab-jobs/1"})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                raise JobError(429, "GitHub rate limit or access denied (no retry)")
            if e.code == 404:
                raise JobError(404, "repository not found or not public")
            last = f"HTTP {e.code}"
            if e.code < 500:
                raise JobError(502, last)
        except (urllib.error.URLError, TimeoutError) as e:
            last = type(e).__name__
        log("warn", "transient upstream error", attempt=attempt, error=last)
        if attempt < MAX_TRIES:
            time.sleep(2 ** attempt)
    raise JobError(502, f"upstream failed after {MAX_TRIES} tries: {last}")


def github_repo_metadata(params):
    repo = params.get("repo", "")
    if not isinstance(repo, str) or not REPO_RE.match(repo):
        raise JobError(400, "invalid repo format (expected owner/name)")
    if repo not in ALLOWED:
        raise JobError(403, "repo not in ALLOWED_REPOS")
    d = fetch_json(f"https://api.github.com/repos/{repo}")  # unauthenticated, public data only
    data = {
        "full_name": d.get("full_name"), "description": d.get("description"),
        "html_url": d.get("html_url"), "default_branch": d.get("default_branch"),
        "stars": d.get("stargazers_count"), "forks": d.get("forks_count"),
        "open_issues": d.get("open_issues_count"), "archived": d.get("archived"),
        "license": (d.get("license") or {}).get("spdx_id"), "pushed_at": d.get("pushed_at"),
    }
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, repo.replace("/", "__") + ".md")
    md = f"# {data['full_name']}\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in data.items() if k != "full_name") + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return {"data": data, "report": path}


_SNAPSHOT_LOCK = threading.Lock()


def github_dev_snapshot(params):
    """Read-only multi-repository GitHub snapshot + daily Markdown report (see github_snapshot.py)."""
    import github_snapshot as gs
    cfg = gs.Config()
    owner = params.get("owner") or (sorted(cfg.owners)[0] if cfg.owners else "")
    if not isinstance(owner, str) or not owner or owner not in cfg.owners:
        raise JobError(403, "owner not in GITHUB_OWNERS")
    if not _SNAPSHOT_LOCK.acquire(blocking=False):
        raise JobError(409, "a snapshot is already running")
    try:
        return gs.run(owner, cfg)
    except gs.ApiError as e:
        log("error", "snapshot failed", error=str(e)[:200])
        raise JobError(502, f"snapshot failed: {str(e)[:150]}")
    finally:
        _SNAPSHOT_LOCK.release()


JOBS = {"github-repo-metadata": github_repo_metadata, "github-dev-snapshot": github_dev_snapshot}


class Handler(BaseHTTPRequestHandler):
    timeout = 15
    server_version = "jobs/1"

    def log_message(self, *a):  # replaced by structured request log in do_POST
        pass

    def _send(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        t0 = time.time()
        status, job = 500, self.path
        try:
            auth = self.headers.get("Authorization", "")
            if not TOKEN or not hmac.compare_digest(auth, f"Bearer {TOKEN}"):
                status = 401
                return self._send(401, {"ok": False, "error": "unauthorized"})
            fn = JOBS.get(self.path[len("/jobs/"):]) if self.path.startswith("/jobs/") else None
            if fn is None:
                status = 404
                return self._send(404, {"ok": False, "error": "unknown job"})
            log("info", "request started", job=job)
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n > MAX_BODY:
                    raise JobError(413, "body too large")
                params = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(params, dict):
                    raise JobError(400, "body must be a JSON object")
                result = fn(params)
                status = 200
                self._send(200, {"ok": True, **result})
            except JobError as e:
                status = e.status
                self._send(e.status, {"ok": False, "error": str(e)})
            except json.JSONDecodeError:
                status = 400
                self._send(400, {"ok": False, "error": "invalid JSON"})
        except Exception as e:  # never leak internals to the caller
            log("error", "unhandled", error=type(e).__name__)
            try:
                self._send(500, {"ok": False, "error": "internal error"})
            except Exception:
                pass
        finally:
            log("info", "request", job=job, status=status, ms=int((time.time() - t0) * 1000))


if __name__ == "__main__":
    if not TOKEN:
        log("error", "JOBS_TOKEN not set")
        sys.exit(1)
    log("info", "starting", allowed_repos=len(ALLOWED))
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
