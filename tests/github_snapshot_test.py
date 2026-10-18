#!/usr/bin/env python3
"""Local tests for stacks/n8n/python-jobs/github_snapshot.py using a fake GitHub API and fake Uptime Kuma.
No network access to the real GitHub. Run: python tests/github_snapshot_test.py"""
import datetime as dt
import json
import os
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stacks", "n8n", "python-jobs"))
import github_snapshot as gs  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
TOKEN = "github_pat_TESTTOKEN0123456789abcdef"
KUMA = "KUMAPUSHTOKEN0123"
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        fails.append(name)


def iso(days_ago, base=NOW):
    return (base - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class World:
    """Mutable fake GitHub state shared with the HTTP handler."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.requests = []          # (path, has_auth, auth_value)
        self.inject = {}            # path prefix -> list of (status, headers) consumed in order
        self.remaining = 4000
        self.repos = [self.repo("alpha", 1, issues=2), self.repo("beta", 3, issues=1), self.repo("gamma", 200), self.repo("delta", 5, archived=True),
                      self.repo("fork1", 1, fork=True), self.repo("priv", 2, private=True)]
        self.repos += [self.repo(f"filler{i:03d}", 100 + i, fork=True) for i in range(130)]   # forces pagination
        self.issues = {"alpha#1": ("issue", "alpha", 1, "Crash on start", 1, 1), "alpha#2": ("issue", "alpha", 2, "Old idea", 90, 60),
                       "fork1#1": ("issue", "fork1", 1, "Upstream issue", 2, 2), "beta#5": ("pr", "beta", 5, "Add feature | pipe\n# injected", 10, 10)}
        self.runs = {"alpha": [self.run(1, "success", 1)], "beta": [self.run(900, "failure", 1), self.run(899, "failure", 4), self.run(898, "success", 6)]}
        self.dependabot = {"alpha": [{"security_vulnerability": {"severity": "critical"}}, {"security_vulnerability": {"severity": "high"}}, {"security_vulnerability": {"severity": "low"}}]}

    @staticmethod
    def repo(name, pushed_days, issues=0, fork=False, archived=False, private=False):
        return {"name": name, "fork": fork, "archived": archived, "private": private, "pushed_at": iso(pushed_days), "default_branch": "main",
                "open_issues_count": issues, "html_url": f"https://github.com/o/{name}", "owner": {"login": "moruku36"}}

    @staticmethod
    def run(i, concl, days):
        return {"id": i, "name": "CI", "status": "completed", "conclusion": concl, "created_at": iso(days), "html_url": f"https://github.com/o/r/actions/runs/{i}"}


W = World()


class GitHubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, headers=None):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        hdrs = {"X-RateLimit-Remaining": str(W.remaining)}
        hdrs.update(headers or {})
        for k, v in hdrs.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        auth = self.headers.get("Authorization")
        W.requests.append((u.path, auth is not None, auth))
        W.remaining -= 1
        for prefix, seq in W.inject.items():
            if u.path.startswith(prefix) and seq:
                code, hdrs = seq.pop(0)
                return self._send(code, {"message": "injected"}, hdrs)
        p = u.path.strip("/").split("/")
        page, per = int(q.get("page", ["1"])[0]), int(q.get("per_page", ["30"])[0])
        sl = lambda items: items[(page - 1) * per: page * per]  # noqa: E731
        if u.path in ("/users/moruku36/repos", "/user/repos"):
            if u.path == "/user/repos" and not auth:
                return self._send(401, {"message": "Requires authentication"})
            items = [r for r in W.repos if (u.path == "/user/repos" or not r["private"])]
            return self._send(200, sl(items))
        if u.path == "/search/issues":
            kind = "pr" if "is:pr" in q["q"][0] else "issue"
            items = [{"repository_url": f"https://api.github.com/repos/moruku36/{v[1]}", "number": v[2], "title": v[3], "created_at": iso(v[4]), "updated_at": iso(v[5]),
                      "html_url": f"https://github.com/moruku36/{v[1]}/issues/{v[2]}", "user": {"login": "u"}, "draft": False}
                     for v in W.issues.values() if v[0] == kind and (auth or not W.repo_private(v[1]))]
            return self._send(200, {"total_count": len(items), "items": sl(items)})
        if len(p) == 5 and p[0] == "repos" and p[3] == "actions" and p[4] == "runs":
            return self._send(200, {"workflow_runs": W.runs.get(p[2], [])})
        if len(p) == 4 and p[0] == "repos" and p[3] == "commits":
            return self._send(200, [{"sha": "abcdef1234567", "commit": {"message": f"update {p[2]}\n\nbody", "author": {"date": iso(1)}}}])
        if len(p) == 5 and p[0] == "repos" and p[3] == "dependabot":
            if not auth:
                return self._send(403, {"message": "Resource not accessible"})
            if p[2] == "beta":
                return self._send(403, {"message": "Resource not accessible by personal access token"})
            return self._send(200, W.dependabot.get(p[2], []))
        return self._send(404, {"message": "Not Found"})


World.repo_private = lambda self, name: any(r["name"] == name and r["private"] for r in self.repos)


class KumaHandler(BaseHTTPRequestHandler):
    pushes = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        KumaHandler.pushes.append((u.path, q.get("status", [""])[0], q.get("msg", [""])[0]))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


def serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def mkcfg(gh_url, kuma_url, token="", now=NOW, **kw):
    d = tempfile.mkdtemp()
    base = dict(api=gh_url, token=token, owners={"moruku36"}, state_dir=os.path.join(d, "state"), report_dir=os.path.join(d, "reports"), retry_base=0,
                kuma_base=kuma_url, kuma_token=KUMA, max_calls=1500 if token else 45, now=lambda: now)
    base.update(kw)
    return gs.Config(**base)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main():
    gh, gh_url = serve(GitHubHandler)
    km, km_url = serve(KumaHandler)
    try:
        # ---- 1. unauthenticated run
        W.reset()
        KumaHandler.pushes.clear()
        cfg = mkcfg(gh_url, km_url)
        r = gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        check("run returns report names and counts", r["report"] == "github-daily-2026-10-15.md" and r["counts"]["repos"] == 135, r["counts"])
        check("pagination: 135 repos read across 2 pages", sum(1 for p, _, _ in W.requests if p == "/users/moruku36/repos") == 2)
        check("latest copy equals dated report", read(os.path.join(cfg.report_dir, "github-daily-latest.md")) == rep)
        check("report has all 7 sections + summary", all(s in rep for s in ["## Summary", "## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7."]))
        check("forks are excluded from analysis (fork1 absent)", "fork1" not in rep and "filler" not in rep)
        check("private repo absent when unauthenticated", "| priv |" not in rep)
        check("failing Actions on default branch -> critical alert", r["counts"]["critical"] == 1 and "beta" in r["critical_alerts"][0], r["critical_alerts"])
        check("stale issue (60d) counted as warn", r["counts"]["warn"] >= 1 and "alpha#2" in rep)
        check("old repo (200d) listed as stale project", "gamma" in rep.split("## 6.")[1])
        check("archived repo not listed as stale", "delta" not in rep.split("## 6.")[1])
        check("unauthenticated: Dependabot reported as not collected", "not collected" in rep and not any("dependabot" in p for p, _, _ in W.requests))
        check("no Authorization header sent without token", all(not a for _, a, _ in W.requests))
        check("API call count within unauth budget", r["counts"]["api_calls"] <= 45 and r["counts"]["api_calls"] == len(W.requests), (r["counts"]["api_calls"], len(W.requests)))
        check("Kuma push: down with critical summary", KumaHandler.pushes and KumaHandler.pushes[-1][1] == "down" and "beta" in KumaHandler.pushes[-1][2], KumaHandler.pushes)
        check("Kuma push path uses token only in URL, report never contains it", KUMA not in rep)
        check("markdown injection neutralised (pipe escaped, no injected heading)", "\\|" in rep and "\n# injected" not in rep)
        check("first run says no previous snapshot", "First snapshot" in rep)

        # ---- 2. second run (next day) with changes -> diff
        W.issues["alpha#3"] = ("issue", "alpha", 3, "Brand new bug", 0, 0)
        del W.issues["beta#5"]
        W.runs["beta"].insert(0, W.run(901, "failure", 0))
        W.repos[0]["pushed_at"] = iso(0)
        cfg.now = lambda: NOW + dt.timedelta(days=1)
        gs.run("moruku36", cfg)
        rep2 = read(os.path.join(cfg.report_dir, "github-daily-2026-10-16.md"))
        d = rep2.split("## 7.")[1]
        # labels were made precise in TASK-122 (what the data can and cannot say); the facts they carry are unchanged
        check("diff: new issue", "Newly seen open issues: alpha#3" in d, d)
        check("diff: PR no longer open (closed OR merged is not distinguished)", "PRs no longer open (closed OR merged; not distinguished): beta#5" in d)
        check("diff: new Actions failure (run 901)", "New Actions failures" in d and "901" in d)
        check("diff: repo whose last-push time changed (names, not a push count)", "(repository names only; NOT a count of pushes or commits): alpha" in d)
        check("snapshots kept per day + latest", {"2026-10-15.json", "2026-10-16.json", "latest.json"} <= set(os.listdir(os.path.join(cfg.state_dir, "snapshots"))))

        # ---- 3. authenticated run
        W.reset()
        KumaHandler.pushes.clear()
        cfg = mkcfg(gh_url, km_url, token=TOKEN)
        r = gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        check("auth: Bearer token sent to API", any(a == f"Bearer {TOKEN}" for _, _, a in W.requests))
        check("auth: private repo included", "| priv |" in rep)
        check("auth: Dependabot critical/high -> critical alert", "Dependabot: 1 critical / 1 high" in rep, rep[:400])
        check("auth: Dependabot 403 on one repo is tolerated and shown as unavailable", "unavailable for 1" in rep)
        allfiles = "".join(read(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.dirname(cfg.report_dir)) for f in fs)
        check("secrets: token and Kuma token never written to reports/snapshots/state", TOKEN not in allfiles and KUMA not in allfiles)
        check("auth: result never contains tokens", TOKEN not in json.dumps(r) and KUMA not in json.dumps(r))

        # ---- 4. call budget
        W.reset()
        cfg = mkcfg(gh_url, km_url, max_calls=5)
        r = gs.run("moruku36", cfg)
        check("budget exhausted -> partial report, no crash", r["partial"] and any("budget" in n for n in r["notes"]) and r["counts"]["api_calls"] <= 5, r)
        check("partial report states data completeness", "Data completeness" in read(os.path.join(cfg.report_dir, "github-daily-latest.md")))

        # ---- 5. transient 500s are retried
        W.reset()
        W.inject["/search/issues"] = [(500, {}), (502, {})]
        cfg = mkcfg(gh_url, km_url)
        r = gs.run("moruku36", cfg)
        check("transient 5xx retried and recovered", r["counts"]["issues"] >= 1 and sum(1 for p, _, _ in W.requests if p == "/search/issues") == 4, [p for p, _, _ in W.requests if "search" in p])

        # ---- 6. rate limit (403 + remaining 0)
        W.reset()
        W.inject["/search/issues"] = [(403, {"X-RateLimit-Remaining": "0"})] * 2
        cfg = mkcfg(gh_url, km_url)
        r = gs.run("moruku36", cfg)
        check("rate limit on search -> partial, run still completes", r["partial"] and r["counts"]["issues"] == 0 and r["counts"]["repos"] == 135)

        W.reset()
        W.inject["/search/issues"] = [(422, {})] * 2
        r = gs.run("moruku36", mkcfg(gh_url, km_url))
        check("unexpected search error (422) -> partial, report still produced", r["partial"] and r["counts"]["repos"] == 135 and any("search API error" in n for n in r["notes"]))

        # ---- 7. fatal: repo list unavailable
        W.reset()
        KumaHandler.pushes.clear()
        W.inject["/users/moruku36/repos"] = [(500, {})] * 5
        cfg = mkcfg(gh_url, km_url)
        try:
            gs.run("moruku36", cfg)
            ok = False
        except gs.ApiError:
            ok = True
        check("repo list failing -> ApiError, no report written", ok and not os.path.exists(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md")))
        check("collector failure pushes down to Kuma", KumaHandler.pushes and KumaHandler.pushes[-1][1] == "down" and "collector error" in KumaHandler.pushes[-1][2])
        W.reset()
        cfg = mkcfg(gh_url, km_url, token="")
        W.inject["/users/moruku36/repos"] = [(401, {})]
        try:
            gs.run("moruku36", cfg)
            ok = False
        except gs.ApiError as e:
            ok = "401" in str(e)
        check("401 reported clearly", ok)

        # ---- 8. owner allowlist
        try:
            gs.run("someone-else", mkcfg(gh_url, km_url))
            ok = False
        except PermissionError:
            ok = True
        check("owner outside GITHUB_OWNERS rejected", ok)

        # ---- 9. retention only prunes generated files
        W.reset()
        cfg = mkcfg(gh_url, km_url, keep_snapshots=2, keep_reports=2)
        os.makedirs(cfg.report_dir)
        open(os.path.join(cfg.report_dir, "keepme__other.md"), "w").write("x")
        for i in range(4):
            cfg.now = lambda i=i: NOW + dt.timedelta(days=i)
            gs.run("moruku36", cfg)
        reps = sorted(n for n in os.listdir(cfg.report_dir) if n.startswith("github-daily-2"))
        snaps = sorted(n for n in os.listdir(os.path.join(cfg.state_dir, "snapshots")) if n[0] == "2")
        check("retention keeps newest N reports/snapshots", len(reps) == 2 and len(snaps) == 2 and reps[-1].endswith("10-18.md"), (reps, snaps))
        check("retention never touches other files", os.path.exists(os.path.join(cfg.report_dir, "keepme__other.md")) and os.path.exists(os.path.join(cfg.report_dir, "github-daily-latest.md")))

        # ---- 10. Kuma unreachable must not break the job
        W.reset()
        cfg = mkcfg(gh_url, "http://127.0.0.1:1")
        r = gs.run("moruku36", cfg)
        check("Kuma unreachable -> job still succeeds", r["kuma_pushed"] is False and r["counts"]["repos"] == 135)
        cfg = mkcfg(gh_url, km_url, kuma_token="")
        r = gs.run("moruku36", cfg)
        check("no Kuma token configured -> push skipped quietly", r["kuma_pushed"] is False)

        # ---- 11. a poorer same-day re-run must not replace a fuller report (and must not clear a critical state)
        W.reset()
        KumaHandler.pushes.clear()
        cfg = mkcfg(gh_url, km_url)
        gs.run("moruku36", cfg)                                   # full run: critical alert for beta
        before = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        cfg.max_calls = 6                                         # simulate the shared rate limit being almost used up
        r = gs.run("moruku36", cfg)
        after = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        check("poorer same-day re-run keeps the fuller report", r.get("kept_previous") is True and before == after, r)
        check("poorer re-run repeats the earlier critical verdict to Kuma (down, not up)", KumaHandler.pushes[-1][1] == "down" and "beta" in KumaHandler.pushes[-1][2], KumaHandler.pushes[-1])
        cfg.max_calls = 45
        W.reset()
        r = gs.run("moruku36", cfg)
        check("an equally complete re-run still updates the report", not r.get("kept_previous"))

        # ---- 12. same-day protection also works against a snapshot written by an older version (no stored coverage field)
        W.reset()
        cfg = mkcfg(gh_url, km_url)
        gs.run("moruku36", cfg)
        sp = os.path.join(cfg.state_dir, "snapshots", "2026-10-15.json")
        old = json.load(open(sp, encoding="utf-8"))
        old.pop("coverage", None)
        json.dump(old, open(sp, "w", encoding="utf-8"))
        before = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        cfg.max_calls = 6
        r = gs.run("moruku36", cfg)
        check("legacy snapshot without coverage field is still protected", r.get("kept_previous") is True and before == read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md")), r)

        # ---- 13. TASK-122: a failed search must read "not collected", never "0" / "None"
        W.reset()
        W.inject["/search/issues"] = [(403, {"X-RateLimit-Remaining": "0"})] * 2
        cfg = mkcfg(gh_url, km_url)
        r = gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        why = "GitHub API rate limit reached or nearly used up"
        check("failed search: summary says 'not collected', not 0", "| Open issues (own repos) | not collected |" in rep and "| Open PRs (own repos) | not collected |" in rep)
        check("failed search: coverage table names the reason", f"| Open issues (search) | **not collected** | {why} |" in rep and f"| Open PRs (search) | **not collected** | {why} |" in rep)
        check("failed search: sections 2 and 3 say not collected, not 'None'", rep.count("_Not collected in this run (see Coverage)._") == 2)
        check("failed search: stale figures are flagged as incomplete", rep.count("incomplete: open issues/PRs not fully collected") == 2)
        check("failed search: machine-readable flags and reasons are returned", r["collected"] == {"issues": False, "prs": False} and r["coverage_detail"]["searches"] == {"issues": "rate_limit", "prs": "rate_limit"}, r["coverage_detail"])
        check("failed search: counts keep their numeric type (n8n Summary node concatenates them)", r["counts"]["issues"] == 0 and r["counts"]["prs"] == 0 and r["partial"] is True)

        # ---- 14. TASK-122: a failed search must never make every open item look closed (or, the next day, new)
        W.reset()
        cfg = mkcfg(gh_url, km_url)
        gs.run("moruku36", cfg)                                        # day 1: complete
        W.inject["/search/issues"] = [(403, {"X-RateLimit-Remaining": "0"})] * 2
        cfg.now = lambda: NOW + dt.timedelta(days=1)
        gs.run("moruku36", cfg)                                        # day 2: both searches fail
        W.inject.clear()
        d2 = read(os.path.join(cfg.report_dir, "github-daily-2026-10-16.md")).split("## 7.")[1]
        check("search failed today: issues/PRs are 'not compared' and nothing is listed as closed", d2.count("**not compared**") == 4 and "alpha#1" not in d2 and "beta#5" not in d2, d2)
        cfg.now = lambda: NOW + dt.timedelta(days=2)
        gs.run("moruku36", cfg)                                        # day 3: searches work again, but the previous snapshot has no open items
        d3 = read(os.path.join(cfg.report_dir, "github-daily-2026-10-17.md")).split("## 7.")[1]
        check("previous search had failed: nothing is shown as 'new' either", d3.count("**not compared**") == 4 and "alpha#1" not in d3, d3)
        W.issues["alpha#9"] = ("issue", "alpha", 9, "Fresh issue", 0, 0)
        cfg.now = lambda: NOW + dt.timedelta(days=3)
        gs.run("moruku36", cfg)                                        # day 4: both snapshots complete again
        d4 = read(os.path.join(cfg.report_dir, "github-daily-2026-10-18.md")).split("## 7.")[1]
        check("both snapshots complete again: comparison resumes", "Newly seen open issues: alpha#9" in d4 and "**not compared**" not in d4, d4)

        # ---- 15. TASK-122: snapshots written before this change have no 'collected' flag
        def latest_path(c):
            return os.path.join(c.state_dir, "snapshots", "latest.json")

        W.reset()
        cfg = mkcfg(gh_url, km_url)
        gs.run("moruku36", cfg)
        legacy = json.load(open(latest_path(cfg), encoding="utf-8"))
        legacy.pop("collected", None)
        legacy.pop("coverage_detail", None)
        json.dump(legacy, open(latest_path(cfg), "w", encoding="utf-8"))   # complete legacy snapshot: no flags, no note about searches
        del W.issues["beta#5"]
        cfg.now = lambda: NOW + dt.timedelta(days=1)
        gs.run("moruku36", cfg)
        d5 = read(os.path.join(cfg.report_dir, "github-daily-2026-10-16.md")).split("## 7.")[1]
        check("complete legacy snapshot is still compared", "PRs no longer open (closed OR merged; not distinguished): beta#5" in d5 and "**not compared**" not in d5, d5)
        W.reset()
        cfg = mkcfg(gh_url, km_url)
        gs.run("moruku36", cfg)
        legacy = json.load(open(latest_path(cfg), encoding="utf-8"))
        legacy.pop("collected", None)
        legacy.pop("coverage_detail", None)
        legacy.update(prs={}, partial=True, notes=["open prs not collected (API rate limit / call budget)"])   # how the previous version recorded a failed PR search
        json.dump(legacy, open(latest_path(cfg), "w", encoding="utf-8"))
        cfg.now = lambda: NOW + dt.timedelta(days=1)
        gs.run("moruku36", cfg)
        d6 = read(os.path.join(cfg.report_dir, "github-daily-2026-10-16.md")).split("## 7.")[1]
        check("legacy snapshot whose PR search had failed: PRs not compared (beta#5 not shown as new)",
              "Newly seen open PRs: **not compared**" in d6 and "PRs no longer open (closed OR merged; not distinguished): **not compared**" in d6 and "beta#5" not in d6, d6)
        check("...while issues are still compared", "Newly seen open issues: none" in d6 and "Issues no longer open (closed; reason not available): none" in d6, d6)

        # ---- 16. TASK-122: wording - what the diff can and cannot say
        check("diff wording: misleading labels are gone", "Repositories with new pushes" not in rep2 and "Closed/merged PRs" not in rep2 and "Closed issues" not in rep2)
        check("diff wording: scope note says snapshot-to-snapshot and no daily push/merge counts", "not a calendar day" in rep2 and "does not give daily push or merge counts" in rep2)

        # ---- 17. TASK-122: coverage table (N/M and reasons) for a budget-limited unauthenticated run
        W.reset()
        cfg = mkcfg(gh_url, km_url, max_calls=5)
        r = gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        why = "per-run API call budget reached (MAX_API_CALLS=5)"
        check("coverage: Actions N/M with its reason", f"| GitHub Actions | 1/2 repositories checked | {why} |" in rep, [l for l in rep.splitlines() if "GitHub Actions |" in l])
        check("coverage: last commit 0/2 with its reason", f"| last commit | 0/2 repositories checked | {why} |" in rep, [l for l in rep.splitlines() if "last commit |" in l])
        check("coverage: unauthenticated -> Dependabot not collected, reason 'no token'", "| Dependabot alerts | **not collected** | no read-only token configured |" in rep)
        check("coverage: API calls vs allowed", f"| API calls | {r['counts']['api_calls']} of 5 allowed | - |" in rep)
        check("coverage: unchecked repositories are not presented as checked (section 4)", "among 1 of 2 active repositories checked (the others were not checked" in rep)
        check("coverage: last commit of an unchecked repository reads 'not collected' (not '-')", "| not collected | 2 |" in rep)
        check("coverage: stop reasons are machine-readable", r["coverage_detail"]["passes"]["GitHub Actions"] == {"done": 1, "total": 2, "failed": 0, "stopped": "call_budget"}, r["coverage_detail"])
        W.reset()
        cfg = mkcfg(gh_url, km_url, max_active=1)
        gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        check("coverage: MAX_ACTIVE_REPOS cap is disclosed",
              "| 2 found, 1 eligible for per-repository checks | only the 1 most recently pushed are checked (MAX_ACTIVE_REPOS=1) |" in rep, [l for l in rep.splitlines() if "Active repositories" in l])

        # ---- 18. TASK-122: a complete run reports full coverage (and does not cry wolf)
        W.reset()
        cfg = mkcfg(gh_url, km_url)
        r = gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        check("complete unauthenticated run: full coverage rows",
              all(s in rep for s in ["| Repository list | 135 repositories (public only) | - |", "| Open issues (search) | collected | - |", "| Open PRs (search) | collected | - |",
                                     "| GitHub Actions | 2/2 repositories checked | - |", "| last commit | 2/2 repositories checked | - |"]), [l for l in rep.splitlines() if l.startswith("| ") and "|" in l][:25])
        check("complete run: nothing reads 'not collected' except the token-only checks", rep.count("not collected") == 2 and "**not compared**" not in rep and "Not collected in this run" not in rep, rep.count("not collected"))
        check("repository outside the active set (archived delta) says 'not checked', not 'not collected'", "| delta | public | 2026-10-10 09:00 | not checked (outside active set) | 0 |" in rep)
        W.reset()
        cfg = mkcfg(gh_url, km_url, token=TOKEN)
        r = gs.run("moruku36", cfg)
        rep = read(os.path.join(cfg.report_dir, "github-daily-2026-10-15.md"))
        check("complete authenticated run: Dependabot coverage and private repositories",
              "| Repository list | 136 repositories (public + private) | - |" in rep and "| Dependabot alerts | 3/3 repositories checked | - |" in rep, [l for l in rep.splitlines() if "Dependabot alerts |" in l])

        # ---- 19. TASK-122: result stays compatible with the n8n Summary node; nothing secret is added
        check("result keeps every key the n8n Summary node reads", all(k in r["counts"] for k in ("repos", "issues", "prs", "critical", "warn", "api_calls")) and "partial" in r and "report" in r)
        allfiles = "".join(read(os.path.join(dp, f)) for dp, _, fs in os.walk(os.path.dirname(cfg.report_dir)) for f in fs)
        check("tokens never appear in the result, snapshots or reports (coverage fields included)", TOKEN not in json.dumps(r) and TOKEN not in allfiles and KUMA not in json.dumps(r) and KUMA not in allfiles)

        # ---- 20. TASK-122: a same-day poorer re-run exposes the KEPT snapshot's collection flags (not its own)
        W.reset()
        cfg = mkcfg(gh_url, km_url)
        gs.run("moruku36", cfg)
        cfg.max_calls = 6
        r = gs.run("moruku36", cfg)
        check("kept report: result carries the kept snapshot's flags",
              r.get("kept_previous") is True and r["collected"] == {"issues": True, "prs": True} and r["coverage_detail"]["searches"] == {"issues": "ok", "prs": "ok"}, r)
    finally:
        gh.shutdown()
        km.shutdown()
    print(f"\n{len(fails)} failure(s)" if fails else "\nALL PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
