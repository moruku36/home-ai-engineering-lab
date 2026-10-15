"""Offline tests only. Synthetic counters, identities, and query logs; no probes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


metrics = module('network_host_metrics')
report = module('network_report')
COUNTERS = 'Inter-| Receive | Transmit\n face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n test0: 100 2 3 4 0 0 0 0 200 5 6 7 0 0 0 0\n other0: 900 0 0 0 0 0 0 0 800 0 0 0 0 0 0 0\n'


class MetricsTests(unittest.TestCase):
    def test_selected_host_values_and_no_unselected_series(self):
        text = metrics.render(COUNTERS, ['test0'], 1000)
        for suffix, value in [('receive_bytes', 100), ('transmit_bytes', 200),
                              ('receive_errors', 3), ('transmit_dropped', 7)]:
            self.assertIn(f'lab_host_network_{suffix}_total{{device="test0"}} {value}', text)
        self.assertNotIn('other0', text)
        self.assertIn('snapshot_timestamp_seconds 1000.0', text)

    def test_missing_selection_or_interface_fails(self):
        for interfaces in ([], ['absent0'], ['test0', 'test0']):
            with self.assertRaises(ValueError):
                metrics.render(COUNTERS, interfaces, 1000)

    def test_invalid_counters_fail(self):
        for raw in ('test0: 1 2', COUNTERS.replace('100 2', '-100 2')):
            with self.assertRaises(ValueError):
                metrics.render(raw, ['test0'], 1000)

    def test_atomic_snapshot_replaces_previous_and_cleans_temp(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / 'host.prom'
            metrics.atomic_write(target, 'first\n')
            metrics.atomic_write(target, 'second\n')
            self.assertEqual(target.read_bytes(), b'second\n')
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['host.prom'])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 15, 13, tzinfo=timezone.utc)
        self.log = json.loads((ROOT/'docs/samples/network-querylog.example.json').read_text())

    def test_allowlist_and_dns_case_aggregation(self):
        self.log['data'][0]['question']['name'] = 'EXAMPLE.COM.'
        summary = report.summarize(self.log, {'192.0.2.10'}, self.now)
        self.assertEqual(summary, {'queries': 2, 'excluded': 1, 'domains': [('example.com', 2)]})

    def test_expired_future_and_timezone(self):
        self.log['data'][0]['time'] = '2026-10-13T00:00:00Z'
        self.log['data'][1]['time'] = '2026-10-16T00:00:00Z'
        self.assertEqual(report.summarize(self.log, {'192.0.2.10'}, self.now)['queries'], 0)
        self.log['data'][0]['time'] = '2026-10-15T12:00:00'
        with self.assertRaises(ValueError):
            report.summarize(self.log, {'192.0.2.10'}, self.now)

    def test_requires_allowlist(self):
        with self.assertRaises(ValueError):
            report.summarize(self.log, set(), self.now)

    def test_html_escaping_and_inventory_consent(self):
        inventory = {'devices': [
            {'label': '<script>alert(1)</script>', 'consent': True},
            {'label': 'private-unapproved-device', 'consent': False}]}
        summary = {'queries': 1, 'excluded': 0, 'domains': [('<img src=x onerror=alert(1)>', 1)]}
        html = report.render(inventory, summary)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img ', html)
        self.assertNotIn('private-unapproved-device', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn("default-src 'none'", html)
        self.assertIn('自動探索', html)

    def test_empty_log_and_limit(self):
        self.assertEqual(report.summarize({'data': []}, {'192.0.2.10'}, self.now)['domains'], [])
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / 'oversized.json'
            path.write_bytes(b' ' * (report.MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                report.load(path)


if __name__ == '__main__':
    unittest.main()
