import copy
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).parents[1] / 'roles/compose_service/files/compare_runtime.py'
spec = importlib.util.spec_from_file_location('compare_runtime', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ROOT = '/example/observability'
CONFIG = {
    'name': 'observability',
    'volumes': {'prometheus-data': {'name': 'observability_prometheus-data'}},
    'services': {'prometheus': {'container_name': 'prometheus', 'volumes': [
        {'type': 'volume', 'source': 'prometheus-data', 'target': '/prometheus'},
        {'type': 'bind', 'source': ROOT + '/prometheus/prometheus.yml',
         'target': '/etc/prometheus/prometheus.yml', 'read_only': True},
    ], 'ports': [{'host_ip': '127.0.0.1', 'published': '9090', 'target': 9090, 'protocol': 'tcp'}]}},
}
CONTAINER = {'Mounts': [
    {'Type': 'volume', 'Name': 'observability_prometheus-data', 'Destination': '/prometheus', 'RW': True},
    {'Type': 'bind', 'Source': ROOT + '/prometheus/prometheus.yml',
     'Destination': '/etc/prometheus/prometheus.yml', 'RW': False},
], 'NetworkSettings': {'Ports': {'9090/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '9090'}]}}}


class CompareTest(unittest.TestCase):
    def test_match(self):
        module.compare(CONFIG, CONTAINER, ROOT)

    def test_reject_runtime_volume_port_and_mode_changes(self):
        for mutation in ('volume', 'port', 'mode'):
            container = copy.deepcopy(CONTAINER)
            if mutation == 'volume':
                container['Mounts'][0]['Name'] = 'other'
            elif mutation == 'port':
                container['NetworkSettings']['Ports']['9090/tcp'][0]['HostIp'] = '0.0.0.0'
            else:
                container['Mounts'][1]['RW'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.compare(CONFIG, container, ROOT)

    def test_reject_compose_changes(self):
        config = copy.deepcopy(CONFIG)
        config['services']['prometheus']['ports'][0]['published'] = '9091'
        with self.assertRaises(ValueError):
            module.compare(config, CONTAINER, ROOT)


if __name__ == '__main__':
    unittest.main()
