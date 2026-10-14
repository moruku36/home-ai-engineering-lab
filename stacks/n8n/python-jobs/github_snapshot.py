#!/usr/bin/env python3
"""Read-only GitHub development snapshot + daily Markdown report. stdlib only.

What it does (all READ-ONLY GET requests, never writes to GitHub):
  1. lists the owner's repositories (public only without a token; private too with a read-only PAT)
  2. finds open issues / PRs with two Search API calls (cheap: not one call per repository)
  3. for recently active, non-fork repositories: latest GitHub Actions run, last commit,
     and (token only) open Dependabot alerts - within a call budget (unauthenticated limit is 60/hour)
  4. diffs against the previous snapshot, derives alerts, writes a Markdown report + JSON snapshot
  5. reports health to an Uptime Kuma *push* monitor (down on critical alerts or collector failure)

Secrets: GITHUB_TOKEN and KUMA_PUSH_TOKEN come from the environment only and are never logged,
written to reports/snapshots, or returned to the caller.
"""
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

JST = dt.timezone(dt.timedelta(hours=9))
FAIL = {"failure", "timed_out", "startup_failure"}
SNAP_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
REPORT_NAME = re.compile(r"^github-daily-\d{4}-\d{2}-\d{2}\.md$")


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    def __init__(self, **kw):
        self.api = os.environ.get("GITHUB_API_BASE", "https://api.github.com").rstrip("/")
        self.token = os.environ.get("GITHUB_TOKEN", "").strip()
        self.owners = {o.strip() for o in os.environ.get("GITHUB_OWNERS", "").split(",") if o.strip()}
        self.state_dir = os.environ.get("STATE_DIR", "/data/state")
        self.report_dir = os.environ.get("REPORT_DIR", "/data/reports")
        self.stale_issue_days = _int("STALE_DAYS", 30)
        self.stale_repo_days = _int("STALE_REPO_DAYS", 90)
        self.active_days = _int("ACTIVE_DAYS", 14)
        self.recent_days = _int("RECENT_DAYS", 7)
        self.actions_alert_hours = _int("ACTIONS_ALERT_HOURS", 48)
        self.max_active = _int("MAX_ACTIVE_REPOS", 40)
        self.max_calls = _int("MAX_API_CALLS", 1500 if self.token else 45)
        self.http_timeout = _int("HTTP_TIMEOUT", 10)
        self.tries = _int("HTTP_TRIES", 3)
        self.retry_base = float(os.environ.get("RETRY_BASE_SECONDS", "2"))
        self.keep_snapshots = _int("KEEP_SNAPSHOTS", 30)
        self.keep_reports = _int("KEEP_REPORTS", 60)
        self.kuma_base = os.environ.get("KUMA_BASE", "http://uptime-kuma:3001").rstrip("/")
        self.kuma_token = os.environ.get("KUMA_PUSH_TOKEN", "").strip()
        self.now = lambda: dt.datetime.now(dt.timezone.utc)
        for k, v in kw.items():
            setattr(self, k, v)


def log(level, msg, **kw):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level, "msg": msg, **kw}), flush=True)


class RateLimited(Exception):
    pass


class BudgetExhausted(Exception):
    pass


class ApiError(Exception):
    pass


class GH:
    def __init__(self, cfg):
        self.cfg, self.calls, self.remaining = cfg, 0, None

    def _note(self, headers):
        try:
            if headers is not None and headers.get("X-RateLimit-Remaining") is not None:
                self.remaining = int(headers.get("X-RateLimit-Remaining"))
        except (TypeError, ValueError):
            pass

    def get(self, path, params=None, allow=()):
        """GET with timeout, bounded retries (5xx / network only) and a call budget.
        Returns (status, json|None). `allow` = HTTP codes that are returned instead of raised."""
        url = self.cfg.api + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "home-ai-lab-github-monitor/1"}
        if self.cfg.token:
            headers["Authorization"] = "Bearer " + self.cfg.token   # only ever sent to cfg.api
        last = None
        for attempt in range(1, self.cfg.tries + 1):
            if self.calls >= self.cfg.max_calls or (self.remaining is not None and self.remaining < 3):
                raise BudgetExhausted()
            self.calls += 1
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=self.cfg.http_timeout) as r:
                    self._note(r.headers)
                    return r.status, json.load(r)
            except urllib.error.HTTPError as e:
                self._note(e.headers)
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")[:300].lower()
                except Exception:  # noqa: BLE001
                    pass
                if e.code == 401:
                    raise ApiError("401 unauthorized (token invalid or expired)")
                if e.code in (403, 429) and (e.code == 429 or e.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in body):
                    raise RateLimited()
                if e.code in allow:
                    return e.code, None
                if e.code >= 500:
                    last = f"HTTP {e.code}"
                else:
                    raise ApiError(f"HTTP {e.code} on {path.split('?')[0]}")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = type(e).__name__
            log("warn", "transient upstream error", attempt=attempt, error=last, path=path.split("?")[0])
            if attempt < self.cfg.tries:
                time.sleep(self.cfg.retry_base * (2 ** (attempt - 1)))
        raise ApiError(f"upstream failed after {self.cfg.tries} tries: {last}")

    def paged(self, path, params, max_pages=10, key=None):
        out = []
        for page in range(1, max_pages + 1):
            _, data = self.get(path, dict(params, page=page))
            items = data.get(key, []) if key else data
            out.extend(items)
            if len(items) < int(params.get("per_page", 30)):
                break
        return out


def coverage_of(snap):
    """How much was collected, computed from the snapshot's CONTENT (works for snapshots written by older versions):
    (number of search results groups present, number of per-repo checks done)."""
    return (int(bool(snap.get("issues"))) + int(bool(snap.get("prs"))),
            len(snap.get("actions", {})) + len(snap.get("commits", {})) + len(snap.get("dependabot", {})))


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def age_days(ts, now):
    t = parse_ts(ts)
    return (now - t).total_seconds() / 86400 if t else None


def md(s, n=100):
    s = re.sub(r"[\r\n\t]+", " ", str(s or "")).replace("|", "\\|").strip()
    return (s[:n] + "…") if len(s) > n else s


def jst(ts):
    t = parse_ts(ts)
    return t.astimezone(JST).strftime("%Y-%m-%d %H:%M") if t else "-"


# ------------------------------------------------------------------ collection
def collect(cfg, gh, owner, prev):
    now = cfg.now()
    snap = {"schema": 1, "owner": owner, "generated_at": now.isoformat(), "authenticated": bool(cfg.token),
            "partial": False, "notes": [], "repos": {}, "issues": {}, "prs": {}, "actions": {}, "commits": {}, "dependabot": {}}

    # 1. repositories (fatal if this fails)
    if cfg.token:
        repos = gh.paged("/user/repos", {"affiliation": "owner", "per_page": 100, "sort": "pushed"}, key=None)
        repos = [r for r in repos if (r.get("owner") or {}).get("login", "").lower() == owner.lower()]
    else:
        repos = gh.paged(f"/users/{owner}/repos", {"type": "owner", "per_page": 100, "sort": "pushed"})
    for r in repos:
        snap["repos"][r["name"]] = {k: r.get(k) for k in ("private", "fork", "archived", "pushed_at", "default_branch", "open_issues_count", "html_url")}

    def mark_partial(why):
        snap["partial"] = True
        if why not in snap["notes"]:
            snap["notes"].append(why)

    # 2. open issues / PRs via search (2+ calls instead of N calls)
    for kind, bucket in (("issue", "issues"), ("pr", "prs")):
        try:
            items = gh.paged("/search/issues", {"q": f"user:{owner} is:open is:{kind}", "per_page": 100, "sort": "updated", "order": "desc"}, max_pages=5, key="items")
        except (RateLimited, BudgetExhausted):
            mark_partial(f"open {kind}s not collected (API rate limit / call budget)")
            continue
        except ApiError as e:               # e.g. 403 secondary limit / 422: degrade, still produce the report
            log("warn", "search failed", kind=kind, error=str(e)[:120])
            mark_partial(f"open {kind}s not collected (search API error)")
            continue
        for it in items:
            repo = (it.get("repository_url") or "").rsplit("/", 1)[-1]
            snap[bucket][f"{repo}#{it['number']}"] = {"repo": repo, "number": it["number"], "title": it.get("title"), "created_at": it.get("created_at"),
                                                     "updated_at": it.get("updated_at"), "url": it.get("html_url"), "draft": bool(it.get("draft")),
                                                     "author": (it.get("user") or {}).get("login")}

    # 3. per-repo detail for recently active own repositories, in priority passes
    own = {n: r for n, r in snap["repos"].items() if not r["fork"]}
    active = sorted((n for n, r in own.items() if not r["archived"] and (age_days(r["pushed_at"], now) or 1e9) <= cfg.active_days),
                    key=lambda n: own[n]["pushed_at"] or "", reverse=True)[:cfg.max_active]

    def run_pass(label, fn, repos_):
        done, failed = 0, []
        try:
            for n in repos_:
                try:
                    fn(n)
                    done += 1
                except ApiError as e:           # one bad repository must not abort the whole run
                    failed.append(n)
                    log("warn", "repo check failed", pass_=label, repo=n, error=str(e)[:120])
        except (RateLimited, BudgetExhausted):
            mark_partial(f"{label}: {done}/{len(repos_)} active repositories checked (API rate limit / call budget; add a read-only token to raise it)")
        if failed:
            mark_partial(f"{label}: failed for {len(failed)} repositories ({', '.join(failed[:5])})")

    def do_actions(n):
        st, data = gh.get(f"/repos/{owner}/{n}/actions/runs", {"branch": own[n]["default_branch"] or "main", "per_page": 10}, allow=(404,))
        runs = [x for x in ((data or {}).get("workflow_runs") or []) if x.get("status") == "completed"]
        latest = runs[0] if runs else None
        fails = [x for x in runs if x.get("conclusion") in FAIL and (age_days(x.get("created_at"), now) or 1e9) <= cfg.recent_days]
        pick = lambda x: {"id": x["id"], "name": x.get("name"), "conclusion": x.get("conclusion"), "created_at": x.get("created_at"), "url": x.get("html_url")}  # noqa: E731
        snap["actions"][n] = {"latest": pick(latest) if latest else None, "failures": [pick(x) for x in fails]}

    def do_commit(n):
        st, data = gh.get(f"/repos/{owner}/{n}/commits", {"per_page": 1, "sha": own[n]["default_branch"] or "main"}, allow=(404, 409))
        if data:
            c = data[0]
            snap["commits"][n] = {"sha": c["sha"][:7], "message": (c["commit"]["message"] or "").splitlines()[0][:100], "date": c["commit"]["author"]["date"]}

    def do_dependabot(n):
        st, data = gh.get(f"/repos/{owner}/{n}/dependabot/alerts", {"state": "open", "per_page": 100}, allow=(403, 404))
        if data is None:
            snap["dependabot"][n] = {"available": False}
            return
        sev = {}
        for a in data:
            s = ((a.get("security_vulnerability") or {}).get("severity") or (a.get("security_advisory") or {}).get("severity") or "unknown").lower()
            sev[s] = sev.get(s, 0) + 1
        snap["dependabot"][n] = {"available": True, "open": len(data), "by_severity": sev}

    run_pass("GitHub Actions", do_actions, active)
    run_pass("last commit", do_commit, active)
    if cfg.token:
        run_pass("Dependabot alerts", do_dependabot, active)
    else:
        snap["notes"].append("Dependabot alerts and private repositories are not included (no read-only token configured)")
    snap["api_calls"], snap["rate_remaining"], snap["active_repos"] = gh.calls, gh.remaining, active
    # how much was actually collected: (search results present?, per-repo checks done) - used to avoid
    # replacing a fuller report from the same day with a poorer one (e.g. a manual re-run at the rate limit)
    return snap


# ------------------------------------------------------------------ analysis
def derive_alerts(cfg, snap, now):
    alerts = []
    for n, a in snap["actions"].items():
        latest = a["latest"]
        if latest and latest["conclusion"] in FAIL and (age_days(latest["created_at"], now) or 1e9) * 24 <= cfg.actions_alert_hours:
            alerts.append({"key": f"actions:{n}:{latest['id']}", "severity": "critical", "repo": n,
                           "text": f"GitHub Actions failing on default branch of {n}: {latest['name']} ({latest['conclusion']})", "url": latest["url"]})
    for n, d in snap["dependabot"].items():
        sev = d.get("by_severity", {}) if d.get("available") else {}
        crit, high = sev.get("critical", 0), sev.get("high", 0)
        if crit or high:
            alerts.append({"key": f"dependabot:{n}:{crit}-{high}", "severity": "critical", "repo": n,
                           "text": f"Dependabot: {crit} critical / {high} high open alert(s) in {n}", "url": ""})
    for coll in ("issues", "prs"):
        for k, it in snap[coll].items():
            if (age_days(it["updated_at"], now) or 0) >= cfg.stale_issue_days:
                alerts.append({"key": f"stale:{k}", "severity": "warn", "repo": it["repo"], "text": f"Stale {coll[:-1].upper()} {k}: {it['title']}", "url": it["url"]})
    if snap["partial"]:
        alerts.append({"key": "collector:partial", "severity": "warn", "repo": "", "text": "Collector ran with partial data: " + "; ".join(snap["notes"]), "url": ""})
    return alerts


def diff(prev, snap):
    if not prev:
        return None
    d = {"new_repos": sorted(set(snap["repos"]) - set(prev.get("repos", {}))),
         "pushed": sorted(n for n, r in snap["repos"].items() if n in prev.get("repos", {}) and r["pushed_at"] != prev["repos"][n]["pushed_at"]),
         "new_issues": sorted(set(snap["issues"]) - set(prev.get("issues", {}))), "closed_issues": sorted(set(prev.get("issues", {})) - set(snap["issues"])),
         "new_prs": sorted(set(snap["prs"]) - set(prev.get("prs", {}))), "closed_prs": sorted(set(prev.get("prs", {})) - set(snap["prs"])),
         "prev_at": prev.get("generated_at")}
    old = {f["id"] for a in prev.get("actions", {}).values() for f in a.get("failures", [])}
    d["new_failures"] = sorted(f"{n}: {f['name']} #{f['id']}" for n, a in snap["actions"].items() for f in a["failures"] if f["id"] not in old)
    return d


# ------------------------------------------------------------------ report
def build_report(cfg, snap, alerts, d, state, now):
    owner, repos = snap["owner"], snap["repos"]
    own = {n: r for n, r in repos.items() if not r["fork"]}
    forks = len(repos) - len(own)
    today = now.astimezone(JST)
    crit = [a for a in alerts if a["severity"] == "critical"]
    issues_own = {k: v for k, v in snap["issues"].items() if v["repo"] in own}
    prs_own = {k: v for k, v in snap["prs"].items() if v["repo"] in own}
    stale_items = [a for a in alerts if a["key"].startswith("stale:") and a["repo"] in own]
    L = [f"# GitHub daily report — {owner} — {today:%Y-%m-%d} (JST)", "",
         f"_Generated {today:%Y-%m-%d %H:%M} JST · read-only · {snap['api_calls']} API calls · "
         f"{'authenticated (read-only token)' if snap['authenticated'] else 'unauthenticated (public data only)'}_", ""]
    if snap["partial"] or snap["notes"]:
        L += ["> **Data completeness / データの完全性**"] + [f"> - {md(n, 300)}" for n in snap["notes"]] + [""]
    L += ["## Summary / 概要", "",
          "| Item | Count |", "|---|---|",
          f"| Repositories (own / forks) | {len(own)} / {forks} |",
          f"| Archived (own) | {sum(1 for r in own.values() if r['archived'])} |",
          f"| Private (own) | {sum(1 for r in own.values() if r['private'])} |",
          f"| Open issues (own repos) | {len(issues_own)} |", f"| Open PRs (own repos) | {len(prs_own)} |",
          f"| Critical alerts | {len(crit)} |", f"| Stale issues/PRs (≥{cfg.stale_issue_days}d) | {len(stale_items)} |", ""]
    if crit:
        L += ["### ⚠️ Critical alerts / 重要な警告", ""] + [f"- **{md(a['text'], 200)}**" + (f" — {a['url']}" if a["url"] else "") for a in crit] + [""]

    L += [f"## 1. Recently updated repositories / 最近更新（{cfg.recent_days}日以内）", ""]
    recent = sorted((n for n, r in own.items() if (age_days(r["pushed_at"], now) or 1e9) <= cfg.recent_days), key=lambda n: own[n]["pushed_at"], reverse=True)
    if recent:
        L += ["| Repository | Visibility | Last push (JST) | Last commit | Open issues |", "|---|---|---|---|---|"]
        for n in recent:
            c = snap["commits"].get(n)
            L.append(f"| {md(n)} | {'private' if own[n]['private'] else 'public'} | {jst(own[n]['pushed_at'])} | {md(c['sha'] + ' ' + c['message']) if c else '-'} | {own[n]['open_issues_count']} |")
    else:
        L.append("_None._")

    L += ["", f"## 2. New / updated issues / 新規・更新Issue（直近2日）", ""]
    upd = sorted((v for v in issues_own.values() if (age_days(v["updated_at"], now) or 1e9) <= 2), key=lambda v: v["updated_at"], reverse=True)
    L += [f"- {'🆕 ' if (age_days(v['created_at'], now) or 1e9) <= 2 else ''}[{md(v['repo'])}#{v['number']}]({v['url']}) {md(v['title'])} _(updated {jst(v['updated_at'])})_" for v in upd] or ["_None._"]

    L += ["", "## 3. Open pull requests / 未対応PR", ""]
    if prs_own:
        L += ["| PR | Title | Age (days) | Draft |", "|---|---|---|---|"]
        for v in sorted(prs_own.values(), key=lambda v: v["created_at"]):
            L.append(f"| [{md(v['repo'])}#{v['number']}]({v['url']}) | {md(v['title'])} | {int(age_days(v['created_at'], now) or 0)} | {'yes' if v['draft'] else ''} |")
    else:
        L.append("_None._")

    L += ["", "## 4. Failed GitHub Actions / 失敗したActions", ""]
    failing = {n: a for n, a in snap["actions"].items() if a["failures"] or (a["latest"] and a["latest"]["conclusion"] in FAIL)}
    if failing:
        for n, a in sorted(failing.items()):
            st = "**currently failing**" if a["latest"] and a["latest"]["conclusion"] in FAIL else "recovered (latest run OK)"
            L.append(f"- {md(n)}: {st}; {len(a['failures'])} failed run(s) in the last {cfg.recent_days} days" + (f" — latest: {a['latest']['url']}" if a["latest"] else ""))
    else:
        L.append(f"_No failures among {len(snap['actions'])} active repositories checked._")

    L += ["", "## 5. Security notes / セキュリティ上の注意", ""]
    if snap["authenticated"]:
        av = {n: d_ for n, d_ in snap["dependabot"].items() if d_.get("available")}
        un = [n for n, d_ in snap["dependabot"].items() if not d_.get("available")]
        L += [f"- Dependabot: {sum(d_['open'] for d_ in av.values())} open alert(s) across {len(av)} repositories checked" + (f"; unavailable for {len(un)} (token lacks permission or alerts disabled)" if un else "")]
        L += [f"  - {md(n)}: " + ", ".join(f"{k} {v}" for k, v in d_["by_severity"].items()) for n, d_ in sorted(av.items()) if d_["open"]]
    else:
        L.append("- Dependabot alerts: **not collected** (needs a read-only token with the Dependabot alerts permission).")
    pub_no_issue = [n for n, r in own.items() if not r["private"] and not r["archived"]]
    L.append(f"- {len(pub_no_issue)} public, non-archived repositories: keep secrets out of them; run `scripts/scan-secrets.sh` on important ones.")

    L += ["", f"## 6. Stale projects / 長期間更新されていないプロジェクト", ""]
    stale_repos = sorted((n for n, r in own.items() if not r["archived"] and (age_days(r["pushed_at"], now) or 0) >= cfg.stale_repo_days), key=lambda n: own[n]["pushed_at"] or "")
    L += [f"- Repositories with no push for ≥{cfg.stale_repo_days} days: " + (", ".join(f"{md(n)} ({jst(own[n]['pushed_at'])[:10]})" for n in stale_repos[:20]) + (f" … +{len(stale_repos) - 20}" if len(stale_repos) > 20 else "") if stale_repos else "none")]
    L += [f"- Issues/PRs not updated for ≥{cfg.stale_issue_days} days: " + ("; ".join(f"[{md(a['text'], 70)}]({a['url']})" for a in stale_items[:15]) if stale_items else "none")]

    L += ["", "## 7. Changes since the previous snapshot / 前回収集との差分", ""]
    if not d:
        L.append("_First snapshot — nothing to compare yet._")
    else:
        L.append(f"_Previous snapshot: {jst(d['prev_at'])} JST_")
        for label, key in (("New repositories", "new_repos"), ("Repositories with new pushes", "pushed"), ("New issues", "new_issues"), ("Closed issues", "closed_issues"),
                           ("New PRs", "new_prs"), ("Closed/merged PRs", "closed_prs"), ("New Actions failures", "new_failures")):
            L.append(f"- {label}: " + (", ".join(md(x) for x in d[key][:20]) + (f" … +{len(d[key]) - 20}" if len(d[key]) > 20 else "") if d[key] else "none"))
    L += ["", "---", f"_Scope: owner `{owner}` only; forks are counted but not analysed. Nothing was written to GitHub._", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ storage / notify
def _atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _prune(directory, pattern, keep):
    try:
        names = sorted(n for n in os.listdir(directory) if pattern.match(n))
    except FileNotFoundError:
        return 0
    old = names[:-keep] if keep > 0 else names
    for n in old:
        os.remove(os.path.join(directory, n))
    return len(old)


def ping_kuma(cfg, status, msg):
    """Best-effort heartbeat to an Uptime Kuma push monitor. Never raises, never logs the token."""
    if not cfg.kuma_token:
        return False
    url = f"{cfg.kuma_base}/api/push/{urllib.parse.quote(cfg.kuma_token, safe='')}?" + urllib.parse.urlencode({"status": status, "msg": msg[:200], "ping": ""})
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except Exception as e:  # noqa: BLE001
        log("warn", "kuma push failed", error=type(e).__name__)
        return False


def run(owner, cfg=None):
    cfg = cfg or Config()
    if owner not in cfg.owners:
        raise PermissionError("owner not in GITHUB_OWNERS")
    now = cfg.now()
    snap_dir = os.path.join(cfg.state_dir, "snapshots")
    prev = None
    try:
        with open(os.path.join(snap_dir, "latest.json"), encoding="utf-8") as f:
            prev = json.load(f)
    except (FileNotFoundError, ValueError):
        pass
    gh = GH(cfg)
    try:
        snap = collect(cfg, gh, owner, prev)
    except (RateLimited, BudgetExhausted):
        ping_kuma(cfg, "down", "collector: API rate limit before repository list was read")
        raise ApiError("rate limited / budget exhausted before the repository list could be read")
    except ApiError as e:
        ping_kuma(cfg, "down", f"collector error: {e}")
        raise
    alerts = derive_alerts(cfg, snap, now)
    d = diff(prev, snap)
    today = now.astimezone(JST).strftime("%Y-%m-%d")

    # Same-day re-run that collected LESS than the existing snapshot: keep the fuller one, change nothing.
    try:
        with open(os.path.join(snap_dir, f"{today}.json"), encoding="utf-8") as f:
            same_day = json.load(f)
    except (FileNotFoundError, ValueError):
        same_day = None
    if same_day and snap["partial"] and coverage_of(snap) < coverage_of(same_day):
        log("warn", "re-run collected less than the existing report of today; keeping the existing report", new=list(coverage_of(snap)), old=list(coverage_of(same_day)))
        old_crit = [a["text"] for a in same_day.get("alerts", []) if a["severity"] == "critical"]
        # never clear an existing critical state because of a poorer re-run: repeat the earlier verdict
        pushed = ping_kuma(cfg, "down", f"{len(old_crit)} critical: " + "; ".join(old_crit)[:150]) if old_crit else ping_kuma(cfg, "up", "re-run was partial; kept today's fuller report")
        return {"report": f"github-daily-{today}.md", "latest": "github-daily-latest.md", "partial": True, "authenticated": snap["authenticated"], "kept_previous": True,
                "counts": {"repos": len(same_day.get("repos", {})), "issues": len(same_day.get("issues", {})), "prs": len(same_day.get("prs", {})),
                           "critical": sum(1 for a in same_day.get("alerts", []) if a["severity"] == "critical"), "warn": sum(1 for a in same_day.get("alerts", []) if a["severity"] != "critical"),
                           "api_calls": gh.calls},
                "critical_alerts": [a["text"] for a in same_day.get("alerts", []) if a["severity"] == "critical"][:10],
                "notes": snap["notes"] + ["kept today's earlier, fuller report (this run was partial)"], "kuma_pushed": pushed}

    # alert state: remember first_seen so reports can show how long something has been open
    sp = os.path.join(cfg.state_dir, "alerts_state.json")
    try:
        with open(sp, encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, ValueError):
        st = {}
    st = {a["key"]: {"first_seen": st.get(a["key"], {}).get("first_seen", now.isoformat()), "severity": a["severity"]} for a in alerts}
    _atomic(sp, json.dumps(st, indent=1))

    report = build_report(cfg, snap, alerts, d, st, now)
    rp = os.path.join(cfg.report_dir, f"github-daily-{today}.md")
    _atomic(rp, report)
    _atomic(os.path.join(cfg.report_dir, "github-daily-latest.md"), report)
    snap["alerts"] = [{k: v for k, v in a.items() if k != "url"} for a in alerts]
    _atomic(os.path.join(snap_dir, f"{today}.json"), json.dumps(snap, indent=1))
    _atomic(os.path.join(snap_dir, "latest.json"), json.dumps(snap, indent=1))
    pruned = _prune(snap_dir, SNAP_NAME, cfg.keep_snapshots), _prune(cfg.report_dir, REPORT_NAME, cfg.keep_reports)

    crit = [a for a in alerts if a["severity"] == "critical"]
    if crit:
        pushed = ping_kuma(cfg, "down", f"{len(crit)} critical: " + "; ".join(a["text"] for a in crit)[:150])
    else:
        pushed = ping_kuma(cfg, "up", f"OK repos={len(snap['repos'])} issues={len(snap['issues'])} prs={len(snap['prs'])}" + (" PARTIAL" if snap["partial"] else ""))
    log("info", "snapshot done", repos=len(snap["repos"]), calls=gh.calls, partial=snap["partial"], critical=len(crit), pruned=list(pruned))
    return {"report": f"github-daily-{today}.md", "latest": "github-daily-latest.md", "partial": snap["partial"], "authenticated": snap["authenticated"],
            "counts": {"repos": len(snap["repos"]), "issues": len(snap["issues"]), "prs": len(snap["prs"]), "critical": len(crit),
                       "warn": len(alerts) - len(crit), "api_calls": gh.calls},
            "critical_alerts": [a["text"] for a in crit][:10], "notes": snap["notes"], "kuma_pushed": pushed}
