import copy
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

source = Path(__file__).parents[1] / 'roles/grafana_service/files/prepare_grafana_compose.py'
spec = importlib.util.spec_from_file_location('prepare', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreserveTest(unittest.TestCase):
    def setUp(self):
        self.base = {'services': {'grafana': {'image': 'old', 'networks': ['monitor']},
                                  'other': {'image': 'fixed'}}, 'networks': {'monitor': {}}}

    def test_only_image_change(self):
        new = copy.deepcopy(self.base)
        new['services']['grafana']['image'] = module.IMAGE
        module.validate_image_only(self.base, new)
        self.assertEqual(self.base['services']['grafana']['image'], 'old')

    def test_reject_network_and_other_service_changes(self):
        for kind in ('network', 'other'):
            new = copy.deepcopy(self.base)
            new['services']['grafana']['image'] = module.IMAGE
            if kind == 'network':
                new['services']['grafana']['networks'] = ['different']
            else:
                new['services']['other']['image'] = 'different'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                module.validate_image_only(self.base, new)

    def test_identity_preserves_file_order_and_requires_external_hash(self):
        root = '/example/observability'
        base, external = root + '/compose.yaml', '/tmp/compose.override.json'
        for files in ([base, external], [external, base]):
            container = {'Config': {'Labels': {
                'com.docker.compose.project': 'observability',
                'com.docker.compose.service': 'grafana',
                'com.docker.compose.project.working_dir': root,
                'com.docker.compose.project.config_files': ','.join(files)}},
                'State': {'Status': 'running'}}
            def digest(path):
                return module.EXTERNAL_SHA if path == external else 'base-hash'
            with self.subTest(files=files), patch.object(module, 'run_json', return_value=[container]), \
                 patch.object(module.os, 'lstat', return_value=SimpleNamespace(st_uid=0)), \
                 patch.object(module, 'digest', side_effect=digest):
                self.assertEqual(module.identity(root)[1], files)
            with patch.object(module, 'run_json', return_value=[container]), \
                 patch.object(module.os, 'lstat', return_value=SimpleNamespace(st_uid=0)), \
                 patch.object(module, 'digest', return_value='incorrect'):
                with self.assertRaises(ValueError):
                    module.identity(root)


if __name__ == '__main__':
    unittest.main()
