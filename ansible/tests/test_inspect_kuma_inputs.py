import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

source = Path(__file__).parents[1] / 'roles/kuma_service/files/inspect_kuma_inputs.py'
spec = importlib.util.spec_from_file_location('kuma_inputs', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KumaInputTest(unittest.TestCase):
    def test_metadata_and_counts_only(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'compose.yaml'
            file.write_text('services:\n  uptime-kuma:\n    environment:\n      PASSWORD: synthetic-secret\n')
            labels = {'com.docker.compose.project': 'uptime-kuma', 'com.docker.compose.service': 'uptime-kuma',
                      'com.docker.compose.project.working_dir': temp,
                      'com.docker.compose.project.config_files': str(file)}
            mounts = [{'Type': 'volume', 'Name': 'uptime-kuma_uptime-kuma-data',
                       'Destination': '/app/data', 'RW': True}]
            ports = {'3001/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '3001'}]}
            out = io.StringIO()
            result = SimpleNamespace(returncode=0, stdout='tcp_monitors=2 tcp_tls_candidates=1\n')
            with patch.object(module, 'inspect', side_effect=[labels, 'running', mounts, ports]), \
                 patch.object(module.subprocess, 'run', return_value=result), contextlib.redirect_stdout(out):
                module.main()
            self.assertIn('tcp_tls_candidates=1', out.getvalue())
            self.assertIn('expected_volume=true', out.getvalue())
            self.assertNotIn('synthetic-secret', out.getvalue())
            self.assertNotIn(temp, out.getvalue())


if __name__ == '__main__':
    unittest.main()
