"""Synthetic snapshots only: no API, Docker, private data or service access."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("github_snapshot_metrics", ROOT / "scripts/github_snapshot_metrics.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
NOW = datetime(2026, 10, 24, 0, tzinfo=timezone.utc).timestamp()


def snapshot():
    return {"schema": 1, "generated_at": "2026-10-24T00:00:00Z", "partial": False,
            "repos": {"synthetic-private-repo": {"fork": False, "private": True, "pushed_at": "2026-10-23T01:00:00Z"}},
            "issues": {}, "prs": {}, "collected": {"issues": True, "prs": True},
            "coverage_detail": {"searches": {"issues": "ok", "prs": "ok"}},
            "api_calls": 7, "alerts": [],
            "activity": {"window": {"start": "2026-10-22T15:00:00Z", "end": "2026-10-23T15:00:00Z"},
                         "collected_at": "2026-10-24T00:00:00Z",
                         "metrics": {name: {"status": "ok", "keys": []} for name in metrics.ACTIVITY}}}


def samples(text):
    return dict(line.rsplit(" ", 1) for line in text.splitlines() if line and not line.startswith("#"))


class MetricsTests(unittest.TestCase):
    def test_measured_zero_is_present_and_no_source_strings_leak(self):
        data = snapshot()
        data["notes"] = ["synthetic secret-like text that must not be exported"]
        data["activity"]["metrics"]["prs_opened"]["keys"] = ["synthetic-private-repo#1"]
        text, state = metrics.render(data, NOW)
        parsed = samples(text)
        self.assertEqual(state, 1)
        self.assertEqual(parsed['lab_github_value{metric="open_issues"}'], "0")
        self.assertEqual(parsed['lab_github_metric_state{metric="open_issues"}'], "1")
        self.assertNotIn("synthetic-private-repo", text)
        self.assertNotIn(data["notes"][0], text)
        self.assertNotIn("_total", text)
        self.assertEqual(parsed["lab_github_collector_attempt_known"], "0")

    def test_missing_old_schema_flags_are_uncollected_not_zero(self):
        data = snapshot()
        data.pop("collected")
        data.pop("coverage_detail")
        data.pop("activity")
        parsed = samples(metrics.render(data, NOW)[0])
        for metric in ("open_issues", "open_prs", "prs_merged"):
            self.assertEqual(parsed[f'lab_github_metric_state{{metric="{metric}"}}'], "0")
            self.assertNotIn(f'lab_github_value{{metric="{metric}"}}', parsed)

    def test_partial_count_is_lower_bound_even_if_flag_conflicts(self):
        data = snapshot()
        data["coverage_detail"]["searches"]["issues"] = "incomplete"
        data["activity"]["metrics"]["prs_merged"] = {"status": "incomplete", "keys": []}
        parsed = samples(metrics.render(data, NOW)[0])
        for name in ("open_issues", "prs_merged", "latest_push_repositories"):
            self.assertEqual(parsed[f'lab_github_metric_state{{metric="{name}"}}'], "2")
            self.assertIn(f'lab_github_value{{metric="{name}"}}', parsed)

    def test_recorded_failure_has_no_zero_value(self):
        data = snapshot()
        data["collected"]["issues"] = False
        data["coverage_detail"]["searches"]["issues"] = "rate_limit"
        data["activity"]["metrics"]["prs_merged"] = {"status": "api_error", "keys": []}
        parsed = samples(metrics.render(data, NOW)[0])
        for name in ("open_issues", "prs_merged"):
            self.assertEqual(parsed[f'lab_github_metric_state{{metric="{name}"}}'], "4")
            self.assertNotIn(f'lab_github_value{{metric="{name}"}}', parsed)

    def test_stale_values_removed_and_timestamp_preserved(self):
        text, state = metrics.render(snapshot(), NOW + metrics.MAX_AGE + 1)
        self.assertEqual(state, 3)
        self.assertNotIn("lab_github_value{", text)
        self.assertIn('lab_github_metric_state{metric="repos"} 3', text)
        self.assertIn(f"lab_github_snapshot_timestamp_seconds {NOW}", text)

    def test_invalid_schema_timestamp_and_window_fail_closed(self):
        for mutation in ({"schema": 9}, {"schema": True}, {"generated_at": "2026-10-24T00:00:00"},
                         {"generated_at": "2026-10-25T00:00:00Z"}, {"api_calls": -1},
                         {"activity": {"window": {}, "metrics": {}}}):
            data = snapshot()
            data.update(mutation)
            with self.subTest(mutation=mutation):
                text, state = metrics.render(data, NOW)
                self.assertEqual(state, 4)
                self.assertNotIn("lab_github_value{", text)

    def test_repeated_same_day_does_not_add_and_deduplicates_keys(self):
        data = snapshot()
        data["activity"]["metrics"]["prs_merged"]["keys"] = ["synthetic#1", "synthetic#1", "synthetic#2"]
        first, _ = metrics.render(data, NOW)
        second, _ = metrics.render(copy.deepcopy(data), NOW)
        self.assertEqual(first, second)
        self.assertIn('lab_github_value{metric="prs_merged"} 2', second)
        self.assertIn("# TYPE lab_github_value gauge", second)

    def test_missing_failed_and_oversized_input(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "input.json"
            self.assertEqual(metrics.load_snapshot(target), (None, "missing"))
            for raw in (b"not-json", b"\xff", b"[" * 2000 + b"]" * 2000,
                        b" " * (metrics.MAX_BYTES + 1)):
                target.write_bytes(raw)
                self.assertEqual(metrics.load_snapshot(target), (None, "failed"))
            for status, expected in (("missing", 0), ("failed", 4)):
                text, state = metrics.render(None, NOW, status)
                self.assertEqual(state, expected)
                self.assertNotIn("lab_github_value{", text)

    def test_depth_limit_is_independent_of_python_recursion_limit(self):
        import sys
        previous = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(10000)
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                target = Path(directory) / "input.json"
                # Root object counts as one container.
                for depth, expected in ((metrics.MAX_JSON_DEPTH, "ok"),
                                        (metrics.MAX_JSON_DEPTH + 1, "failed"), (2000, "failed")):
                    target.write_bytes(b'{"schema":1,"extra":' + b"[" * (depth - 1) +
                                       b"0" + b"]" * (depth - 1) + b"}")
                    value, status = metrics.load_snapshot(target)
                    self.assertEqual(status, expected)
                    if status == "ok":
                        self.assertIsInstance(value, dict)
                    else:
                        self.assertIsNone(value)
        finally:
            sys.setrecursionlimit(previous)

    def test_brackets_and_escaped_quotes_inside_strings_are_not_depth(self):
        data = snapshot()
        data["notes"] = ["[" * 1000 + '"' + "\\" * 5 + '"]}' + "]" * 1000]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "input.json"
            target.write_text(json.dumps(data), encoding="utf-8")
            value, state = metrics.load_snapshot(target)
        self.assertEqual(state, "ok")
        self.assertEqual(value["schema"], 1)
        self.assertEqual(metrics.render(value, NOW)[1], 1)

    def test_non_object_roots_and_non_utf8_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "input.json"
            for raw in (b"[]", b"1", b"null", b'"text"', json.dumps(snapshot()).encode("utf-16")):
                target.write_bytes(raw)
                value, state = metrics.load_snapshot(target)
                self.assertIsNone(value)
                self.assertEqual(state, "failed")

    def test_cli_replaces_previous_output_when_source_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            source = Path(directory) / "snapshot.json"
            output = Path(directory) / "github.prom"
            source.write_text(json.dumps(snapshot()), encoding="utf-8")
            with patch.object(metrics.time, "time", return_value=NOW):
                self.assertEqual(metrics.main(["--input", str(source), "--output", str(output)]), 0)
                self.assertIn("lab_github_value{", output.read_text())
                source.write_text("broken", encoding="utf-8")
                self.assertEqual(metrics.main(["--input", str(source), "--output", str(output)]), 3)
            self.assertNotIn("lab_github_value{", output.read_text())
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["github.prom", "snapshot.json"])

    def test_output_cannot_replace_input_or_write_a_non_metrics_file(self):
        with patch.object(metrics, "load_snapshot") as read, patch.object(metrics.sys, "stderr"):
            for source, output in (("synthetic.prom", "synthetic.prom"), ("input.json", "output.json")):
                with self.subTest(source=source, output=output), self.assertRaises(SystemExit):
                    metrics.main(["--input", source, "--output", output])
        read.assert_not_called()

    def test_output_failure_is_reported_without_input_details(self):
        with patch.object(metrics, "load_snapshot", return_value=(snapshot(), "ok")), \
             patch.object(metrics, "atomic_write", side_effect=OSError("synthetic-sensitive-detail")), \
             patch.object(metrics.sys, "stderr") as stderr:
            self.assertEqual(metrics.main(["--input", "synthetic", "--output", "synthetic.prom"]), 3)
        self.assertNotIn("synthetic-sensitive-detail", str(stderr.write.call_args_list))


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = json.loads((ROOT / "stacks/observability/grafana/provisioning/dashboards/json/github-daily.json").read_text(encoding="utf-8"))

    def test_queries_are_gauges_and_require_converter_freshness(self):
        for panel in self.dashboard["panels"]:
            for target in panel.get("targets", []):
                query = target["expr"]
                for forbidden in ("rate(", "increase(", "sum_over_time("):
                    self.assertNotIn(forbidden, query)
                self.assertIn('job="node"', query)
                self.assertIn("lab_github_export_timestamp_seconds", query)
                self.assertIn("< 120", query)
                if "lab_github_value{" in query:
                    self.assertIn("lab_github_snapshot_timestamp_seconds", query)
                    self.assertIn(str(metrics.MAX_AGE), query)
                    self.assertIn("lab_github_export_state", query)

    def test_fixed_metric_selectors_and_state_mappings(self):
        import re
        for panel in self.dashboard["panels"]:
            for target in panel.get("targets", []):
                for selector in re.findall(r'metric=~"([^"]+)"', target["expr"]):
                    self.assertLessEqual(set(selector.split("|")), set(metrics.METRICS))
        state = next(p for p in self.dashboard["panels"] if p["id"] == 3)
        self.assertEqual(set(state["fieldConfig"]["defaults"]["mappings"][0]["options"]), set("01234"))
        self.assertIn("未取得", state["fieldConfig"]["defaults"]["noValue"])

    def test_separate_uid_and_disclaimer(self):
        self.assertEqual(self.dashboard["uid"], "home-github-daily")
        notes = next(p for p in self.dashboard["panels"] if p["type"] == "text")["options"]["content"]
        self.assertIn("収集時点", notes)
        self.assertIn("直近ジョブの失敗は検出できません", notes)
        self.assertIn("push回数・コミット数は未収集", notes)


if __name__ == "__main__":
    unittest.main()
