import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

source = Path(__file__).parents[1] / 'roles/n8n_service/files/inspect_n8n_inputs.py'
spec = importlib.util.spec_from_file_location('n8n_inputs', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InputTest(unittest.TestCase):
    def test_metadata_only(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'compose.yaml'
            file.write_text('services:\n  n8n:\n    environment:\n      SECRET: not_for_output\n')
            labels = {'com.docker.compose.project': 'n8n', 'com.docker.compose.service': 'n8n',
                      'com.docker.compose.project.working_dir': temp,
                      'com.docker.compose.project.config_files': str(file)}
            mounts = [{'Type': 'volume', 'Name': 'n8n_n8n-data',
                       'Destination': '/home/node/.n8n', 'RW': True}]
            ports = {'5678/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '5678'}]}
            out = io.StringIO()
            with patch.object(sys, 'argv', ['test', temp]), patch.object(module, 'inspect', side_effect=[labels, 'running', mounts, ports]), contextlib.redirect_stdout(out):
                module.main()
            self.assertIn('expected_volume=true', out.getvalue())
            self.assertIn('n8n_fields=environment', out.getvalue())
            self.assertNotIn('not_for_output', out.getvalue())
            self.assertNotIn(temp, out.getvalue())


if __name__ == '__main__':
    unittest.main()
