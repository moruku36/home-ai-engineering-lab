#!/usr/bin/env python3
"""Read retained snapshots only. No API clients, collectors or scheduler."""
import argparse
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time

import github_snapshot_metrics as snapshot_codec

JST = timezone(timedelta(hours=9))
METRICS = ("prs_opened", "prs_merged", "prs_closed_unmerged", "issues_opened", "issues_closed")
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
MAX_DAYS = 366
MAX_FILES = 366


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def blank_day(day, state=0):
    row = {"day": day.isoformat(), "time": datetime.combine(day, datetime.min.time(), JST).isoformat(),
           "collected_at": None, "quality": state, "coverage": 0}
    for name in METRICS:
        row[name] = None
        row[name + "_quality"] = state
    return row


def parse_day(snapshot, file_day, now):
    if type(snapshot.get("schema")) is not int or snapshot["schema"] != 1:
        raise ValueError("schema")
    generated = snapshot_codec.timestamp(snapshot.get("generated_at"))
    if generated > now + 300 or datetime.fromtimestamp(generated, JST).date() != file_day:
        raise ValueError("date mismatch")
    row = blank_day(file_day - timedelta(days=1))
    row["collected_at"] = utc(generated)
    activity = snapshot.get("activity")
    if activity is None:
        return row  # older snapshots do not establish daily activity
    if not isinstance(activity, dict):
        raise ValueError("activity")
    end = datetime.combine(file_day, datetime.min.time(), JST).timestamp()
    start = end - 86400
    window = activity.get("window") or {}
    if (snapshot_codec.timestamp(window.get("start")), snapshot_codec.timestamp(window.get("end"))) != (start, end):
        raise ValueError("window")
    if abs(snapshot_codec.timestamp(activity.get("collected_at")) - generated) > 300:
        raise ValueError("activity time")
    metrics = activity.get("metrics") or {}
    if not isinstance(metrics, dict):
        raise ValueError("metrics")
    for name in METRICS:
        item = metrics.get(name)
        if item is None:
            continue
        if not isinstance(item, dict):
            row[name + "_quality"] = 4
            continue
        status = item.get("status")
        if status in ("ok", "incomplete"):
            keys = item.get("keys")
            if isinstance(keys, list) and all(isinstance(k, str) for k in keys):
                row[name] = len(set(keys))
                row[name + "_quality"] = 1 if status == "ok" else 2
            else:
                row[name + "_quality"] = 4
        else:
            row[name + "_quality"] = 0 if status in (None, "no_token", "not_collected") else 4
    qualities = [row[n + "_quality"] for n in METRICS]
    row["coverage"] = sum(q in (1, 2) for q in qualities)
    row["quality"] = 4 if 4 in qualities else 1 if all(q == 1 for q in qualities) else 0 if not row["coverage"] else 2
    return row


def security_view(snapshot, now):
    base = {"scope": "github_dependabot", "quality": 0, "risk": 0,
            "critical_high": None, "medium_low": None, "unknown_alerts": None, "checked": 0, "expected": None,
            "observed_utc": None}
    if snapshot is None:
        return [base, {"scope": "sidekick", "quality": 0, "risk": 0, "critical_high": None,
                       "medium_low": None, "checked": None, "expected": None, "observed_utc": None}]
    try:
        generated = snapshot_codec.timestamp(snapshot.get("generated_at"))
        base["observed_utc"] = utc(generated)
        data = snapshot.get("dependabot") or {}
        if not isinstance(data, dict):
            raise ValueError("security")
        entries = [v for v in data.values() if isinstance(v, dict) and v.get("available") is True]
        if now - generated > 26 * 3600:
            base["quality"] = 3
        elif entries:
            totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            unknown_alerts = 0
            for entry in entries:
                severity = entry.get("by_severity")
                if not isinstance(severity, dict) or any(type(n) is not int or n < 0 for n in severity.values()):
                    raise ValueError("severity")
                if type(entry.get("open")) is not int or entry["open"] != sum(severity.values()):
                    raise ValueError("security count mismatch")
                unknown_alerts += sum(v for k, v in severity.items() if k not in totals)
                for name in totals:
                    totals[name] += severity.get(name, 0)
            coverage = ((snapshot.get("coverage_detail") or {}).get("passes") or {}).get("Dependabot alerts") or {}
            expected = coverage.get("total")
            complete = (type(expected) is int and expected > 0 and len(entries) == expected
                        and coverage.get("done") == expected and coverage.get("failed") == 0
                        and coverage.get("stopped") is None and unknown_alerts == 0)
            base.update(quality=1 if complete else 2, checked=len(entries),
                        expected=expected if type(expected) is int and expected >= 0 else None,
                        critical_high=totals["critical"] + totals["high"],
                        medium_low=totals["medium"] + totals["low"], unknown_alerts=unknown_alerts)
            base["risk"] = 3 if base["critical_high"] else 2 if base["medium_low"] else 1 if complete else 0
    except (ValueError, TypeError, AttributeError, OverflowError):
        base.update(quality=4, risk=0, critical_high=None, medium_low=None)
    return [base, {"scope": "sidekick", "quality": 0, "risk": 0, "critical_high": None,
                   "medium_low": None, "checked": None, "expected": None, "observed_utc": None}]


def history(directory, now=None):
    now = time.time() if now is None else now
    rows = {}
    latest_snapshot = None
    invalid = 0
    meta = {"built_utc": utc(now), "retention_default_snapshots": 30, "dated_files": 0,
            "invalid_files": 0, "missing_days": 0, "available_start": None, "available_end": None,
            "latest_snapshot_utc": None, "latest_age_seconds": None, "quality": 0}
    try:
        files = sorted(p for p in Path(directory).iterdir() if DATED.fullmatch(p.name))
        if len(files) > MAX_FILES:
            raise ValueError("file bound")
        for path in files:
            try:
                file_day = date.fromisoformat(path.stem)
            except ValueError:
                invalid += 1
                continue
            target = file_day - timedelta(days=1)
            meta["dated_files"] += 1
            latest_snapshot = None
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("not a regular file")
                snapshot, state = snapshot_codec.load_snapshot(path)
                if state != "ok":
                    raise ValueError("invalid input")
                rows[target] = parse_day(snapshot, file_day, now)
                latest_snapshot = snapshot
            except (ValueError, TypeError, AttributeError, OSError, OverflowError):
                invalid += 1
                rows[target] = blank_day(target, 4)
        if rows:
            first, last = min(rows), max(rows)
            if (last - first).days >= MAX_DAYS:
                raise ValueError("calendar bound")
            meta.update(available_start=first.isoformat(), available_end=last.isoformat())
            day = first
            while day <= last:
                if day not in rows:
                    rows[day] = blank_day(day)
                    meta["missing_days"] += 1
                day += timedelta(days=1)
            final = rows[last]
            quality = final["quality"]
            if final["collected_at"]:
                stamp = snapshot_codec.timestamp(final["collected_at"])
                age = now - stamp
                meta.update(latest_snapshot_utc=utc(stamp), latest_age_seconds=max(0, round(age)))
                if age > 26 * 3600 and quality != 4:
                    quality = 3
            meta["quality"] = quality
        elif invalid:
            meta["quality"] = 4
        if meta["quality"] == 1 and (invalid or meta["missing_days"]):
            meta["quality"] = 2
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError):
        rows.clear()
        latest_snapshot = None
        meta.update(quality=4, available_start=None, available_end=None)
    meta["invalid_files"] = invalid
    return {"schema": 1, "meta": [meta], "days": [rows[d] for d in sorted(rows)],
            "security": security_view(latest_snapshot, now)}


class ReadOnlyAdapter:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.lock = threading.Lock()
        self.at = -float("inf")
        self.cached = None

    def payload(self):
        with self.lock:
            if self.cached is None or time.monotonic() - self.at > 10:
                self.cached = json.dumps(history(self.snapshots),
                                         ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.at = time.monotonic()
            return self.cached


def handler(adapter):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # never log arbitrary request paths or report content

        def do_GET(self):
            if self.path == "/healthz":
                body, status = b'{"ok":true}', 200
            elif self.path == "/history":
                try:
                    body, status = adapter.payload(), 200
                except Exception:
                    body, status = b'{"error":"history unavailable"}', 500
            else:
                body, status = b'{"error":"not found"}', 404
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.send_error(405, "read only")
    return Handler


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots", required=True, type=Path)
    p.add_argument("--serve", action="store_true")
    p.add_argument("--bind", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    p.add_argument("--port", type=int, default=8081)
    args = p.parse_args(argv)
    if args.serve:
        ThreadingHTTPServer((args.bind, args.port), handler(ReadOnlyAdapter(args.snapshots))).serve_forever()
    else:
        print(json.dumps(history(args.snapshots), ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
