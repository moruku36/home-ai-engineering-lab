import copy
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).parents[1] / 'roles/n8n_service/files/prepare_n8n_compose.py'
spec = importlib.util.spec_from_file_location('prepare_n8n', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CONFIG = {'name': 'n8n', 'services': {
    'n8n': {'container_name': 'n8n', 'image': 'old',
            'volumes': [{'type': 'volume', 'source': 'n8n-data', 'target': '/home/node/.n8n'}],
            'ports': [{'host_ip': '127.0.0.1', 'published': '5678', 'target': 5678}],
            'networks': {'internal': {}, 'monitor': {}, 'mcp': {}},
            'environment': {'SECRET': 'synthetic-secret'}},
    'python-jobs': {'image': 'fixed'}},
    'volumes': {'n8n-data': {'name': 'n8n_n8n-data'}},
    'networks': {'internal': {'name': 'n8n_internal'}, 'monitor': {'name': 'monitor-net'},
                 'mcp': {'name': 'mcp-net'}}}
CONTAINER = {'Mounts': [{'Type': 'volume', 'Name': 'n8n_n8n-data', 'Destination': '/home/node/.n8n', 'RW': True}],
             'NetworkSettings': {'Ports': {'5678/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '5678'}]},
                                 'Networks': {'n8n_internal': {}, 'monitor-net': {}, 'mcp-net': {}}}}


class PrepareTest(unittest.TestCase):
    def test_matching_runtime(self):
        module.compare_runtime(CONFIG, CONTAINER)

    def test_reject_runtime_volume_port_network(self):
        for kind in ('volume', 'port', 'network'):
            current = copy.deepcopy(CONTAINER)
            if kind == 'volume':
                current['Mounts'][0]['Name'] = 'different'
            elif kind == 'port':
                current['NetworkSettings']['Ports']['5678/tcp'][0]['HostIp'] = '0.0.0.0'
            else:
                del current['NetworkSettings']['Networks']['mcp-net']
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.compare_runtime(CONFIG, current)

    def test_image_only_and_reject_other_changes(self):
        revised = copy.deepcopy(CONFIG)
        revised['services']['n8n']['image'] = module.IMAGE
        module.image_only(CONFIG, revised)
        for kind in ('network', 'other', 'environment'):
            altered = copy.deepcopy(revised)
            if kind == 'network':
                altered['services']['n8n']['networks'] = {}
            elif kind == 'other':
                altered['services']['python-jobs']['image'] = 'different'
            else:
                altered['services']['n8n']['environment']['SECRET'] = 'changed'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.image_only(CONFIG, altered)

    def test_effective_hash_detects_secret_change_without_returning_it(self):
        revised = copy.deepcopy(CONFIG)
        revised['services']['n8n']['environment']['SECRET'] = 'different'
        self.assertNotEqual(module.effective_hash(CONFIG), module.effective_hash(revised))
        self.assertNotIn('synthetic-secret', module.effective_hash(CONFIG))


if __name__ == '__main__':
    unittest.main()
