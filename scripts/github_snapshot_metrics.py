#!/usr/bin/env python3
"""Export aggregate gauges from an existing snapshot. No API calls or job execution."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

MAX_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 32  # container depth, independent of Python's recursion limit
MAX_AGE = 26 * 3600
JST = timezone(timedelta(hours=9))
STATES = {"uncollected": 0, "ok": 1, "partial": 2, "stale": 3, "failed": 4}
ACTIVITY = ("prs_opened", "prs_merged", "prs_closed_unmerged", "issues_opened", "issues_closed")
METRICS = ("repos", "open_issues", "open_prs", "alerts_critical", "alerts_warn", "api_calls",
           *ACTIVITY, "latest_push_repositories")
# Only these fixed names become label values. No source names/titles/URLs are exported.


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.timestamp()


def number(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid count")
    return value


def render(snapshot, now, source_state="ok", max_age=MAX_AGE):
    """Missing/invalid data never becomes a zero count; status gauges remain visible."""
    values = {}
    states = dict.fromkeys(METRICS, STATES["uncollected"])
    snapshot_time = None
    window = None
    export_state = {"ok": 1, "missing": 0, "failed": 4}[source_state]
    try:
        if source_state != "ok":
            raise ValueError("source unavailable")
        if not isinstance(snapshot, dict) or type(snapshot.get("schema")) is not int or snapshot["schema"] != 1:
            raise ValueError("unknown schema")
        snapshot_time = timestamp(snapshot.get("generated_at"))
        if snapshot_time > now + 300:
            raise ValueError("future snapshot")
        if type(snapshot.get("partial")) is not bool or not isinstance(snapshot.get("repos"), dict):
            raise ValueError("invalid snapshot")
        stale = now - snapshot_time > max_age
        export_state = 3 if stale else 1

        def record(name, value, state=1):
            states[name] = 3 if stale else state
            if not stale and state in (1, 2):
                values[name] = number(value)

        record("repos", len(snapshot["repos"]))
        for bucket, name in (("issues", "open_issues"), ("prs", "open_prs")):
            flag = (snapshot.get("collected") or {}).get(bucket)
            detail = ((snapshot.get("coverage_detail") or {}).get("searches") or {}).get(bucket)
            state = (2 if detail == "incomplete" else
                     4 if detail in ("api_error", "rate_limit", "call_budget") else
                     1 if flag is True else 0)
            if state in (1, 2) and isinstance(snapshot.get(bucket), dict):
                record(name, len(snapshot[bucket]), state)
            elif state in (1, 2):
                states[name] = 4
            else:
                states[name] = state

        if "api_calls" in snapshot:
            record("api_calls", snapshot["api_calls"])
        alerts = snapshot.get("alerts")
        if isinstance(alerts, list):
            if any(not isinstance(a, dict) or a.get("severity") not in ("critical", "warn") for a in alerts):
                raise ValueError("invalid alerts")
            for severity in ("critical", "warn"):
                record("alerts_" + severity, sum(a["severity"] == severity for a in alerts),
                       2 if snapshot["partial"] else 1)

        activity = snapshot.get("activity")
        if isinstance(activity, dict):
            end = datetime.fromtimestamp(snapshot_time, JST).replace(hour=0, minute=0, second=0, microsecond=0)
            expected = ((end - timedelta(days=1)).timestamp(), end.timestamp())
            raw_window = activity.get("window") or {}
            actual = (timestamp(raw_window.get("start")), timestamp(raw_window.get("end")))
            collected_at = timestamp(activity.get("collected_at"))
            if actual != expected or abs(collected_at - snapshot_time) > 300:
                raise ValueError("activity window mismatch")
            window = actual
            for name in ACTIVITY:
                item = (activity.get("metrics") or {}).get(name)
                if not isinstance(item, dict):
                    continue
                status = item.get("status")
                if status in ("ok", "incomplete"):
                    keys = item.get("keys")
                    if not isinstance(keys, list) or any(not isinstance(k, str) for k in keys):
                        states[name] = 4
                    else:
                        record(name, len(set(keys)), 1 if status == "ok" else 2)
                else:
                    states[name] = 0 if status in ("no_token", "not_collected", None) else 4
            # Latest pushed_at can be overwritten by later pushes: always a lower bound.
            count = 0
            for repo in snapshot["repos"].values():
                if not isinstance(repo, dict) or type(repo.get("fork")) is not bool:
                    raise ValueError("invalid repository metadata")
                if not repo["fork"] and repo.get("pushed_at"):
                    count += actual[0] <= timestamp(repo["pushed_at"]) < actual[1]
            record("latest_push_repositories", count, 2)
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        values.clear()
        states = dict.fromkeys(METRICS, 0 if source_state == "missing" else 4)
        export_state = 0 if source_state == "missing" else 4
        snapshot_time = None
        window = None

    lines = [
        "# HELP lab_github_export_state Source state: 0 missing, 1 readable, 3 stale, 4 failed.",
        "# TYPE lab_github_export_state gauge",
        f"lab_github_export_state {export_state}",
        "# HELP lab_github_export_timestamp_seconds Last converter evaluation, not collector attempt.",
        "# TYPE lab_github_export_timestamp_seconds gauge",
        f"lab_github_export_timestamp_seconds {float(now)}",
        "# HELP lab_github_collector_attempt_known Snapshot cannot establish the latest collector attempt.",
        "# TYPE lab_github_collector_attempt_known gauge",
        "lab_github_collector_attempt_known 0",
        "# HELP lab_github_metric_state 0 uncollected, 1 measured, 2 lower bound or partial, 3 stale, 4 failed.",
        "# TYPE lab_github_metric_state gauge",
    ]
    lines += [f'lab_github_metric_state{{metric="{name}"}} {states[name]}' for name in METRICS]
    lines += ["# HELP lab_github_value Latest observed aggregate; daily values are gauges, never cumulative counters.",
              "# TYPE lab_github_value gauge"]
    lines += [f'lab_github_value{{metric="{name}"}} {value}' for name, value in values.items()]
    if snapshot_time is not None:
        lines += ["# TYPE lab_github_snapshot_timestamp_seconds gauge",
                  f"lab_github_snapshot_timestamp_seconds {snapshot_time}"]
    if window is not None:
        for name, value in zip(("start", "end"), window):
            lines += [f"# TYPE lab_github_activity_window_{name}_seconds gauge",
                      f"lab_github_activity_window_{name}_seconds {value}"]
    return "\n".join(lines) + "\n", export_state


def bounded_json_object(raw):
    """UTF-8 JSON object with at most 32 nested containers, before recursive parsing."""
    text = raw.decode("utf-8")
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON nesting limit")
        elif char in "]}":
            depth -= 1
            if depth < 0:
                raise ValueError("invalid JSON nesting")
    if depth or quoted:
        raise ValueError("incomplete JSON")
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("snapshot root must be an object")
    return result


def load_snapshot(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None, "failed"
        return bounded_json_object(raw), "ok"
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None, "failed"


def atomic_write(path, text):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".github-metrics-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.suffix != ".prom" or args.input.resolve() == args.output.resolve():
            parser.error("output must be a distinct .prom path")
    except OSError:
        print("path validation failed", file=sys.stderr)
        return 3
    snapshot, state = load_snapshot(args.input)
    text, export_state = render(snapshot, time.time(), state)
    try:
        atomic_write(args.output, text)
    except OSError:
        print("metric output failed", file=sys.stderr)  # no paths, values or exception text
        return 3
    return 0 if export_state == 1 else 2 if export_state in (0, 3) else 3


if __name__ == "__main__":
    raise SystemExit(main())
