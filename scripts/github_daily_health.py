#!/usr/bin/env python3
"""Check whether the expected GitHub daily report was written after 07:00 JST.

This is a read-only output check. A fresh report does not prove that n8n's
Schedule Trigger fired: a manual execution can produce the same file.
"""

import argparse
import datetime as dt
import json
from pathlib import Path


JST = dt.timezone(dt.timedelta(hours=9), "JST")
SCHEDULE_HOUR = 7


def check(report_dir: Path, now: dt.datetime, grace_hours: int = 2) -> tuple[int, dict]:
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    local = now.astimezone(JST)
    due_today = local.replace(hour=SCHEDULE_HOUR + grace_hours, minute=0, second=0, microsecond=0)
    expected_day = local.date() if local >= due_today else local.date() - dt.timedelta(days=1)
    scheduled_at = dt.datetime.combine(expected_day, dt.time(SCHEDULE_HOUR), JST)
    report = report_dir / f"github-daily-{expected_day.isoformat()}.md"
    result = {"expected_date_jst": expected_day.isoformat(), "checked_at_jst": local.isoformat(timespec="seconds")}
    try:
        modified = dt.datetime.fromtimestamp(report.stat().st_mtime, JST)
    except FileNotFoundError:
        result.update(status="missing", reason="expected dated report does not exist")
        return 2, result
    except OSError as exc:
        result.update(status="error", reason=type(exc).__name__)
        return 3, result
    if modified < scheduled_at:
        result.update(status="stale", reason="report predates the expected schedule", modified_at_jst=modified.isoformat(timespec="seconds"))
        return 2, result
    result.update(status="ok", modified_at_jst=modified.isoformat(timespec="seconds"))
    return 0, result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--grace-hours", type=int, default=2)
    args = parser.parse_args()
    if not 0 <= args.grace_hours <= 16:
        parser.error("--grace-hours must be between 0 and 16")
    code, result = check(args.reports_dir, dt.datetime.now(dt.timezone.utc), args.grace_hours)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
