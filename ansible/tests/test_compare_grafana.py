import copy
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).parents[1] / 'roles/grafana_service/files/compare_grafana.py'
spec = importlib.util.spec_from_file_location('compare_grafana', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROOT = '/example/observability'
CONFIG = {'name': 'observability', 'volumes': {'grafana-data': {'name': 'observability_grafana-data'}},
          'services': {'grafana': {'container_name': 'grafana', 'volumes': [
              {'type': 'volume', 'source': 'grafana-data', 'target': '/var/lib/grafana'},
              {'type': 'bind', 'source': ROOT + '/grafana/provisioning',
               'target': '/etc/grafana/provisioning', 'read_only': True}],
              'ports': [{'host_ip': '127.0.0.1', 'published': '3000', 'target': 3000}]}}}
CONTAINER = {'Mounts': [
    {'Type': 'volume', 'Name': 'observability_grafana-data', 'Destination': '/var/lib/grafana', 'RW': True},
    {'Type': 'bind', 'Source': ROOT + '/grafana/provisioning',
     'Destination': '/etc/grafana/provisioning', 'RW': False}],
    'NetworkSettings': {'Ports': {'3000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '3000'}]}}}


class GrafanaScopeTest(unittest.TestCase):
    def test_match(self):
        module.compare(CONFIG, CONTAINER, ROOT)

    def test_reject_changes(self):
        for kind in ('volume', 'bind', 'port'):
            runtime = copy.deepcopy(CONTAINER)
            if kind == 'volume':
                runtime['Mounts'][0]['Name'] = 'other'
            elif kind == 'bind':
                runtime['Mounts'][1]['RW'] = True
            else:
                runtime['NetworkSettings']['Ports']['3000/tcp'][0]['HostIp'] = '0.0.0.0'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.compare(CONFIG, runtime, ROOT)


if __name__ == '__main__':
    unittest.main()
