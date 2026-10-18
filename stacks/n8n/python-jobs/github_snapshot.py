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
        # API calls withheld from the per-repository checks so that section 8 can run (4 searches + 2 for extra pages / PR lookups)
        self.activity_reserve = _int("ACTIVITY_RESERVE_CALLS", 6)
        self.activity = os.environ.get("GITHUB_ACTIVITY", "1").strip() != "0"     # previous-JST-day activity section; "0" = off (report as before)
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


def stop_reason(e):
    """Why collection stopped: 'rate_limit' (GitHub's own limit reached / nearly used up) or 'call_budget' (our per-run MAX_API_CALLS)."""
    return "rate_limit" if isinstance(e, RateLimited) or (e.args and e.args[0] == "rate_limit") else "call_budget"


class GH:
    def __init__(self, cfg):
        self.cfg, self.calls, self.remaining = cfg, 0, None
        self.reserve = 0        # calls withheld for later work (previous-day activity); 0 = the whole MAX_API_CALLS is usable

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
            if self.calls >= self.cfg.max_calls - self.reserve:
                raise BudgetExhausted("call_budget")        # our own per-run limit (MAX_API_CALLS)
            if self.remaining is not None and self.remaining < 3:
                raise BudgetExhausted("rate_limit")         # GitHub's limit is (nearly) used up
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


# ------------------------------------------------------------------ previous-JST-day activity (TASK-122, part 2)
def activity_window(now):
    """The previous JST calendar day as a half-open UTC interval [start, end): 00:00 JST of yesterday .. 00:00 JST of today."""
    day = now.astimezone(JST).replace(hour=0, minute=0, second=0, microsecond=0)
    return (day - dt.timedelta(days=1)).astimezone(dt.timezone.utc), day.astimezone(dt.timezone.utc)


def _utc(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _in_window(ts, start, end):
    t = parse_ts(ts)
    return bool(t) and start <= t < end


def search_window(gh, query):
    """All pages of one issue/PR search (GitHub returns at most 1000 results per search, 100 per page).
    Returns (items, why_incomplete): why_incomplete is None only when GitHub reported total_count <= 1000, incomplete_results=false
    and every result was fetched; otherwise the items are a lower bound."""
    items, total, incomplete = [], None, False
    for page in range(1, 11):
        try:
            _, data = gh.get("/search/issues", {"q": query, "per_page": 100, "page": page})
        except (RateLimited, BudgetExhausted, ApiError) as e:
            if not items:
                raise
            reason = STOP_REASONS.get(stop_reason(e), "per-run API call budget reached") if not isinstance(e, ApiError) else "search API error"
            return items, f"stopped after {len(items)} result(s): {reason}"      # a lower bound, not nothing
        batch = data.get("items") or []
        items.extend(batch)
        total = data.get("total_count") if isinstance(data.get("total_count"), int) else total
        incomplete = incomplete or bool(data.get("incomplete_results"))
        if len(batch) < 100 or (total is not None and len(items) >= total):
            break
    if incomplete:
        return items, "GitHub reported incomplete_results (search timed out)"
    if total is None or total > 1000:
        return items, "more than 1000 matches (GitHub search returns at most 1000)"
    if len(items) < total:
        return items, f"only {len(items)} of {total} matches were returned"
    return items, None


def collect_activity(cfg, gh, owner, snap, now):
    """Counts for the previous JST day, from the Search API only (no new permission, no extra token). Each metric is stored as
    {"status": "ok" | "incomplete" | "rate_limit" | "call_budget" | "api_error", "why": str, "keys": ["repo#number", ...]}.
    A metric that could not be collected has NO count: it must never be shown as 0. Pushes and commits are NOT collected here."""
    start, end = activity_window(now)
    own = {n for n, r in snap["repos"].items() if not r["fork"]}
    # the search qualifiers are inclusive and their boundary handling is not documented, so ask for a slightly wider range and
    # apply the exact half-open filter [start, end) to each item's timestamp below.
    rng = f"{(start - dt.timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%S+00:00')}..{end.strftime('%Y-%m-%dT%H:%M:%S+00:00')}"
    act = {"window": {"start": _utc(start), "end": _utc(end)}, "scope": "public + private (read-only token)" if cfg.token else "public repositories only",
           "metrics": {}, "ignored_outside_own_nonfork": 0, "collected_at": now.isoformat()}
    snap["activity"] = act

    def fail(names, e):
        for n in names:
            act["metrics"][n] = {"status": e, "why": STOP_REASONS.get(e, "per-run API call budget reached" if e == "call_budget" else e), "keys": []}

    def fetch(q, names):
        try:
            return search_window(gh, q)
        except (RateLimited, BudgetExhausted) as e:
            fail(names, stop_reason(e))
        except ApiError as e:
            log("warn", "activity search failed", error=str(e)[:120])
            fail(names, "api_error")
        return None

    def mine(items, field):
        """Own non-fork repositories only, timestamp inside the window, de-duplicated by repo#number."""
        out = {}
        for it in items:
            repo = (it.get("repository_url") or "").rsplit("/", 1)[-1]
            if repo not in own:
                act["ignored_outside_own_nonfork"] += 1
                continue
            if _in_window(it.get(field), start, end):
                out[f"{repo}#{it['number']}"] = it
        return out

    def record(name, keys, why):
        act["metrics"][name] = {"status": "incomplete" if why else "ok", "why": why or "", "keys": sorted(keys)}

    for name, q, field in (("prs_opened", f"user:{owner} is:pr created:{rng}", "created_at"),
                           ("issues_opened", f"user:{owner} is:issue created:{rng}", "created_at"),
                           ("issues_closed", f"user:{owner} is:issue is:closed closed:{rng}", "closed_at")):
        res = fetch(q, [name])
        if res:
            record(name, mine(res[0], field), res[1])

    # closed PRs: merged only when merged_at (not just "closed") is inside the window
    res = fetch(f"user:{owner} is:pr is:closed closed:{rng}", ["prs_merged", "prs_closed_unmerged"])
    if res:
        merged, unmerged, unresolved, why = [], [], [], res[1] or ""
        for key, it in mine(res[0], "closed_at").items():
            pr = it.get("pull_request") or {}
            if "merged_at" in pr:
                m = pr["merged_at"]
            else:   # search item without merged_at: ask the pull request itself (documented field), never guess
                try:
                    _, data = gh.get(f"/repos/{owner}/{key.rsplit('#', 1)[0]}/pulls/{it['number']}", allow=(404,))
                    m = (data or {}).get("merged_at", "?") if data else "?"
                except (RateLimited, BudgetExhausted, ApiError):
                    m = "?"
            if m is None:
                unmerged.append(key)
            elif m != "?" and _in_window(m, start, end):
                merged.append(key)
            else:
                unresolved.append(key)
        if unresolved:
            why = (why + "; " if why else "") + f"merged/closed could not be determined for {len(unresolved)} PR(s): {', '.join(sorted(unresolved)[:5])}"
        record("prs_merged", merged, why)
        record("prs_closed_unmerged", unmerged, why)


# ------------------------------------------------------------------ collection
def collect(cfg, gh, owner, prev):
    now = cfg.now()
    # "collected" / "coverage_detail" are additive (schema stays 1): they record WHAT was actually collected and WHY not, so that
    # the report never shows an empty bucket as "0 / none" and the diff never treats an uncollected bucket as "all closed".
    snap = {"schema": 1, "owner": owner, "generated_at": now.isoformat(), "authenticated": bool(cfg.token),
            "partial": False, "notes": [], "repos": {}, "issues": {}, "prs": {}, "actions": {}, "commits": {}, "dependabot": {},
            "collected": {"issues": False, "prs": False}, "coverage_detail": {"searches": {}, "passes": {}, "active_total": 0, "api_budget": cfg.max_calls}}

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
        except (RateLimited, BudgetExhausted) as e:
            snap["coverage_detail"]["searches"][bucket] = stop_reason(e)
            mark_partial(f"open {kind}s not collected (API rate limit / call budget)")
            continue
        except ApiError as e:               # e.g. 403 secondary limit / 422: degrade, still produce the report
            log("warn", "search failed", kind=kind, error=str(e)[:120])
            snap["coverage_detail"]["searches"][bucket] = "api_error"
            mark_partial(f"open {kind}s not collected (search API error)")
            continue
        snap["collected"][bucket] = True
        snap["coverage_detail"]["searches"][bucket] = "ok"
        for it in items:
            repo = (it.get("repository_url") or "").rsplit("/", 1)[-1]
            snap[bucket][f"{repo}#{it['number']}"] = {"repo": repo, "number": it["number"], "title": it.get("title"), "created_at": it.get("created_at"),
                                                     "updated_at": it.get("updated_at"), "url": it.get("html_url"), "draft": bool(it.get("draft")),
                                                     "author": (it.get("user") or {}).get("login")}

    # 3. per-repo detail for recently active own repositories, in priority passes
    own = {n: r for n, r in snap["repos"].items() if not r["fork"]}
    active_all = sorted((n for n, r in own.items() if not r["archived"] and (age_days(r["pushed_at"], now) or 1e9) <= cfg.active_days),
                        key=lambda n: own[n]["pushed_at"] or "", reverse=True)
    active = active_all[:cfg.max_active]
    snap["coverage_detail"]["active_total"] = len(active_all)

    if getattr(cfg, "activity", True):
        gh.reserve = max(0, min(cfg.activity_reserve, cfg.max_calls - gh.calls))     # per-repository checks give way first; section 8 keeps its calls
        snap["coverage_detail"]["activity_reserve"] = gh.reserve

    def run_pass(label, fn, repos_):
        done, failed, stopped = 0, [], None
        try:
            for n in repos_:
                try:
                    fn(n)
                    done += 1
                except ApiError as e:           # one bad repository must not abort the whole run
                    failed.append(n)
                    log("warn", "repo check failed", pass_=label, repo=n, error=str(e)[:120])
        except (RateLimited, BudgetExhausted) as e:
            stopped = stop_reason(e)
            mark_partial(f"{label}: {done}/{len(repos_)} active repositories checked (API rate limit / call budget; add a read-only token to raise it)")
        if failed:
            mark_partial(f"{label}: failed for {len(failed)} repositories ({', '.join(failed[:5])})")
        snap["coverage_detail"]["passes"][label] = {"done": done, "total": len(repos_), "failed": len(failed), "stopped": stopped}

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
        snap["coverage_detail"]["passes"]["Dependabot alerts"] = {"done": 0, "total": len(active), "failed": 0, "stopped": "no_token"}
    remaining_before_activity = gh.remaining      # search has its own, much smaller bucket: keep the figure the report always showed
    gh.reserve = 0                            # release the withheld calls: section 8 may use them (and whatever the checks left over)
    if getattr(cfg, "activity", True):
        collect_activity(cfg, gh, owner, snap, now)
    snap["api_calls"], snap["rate_remaining"], snap["active_repos"] = gh.calls, remaining_before_activity, active
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


def was_collected(snap, bucket):
    """Were the open issues / PRs ('issues' / 'prs') actually collected for this snapshot?
    Snapshots written before TASK-122 have no flag: infer it from their notes (same wording as today)."""
    flags = snap.get("collected")
    if isinstance(flags, dict) and bucket in flags:
        return bool(flags[bucket])
    return not any(f"open {bucket} not collected" in n for n in snap.get("notes", []))


def diff(prev, snap):
    """Snapshot-to-snapshot comparison (NOT a calendar-day count). 'pushed' = repositories whose last-push time changed
    (names only, not a number of pushes/commits); 'closed_*' = no longer in the OPEN set (closed OR merged, not distinguishable).
    A bucket is only compared when it was collected in BOTH snapshots; otherwise its entries are None (not compared),
    so a failed search can never show every previous open item as closed (or every current one as new)."""
    if not prev:
        return None
    d = {"new_repos": sorted(set(snap["repos"]) - set(prev.get("repos", {}))),
         "pushed": sorted(n for n, r in snap["repos"].items() if n in prev.get("repos", {}) and r["pushed_at"] != prev["repos"][n]["pushed_at"]),
         "prev_at": prev.get("generated_at"), "not_compared": []}
    for bucket, new_k, closed_k in (("issues", "new_issues", "closed_issues"), ("prs", "new_prs", "closed_prs")):
        if was_collected(snap, bucket) and was_collected(prev, bucket):
            d[new_k] = sorted(set(snap[bucket]) - set(prev.get(bucket, {})))
            d[closed_k] = sorted(set(prev.get(bucket, {})) - set(snap[bucket]))
        else:
            d[new_k] = d[closed_k] = None
            d["not_compared"].append(bucket)
    old ={f["id"] for a in prev.get("actions", {}).values() for f in a.get("failures", [])}
    d["new_failures"] = sorted(f"{n}: {f['name']} #{f['id']}" for n, a in snap["actions"].items() for f in a["failures"] if f["id"] not in old)
    return d


# ------------------------------------------------------------------ report
STOP_REASONS = {"rate_limit": "GitHub API rate limit reached or nearly used up", "no_token": "no read-only token configured", "api_error": "search API error"}


def activity_summary(snap):
    """Machine-readable view of section 8 for the run() result: count is None unless measured (status 'incomplete' = lower bound)."""
    ms = (snap or {}).get("activity", {}).get("metrics") if (snap or {}).get("activity") else None
    if ms is None:
        return None
    return {k: {"status": m["status"], "count": len(m["keys"]) if m["status"] in ("ok", "incomplete") else None} for k, m in ms.items()}


def coverage_lines(cfg, snap):
    """What was collected and, if not, why. Only measured values from snap['coverage'] / snap['collected'] are shown."""
    cov = snap.get("coverage_detail") or {}
    held = cov.get("activity_reserve") or 0
    reasons = dict(STOP_REASONS, call_budget=f"per-run API call budget reached (MAX_API_CALLS={cfg.max_calls}"
                   + (f"; {held} calls are held back for section 8, ACTIVITY_RESERVE_CALLS" if held else "") + ")")
    L = ["### Coverage / 取得範囲", "", "| Check | Collected | Not collected: reason |", "|---|---|---|",
         f"| Repository list | {len(snap['repos'])} repositories ({'public + private' if snap['authenticated'] else 'public only'}) | - |"]
    for bucket, label in (("issues", "Open issues"), ("prs", "Open PRs")):
        if was_collected(snap, bucket):
            L.append(f"| {label} (search) | collected | - |")
        else:
            L.append(f"| {label} (search) | **not collected** | {reasons.get((cov.get('searches') or {}).get(bucket), 'unknown')} |")
    total = cov.get("active_total", len(snap.get("active_repos", [])))
    checked = len(snap.get("active_repos", []))
    L.append(f"| Active repositories (non-fork, not archived, pushed ≤{cfg.active_days}d) | {total} found, {checked} eligible for per-repository checks | "
             + (f"only the {checked} most recently pushed are checked (MAX_ACTIVE_REPOS={cfg.max_active})" if total > checked else "-") + " |")
    for label in ("GitHub Actions", "last commit", "Dependabot alerts"):
        p = (cov.get("passes") or {}).get(label)
        if not p:
            continue
        if p["stopped"] == "no_token":
            L.append(f"| {label} | **not collected** | {reasons['no_token']} |")
            continue
        why = []
        if p["stopped"]:
            why.append(reasons[p["stopped"]])
        if p["failed"]:
            why.append(f"{p['failed']} repositories failed")
        L.append(f"| {label} | {p['done']}/{p['total']} repositories checked | " + ("; ".join(why) if why else "-") + " |")
    ms = (snap.get("activity") or {}).get("metrics")
    if ms is not None:
        okc = sum(1 for m in ms.values() if m["status"] == "ok")
        bad = sorted({m["why"] for m in ms.values() if m["status"] != "ok" and m.get("why")})
        L.append(f"| Previous-day activity (section 8) | {okc}/{len(ms)} metrics read in full (as of collection time; NOT a final value for the day (search-index delay is unverified)) | " + (md("; ".join(bad), 200) if bad else "-") + " |")
    remaining = snap.get("rate_remaining")
    L.append(f"| API calls | {snap['api_calls']} of {cfg.max_calls} allowed | - |")
    if remaining is not None:
        L.append(f"| GitHub rate limit remaining (as reported by GitHub) | {remaining} | - |")
    L.append("")
    return L


def _names(keys, n=15):
    return ", ".join(md(k) for k in keys[:n]) + (f" … +{len(keys) - n}" if len(keys) > n else "")


def activity_lines(cfg, snap):
    """Section 8. A metric is a number only when it was measured; otherwise 'not collected' + reason (never 0); a lower bound is '≥N'."""
    act = snap.get("activity")
    if not act:
        return []
    s, e = parse_ts(act["window"]["start"]), parse_ts(act["window"]["end"])
    fmt = lambda t: t.astimezone(JST).strftime("%Y-%m-%d %H:%M")  # noqa: E731
    L = ["", "## 8. Activity in the previous JST day / 前日（JST）の活動", "",
         f"_Window: {fmt(s)} ≤ t < {fmt(e)} JST (half-open). Scope: own non-fork repositories, {act['scope']}. "
         f"Read from GitHub search at {fmt(parse_ts(act['collected_at'])) if act.get('collected_at') else 'collection time'} JST: all results of the searches were scanned (unless a row says '≥'), "
         "but this is what the search index returned at that moment. GitHub does not document how long indexing takes (not verified here), so items indexed later may be missing: "
         "a count is **not a final value for the day**. Counts are the current state of items; an item reopened later, deleted or moved is not counted._", "",
         "| Metric | Count | Basis |", "|---|---|---|"]
    ms = act["metrics"]

    def cell(name):
        m = ms.get(name)
        if not m or m["status"] not in ("ok", "incomplete"):
            return "**not collected**" + (f" ({md(m['why'], 120)})" if m and m.get("why") else "")
        return str(len(m["keys"])) if m["status"] == "ok" else f"≥{len(m['keys'])} (incomplete: {md(m['why'], 160)})"

    rows = (("PRs opened", "prs_opened", "created_at in window"),
            ("PRs merged", "prs_merged", "closed in window AND merged_at in window (a closed PR without merged_at is not a merge)"),
            ("PRs closed without merge", "prs_closed_unmerged", "closed_at in window, merged_at empty"),
            ("Issues opened", "issues_opened", "created_at in window"),
            ("Issues closed", "issues_closed", "closed_at in window (completed vs. not planned is not distinguished)"))
    for label, name, basis in rows:
        L.append(f"| {label} | {cell(name)} | {basis} |")
    own = {n: r for n, r in snap["repos"].items() if not r["fork"]}
    inwin = sorted(n for n, r in own.items() if _in_window(r["pushed_at"], s, e))
    later = sorted(n for n, r in own.items() if r["pushed_at"] and parse_ts(r["pushed_at"]) >= e)
    L += [f"| Repositories whose LATEST push time is in the window | {len(inwin)} | repository count, NOT a push count or commit count; a later push overwrites the time, so this is a lower bound |",
          f"| Repositories pushed after the window (activity inside the window unknown) | {len(later)} | not counted as active or inactive |",
          "| Push events | **not collected** | needs a source that can be counted exactly (design only: docs/github-monitoring.md §13) |",
          "| Commits | **not collected** | design only (docs/github-monitoring.md §13) |", ""]
    for label, name in (("PRs opened", "prs_opened"), ("PRs merged", "prs_merged"), ("PRs closed without merge", "prs_closed_unmerged"),
                        ("Issues opened", "issues_opened"), ("Issues closed", "issues_closed")):
        m = ms.get(name)
        if m and m["status"] in ("ok", "incomplete") and m["keys"]:
            L.append(f"- {label}: {_names(m['keys'])}")
    if inwin:
        L.append(f"- Repositories whose latest push is in the window: {_names(inwin)}")
    if act.get("ignored_outside_own_nonfork"):
        L.append(f"- _{act['ignored_outside_own_nonfork']} search result(s) in forks / unknown repositories were ignored._")
    return L


def build_report(cfg, snap, alerts, d, state, now):
    owner, repos = snap["owner"], snap["repos"]
    own = {n: r for n, r in repos.items() if not r["fork"]}
    forks = len(repos) - len(own)
    today = now.astimezone(JST)
    crit = [a for a in alerts if a["severity"] == "critical"]
    issues_own = {k: v for k, v in snap["issues"].items() if v["repo"] in own}
    prs_own = {k: v for k, v in snap["prs"].items() if v["repo"] in own}
    stale_items = [a for a in alerts if a["key"].startswith("stale:") and a["repo"] in own]
    got_issues, got_prs = was_collected(snap, "issues"), was_collected(snap, "prs")
    n_a = "not collected"
    active_set = set(snap.get("active_repos", []))     # repositories eligible for per-repository checks (archived / forks / over the cap are not)
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
          f"| Open issues (own repos) | {len(issues_own) if got_issues else n_a} |", f"| Open PRs (own repos) | {len(prs_own) if got_prs else n_a} |",
          f"| Critical alerts | {len(crit)} |",
          f"| Stale issues/PRs (≥{cfg.stale_issue_days}d) | {len(stale_items) if (got_issues and got_prs) else str(len(stale_items)) + ' (incomplete: open issues/PRs not fully collected)'} |", ""]
    if crit:
        L += ["### ⚠️ Critical alerts / 重要な警告", ""] + [f"- **{md(a['text'], 200)}**" + (f" — {a['url']}" if a["url"] else "") for a in crit] + [""]
    L += coverage_lines(cfg, snap)

    L += [f"## 1. Recently updated repositories / 最近更新（{cfg.recent_days}日以内）", ""]
    recent = sorted((n for n, r in own.items() if (age_days(r["pushed_at"], now) or 1e9) <= cfg.recent_days), key=lambda n: own[n]["pushed_at"], reverse=True)
    if recent:
        L += ["| Repository | Visibility | Last push (JST) | Last commit | Open issues |", "|---|---|---|---|---|"]
        for n in recent:
            c = snap["commits"].get(n)
            L.append(f"| {md(n)} | {'private' if own[n]['private'] else 'public'} | {jst(own[n]['pushed_at'])} | {md(c['sha'] + ' ' + c['message']) if c else (n_a if n in active_set else 'not checked (outside active set)')} | {own[n]['open_issues_count']} |")
    else:
        L.append("_None._")

    L += ["", f"## 2. New / updated issues / 新規・更新Issue（直近2日）", ""]
    upd = sorted((v for v in issues_own.values() if (age_days(v["updated_at"], now) or 1e9) <= 2), key=lambda v: v["updated_at"], reverse=True)
    L += [f"- {'🆕 ' if (age_days(v['created_at'], now) or 1e9) <= 2 else ''}[{md(v['repo'])}#{v['number']}]({v['url']}) {md(v['title'])} _(updated {jst(v['updated_at'])})_" for v in upd] or (["_None._"] if got_issues else ["_Not collected in this run (see Coverage)._"])

    L += ["", "## 3. Open pull requests / 未対応PR", ""]
    if not got_prs:
        L.append("_Not collected in this run (see Coverage)._")
    elif prs_own:
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
        total = (snap.get("coverage_detail") or {}).get("active_total", len(snap["actions"]))
        L.append(f"_No failures among {len(snap['actions'])} of {total} active repositories checked" + ("" if len(snap["actions"]) >= total else " (the others were not checked; see Coverage)") + "._")

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
    L += [f"- Issues/PRs not updated for ≥{cfg.stale_issue_days} days: " + ("; ".join(f"[{md(a['text'], 70)}]({a['url']})" for a in stale_items[:15]) if stale_items else "none")
          + ("" if (got_issues and got_prs) else " (incomplete: open issues/PRs not fully collected)")]

    L += ["", "## 7. Changes since the previous snapshot / 前回収集との差分", ""]
    if not d:
        L.append("_First snapshot — nothing to compare yet._")
    else:
        L.append(f"_Compared with the previous snapshot of {jst(d['prev_at'])} JST (snapshot-to-snapshot, not a calendar day)._")
        bucket_of = {"new_issues": "issues", "closed_issues": "issues", "new_prs": "prs", "closed_prs": "prs"}
        for label, key in (("New repositories", "new_repos"),
                           ("Repositories whose last-push time changed (repository names only; NOT a count of pushes or commits)", "pushed"),
                           ("Newly seen open issues", "new_issues"), ("Issues no longer open (closed; reason not available)", "closed_issues"),
                           ("Newly seen open PRs", "new_prs"), ("PRs no longer open (closed OR merged; not distinguished)", "closed_prs"),
                           ("New Actions failures", "new_failures")):
            if d[key] is None:
                L.append(f"- {label}: **not compared** (open {bucket_of[key]} were not collected in this or the previous snapshot)")
                continue
            L.append(f"- {label}: " + (", ".join(md(x) for x in d[key][:20]) + (f" … +{len(d[key]) - 20}" if len(d[key]) > 20 else "") if d[key] else "none"))
        L.append("- _Only currently open issues/PRs are collected: an item opened and closed between two snapshots is never seen, and " + (
            "this section is not a daily count (section 8 gives previous-JST-day counts; push events and commits are not collected)._" if snap.get("activity")
            else "this report does not give daily push or merge counts._"))
    L += activity_lines(cfg, snap)
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
                "notes": snap["notes"] + ["kept today's earlier, fuller report (this run was partial)"], "kuma_pushed": pushed,
                    "collected": same_day.get("collected"), "coverage_detail": same_day.get("coverage_detail"), "activity": activity_summary(same_day)}

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
            "critical_alerts": [a["text"] for a in crit][:10], "notes": snap["notes"], "kuma_pushed": pushed,
            "collected": snap["collected"], "coverage_detail": snap["coverage_detail"], "activity": activity_summary(snap)}
