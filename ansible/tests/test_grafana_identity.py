import copy
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).parents[1] / 'roles/grafana_service/files/inspect_grafana_scope.py'
spec = importlib.util.spec_from_file_location('scope', source)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)
ROOT = '/example/observability'
LABELS = {'com.docker.compose.project': 'observability',
          'com.docker.compose.service': 'grafana',
          'com.docker.compose.project.working_dir': ROOT,
          'com.docker.compose.project.config_files': ROOT + '/compose.yaml'}


class IdentityTest(unittest.TestCase):
    def test_known_sets_and_order(self):
        for files in ('compose.yaml',
                      '.home-lab-ansible-prometheus.yml,compose.yaml',
                      'compose.yaml,.home-lab-ansible-grafana.yml',
                      '.home-lab-ansible-grafana.yml,compose.yaml,.home-lab-ansible-prometheus.yml'):
            labels = copy.copy(LABELS)
            labels['com.docker.compose.project.config_files'] = files
            with self.subTest(files=files):
                self.assertTrue(scope.classify(labels, 'running', ROOT)[1])

    def test_reject_unknown_missing_duplicate_and_state(self):
        for files, state in [('compose.yaml,other.yml', 'running'), ('other.yml', 'running'),
                             ('compose.yaml,./compose.yaml', 'running'), ('compose.yaml', 'exited')]:
            labels = copy.copy(LABELS)
            labels['com.docker.compose.project.config_files'] = files
            with self.subTest(files=files), self.assertRaises(AssertionError):
                assert scope.classify(labels, state, ROOT)[1]


if __name__ == '__main__':
    unittest.main()
