#!/usr/bin/env python3
"""Offline checks for the GitHub report freshness monitor."""

import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "github_daily_health.py"
spec = importlib.util.spec_from_file_location("github_daily_health", SCRIPT)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)
UTC = dt.timezone.utc


class ReportHealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def report(self, date: str, modified: dt.datetime):
        path = self.directory / f"github-daily-{date}.md"
        path.write_text("sample", encoding="utf-8")
        os.utime(path, (modified.timestamp(), modified.timestamp()))

    def test_before_grace_checks_previous_day(self):
        now = dt.datetime(2026, 10, 18, 0, 30, tzinfo=UTC)  # 09:30 JST
        self.report("2026-10-17", dt.datetime(2026, 10, 16, 23, tzinfo=UTC))
        code, result = health.check(self.directory, now, grace_hours=3)
        self.assertEqual((code, result["expected_date_jst"]), (0, "2026-10-17"))

    def test_missing_after_grace(self):
        code, result = health.check(self.directory, dt.datetime(2026, 10, 18, 1, tzinfo=UTC))
        self.assertEqual((code, result["status"], result["expected_date_jst"]), (2, "missing", "2026-10-18"))

    def test_early_report_is_stale(self):
        self.report("2026-10-18", dt.datetime(2026, 10, 17, 21, tzinfo=UTC))  # 06:00 JST
        code, result = health.check(self.directory, dt.datetime(2026, 10, 18, 1, tzinfo=UTC))
        self.assertEqual((code, result["status"]), (2, "stale"))

    def test_after_schedule_is_fresh(self):
        self.report("2026-10-18", dt.datetime(2026, 10, 17, 22, 5, tzinfo=UTC))
        code, result = health.check(self.directory, dt.datetime(2026, 10, 18, 1, tzinfo=UTC))
        self.assertEqual((code, result["status"]), (0, "ok"))


if __name__ == "__main__":
    unittest.main()
