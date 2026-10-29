import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

path = Path(__file__).parents[1] / 'roles/grafana_service/files/describe_unknown_compose.py'
spec = importlib.util.spec_from_file_location('describe_unknown', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DescriptionTest(unittest.TestCase):
    def test_values_are_not_printed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'compose.yaml').write_text('services: {}')
            (root / 'other.yml').write_text('services:\n  grafana:\n    environment:\n      PASSWORD: never_print_this_value\n')
            labels = {'com.docker.compose.project': 'observability', 'com.docker.compose.service': 'grafana',
                      'com.docker.compose.project.working_dir': temp,
                      'com.docker.compose.project.config_files': str(root / 'compose.yaml') + ',' + str(root / 'other.yml')}
            fake = types.SimpleNamespace(stdout=json.dumps(labels).encode())
            output = io.StringIO()
            with patch.object(module.subprocess, 'run', return_value=fake), patch.object(sys, 'argv', ['test', temp]), contextlib.redirect_stdout(output):
                module.main()
            text = output.getvalue()
            self.assertIn('basename=other.yml', text)
            self.assertIn('grafana_fields=environment', text)
            self.assertNotIn('never_print_this_value', text)
            self.assertNotIn(temp, text)


if __name__ == '__main__':
    unittest.main()
