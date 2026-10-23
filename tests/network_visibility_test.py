"""Offline tests only. Synthetic counters, identities, and query logs; no probes."""
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch
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


class CollectionWindowTests(unittest.TestCase):
    def test_default_is_one_snapshot_without_sleep(self):
        with patch.object(metrics.Path, 'read_text', return_value=COUNTERS) as read, \
             patch.object(metrics, 'atomic_write') as write, \
             patch.object(metrics.time, 'time', return_value=1000), \
             patch.object(metrics.time, 'sleep') as sleep:
            metrics.main(['--interface', 'test0', '--output', 'synthetic.prom'])
        read.assert_called_once_with()
        self.assertEqual(write.call_count, 1)
        self.assertIn('snapshot_timestamp_seconds 1000.0', write.call_args.args[1])
        sleep.assert_not_called()

    def test_bounded_window_refreshes_each_timestamp_and_stops(self):
        timestamps = list(range(1000, 1360, 30))
        with patch.object(metrics.Path, 'read_text', return_value=COUNTERS) as read, \
             patch.object(metrics, 'atomic_write') as write, \
             patch.object(metrics.time, 'time', side_effect=timestamps), \
             patch.object(metrics.time, 'sleep') as sleep:
            metrics.main(['--interface', 'test0', '--output', 'synthetic.prom',
                          '--samples', '12', '--interval-seconds', '30'])
        self.assertEqual(read.call_count, 12)
        self.assertEqual(write.call_count, 12)
        self.assertEqual(sleep.call_args_list, [call(30)] * 11)
        for written, timestamp in zip(write.call_args_list, timestamps):
            self.assertIn(f'snapshot_timestamp_seconds {float(timestamp)}', written.args[1])

    def test_invalid_window_never_reads_or_writes(self):
        with patch.object(metrics.Path, 'read_text') as read, \
             patch.object(metrics, 'atomic_write') as write, \
             patch.object(metrics.time, 'sleep') as sleep:
            for samples, interval in [(0, 30), (121, 30), (1, 4), (1, 61)]:
                with self.subTest(samples=samples, interval=interval), self.assertRaises(ValueError):
                    metrics.collect(['test0'], 'synthetic.prom', samples, interval)
        read.assert_not_called()
        write.assert_not_called()
        sleep.assert_not_called()

    def test_failed_read_stops_without_replacing_last_success(self):
        with patch.object(metrics.Path, 'read_text', side_effect=[COUNTERS, OSError('synthetic failure')]) as read, \
             patch.object(metrics, 'atomic_write') as write, \
             patch.object(metrics.time, 'sleep') as sleep:
            with self.assertRaises(OSError):
                metrics.collect(['test0'], 'synthetic.prom', samples=12)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(write.call_count, 1)
        sleep.assert_called_once_with(30)

    def test_failed_write_stops_before_another_sample(self):
        with patch.object(metrics.Path, 'read_text', return_value=COUNTERS) as read, \
             patch.object(metrics, 'atomic_write', side_effect=OSError('synthetic write failure')), \
             patch.object(metrics.time, 'sleep') as sleep:
            with self.assertRaises(OSError):
                metrics.collect(['test0'], 'synthetic.prom', samples=12)
        read.assert_called_once_with()
        sleep.assert_not_called()


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


class DashboardStaticConsistencyTests(unittest.TestCase):
    """Static checks that the Grafana dashboard definition matches what the exporter,
    Prometheus config, provisioning and Compose files actually provide.
    They read repository files only; they prove nothing about a running Grafana."""
    OBS = ROOT / 'stacks' / 'observability'
    DASHBOARD = OBS / 'grafana/provisioning/dashboards/json/network-overview.json'

    def setUp(self):
        self.dashboard = json.loads(self.DASHBOARD.read_text(encoding='utf-8'))
        rendered = metrics.render(COUNTERS, ['test0'], 1000)
        self.emitted = set(re.findall(r'^(lab_host_network_\w+?)(?:\{| )', rendered, re.M))
        self.exprs = [t['expr'] for p in self.dashboard['panels'] for t in p.get('targets', [])]

    def test_dashboard_identity_matches_runbook(self):
        self.assertEqual(self.dashboard['uid'], 'home-network-overview')
        runbook = (ROOT / 'docs/network-visibility-runbook.md').read_text(encoding='utf-8')
        self.assertIn(self.dashboard['uid'], runbook)
        self.assertFalse(self.dashboard.get('editable', False))

    def test_every_host_metric_used_is_emitted_by_the_exporter(self):
        self.assertTrue(self.emitted)
        used = set()
        for expr in self.exprs + [v['query'] for v in self.dashboard['templating']['list']]:
            used |= set(re.findall(r'\blab_host_network_\w+', expr))
        self.assertTrue(used)
        self.assertEqual(used - self.emitted, set(), 'dashboard queries a metric the script never writes')
        for expr in self.exprs:
            for pattern in re.findall(r'__name__=~"([^"]+)"', expr):
                matched = {n for n in self.emitted if re.fullmatch(pattern, n)}
                self.assertEqual(matched, {n for n in self.emitted if 'errors' in n or 'dropped' in n})

    def test_job_label_and_datasource_exist_in_provisioning(self):
        prometheus = (self.OBS / 'prometheus/prometheus.yml').read_text(encoding='utf-8')
        jobs = set(re.findall(r'job_name:\s*(\S+)', prometheus))
        datasource = (self.OBS / 'grafana/provisioning/datasources/prometheus.yaml').read_text(encoding='utf-8')
        names = set(re.findall(r'^\s*-\s*name:\s*(\S+)', datasource, re.M))
        for expr in self.exprs:
            for job in re.findall(r'job="([^"]+)"', expr):
                self.assertIn(job, jobs)
        panels = self.dashboard['panels'] + self.dashboard['templating']['list']
        for item in panels:
            self.assertIn(item['datasource'], names)

    def test_host_nic_panels_are_gated_by_snapshot_freshness(self):
        # Design in the runbook: a stale or missing snapshot must show no data, not an old value.
        for expr in self.exprs:
            if 'lab_host_network_' in expr and 'snapshot_timestamp' not in expr.split('and on')[0]:
                self.assertIn('lab_host_network_snapshot_timestamp_seconds', expr)
                self.assertRegex(expr, r'\band\s+on\s*\(\s*job\s*,\s*instance\s*\)')
                self.assertRegex(expr, r'time\(\)\s*-\s*lab_host_network_snapshot_timestamp_seconds\{[^}]*\}\s*<\s*120\b')

    def test_error_drop_panel_sums_distinct_counter_rates(self):
        # rate() removes the metric name. A multi-name selector would collapse
        # the four metrics onto identical labels and fail before aggregation.
        panel = next(p for p in self.dashboard['panels'] if p['id'] == 7)
        total = panel['targets'][0]['expr'].split(' and on')[0]
        self.assertNotIn('__name__', total)
        rates = re.findall(r'rate\((lab_host_network_\w+)\{([^}]+)\}\[5m\]\)', total)
        expected = {f'lab_host_network_{direction}_{kind}_total'
                    for direction in ('receive', 'transmit')
                    for kind in ('errors', 'dropped')}
        self.assertEqual(len(rates), 4)
        self.assertEqual({metric for metric, _ in rates}, expected)
        for _, selector in rates:
            self.assertIn('job="node"', selector)
            self.assertIn('device=~"$device"', selector)
        self.assertEqual(total.count(' + '), 3)
        self.assertIn('total', panel['title'].lower())
        self.assertIn('total', panel['targets'][0]['legendFormat'].lower())
        self.assertIn('not a unique-packet count', panel['description'])

    def test_compose_mounts_match_provisioning_and_textfile_paths(self):
        compose = (self.OBS / 'compose.yaml').read_text(encoding='utf-8')
        provider = (self.OBS / 'grafana/provisioning/dashboards/network.yaml').read_text(encoding='utf-8')
        self.assertIn('./grafana/provisioning:/etc/grafana/provisioning:ro', compose)
        path = re.search(r'path:\s*(\S+)', provider).group(1)
        self.assertEqual(path, '/etc/grafana/provisioning/dashboards/json')
        relative = Path(path).relative_to('/etc/grafana/provisioning')
        self.assertTrue((self.OBS / 'grafana/provisioning' / relative / self.DASHBOARD.name).is_file())
        self.assertIn('--collector.textfile.directory=/textfile', compose)
        self.assertIn('./data/textfile:/textfile:ro', compose)
        # The exporter publishes no port; only loopback UIs are published.
        published_ports = re.findall(r'-\s*"([^"]+:\d+)"', compose)
        self.assertEqual(set(published_ports), {'127.0.0.1:9090:9090', '127.0.0.1:3000:3000'})
        for published in published_ports:
            self.assertTrue(published.startswith('127.0.0.1:'), published)


if __name__ == '__main__':
    unittest.main()
