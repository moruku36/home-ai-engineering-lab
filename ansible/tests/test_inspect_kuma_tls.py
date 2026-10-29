import contextlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

source = Path(__file__).parents[1] / 'roles/kuma_service/files/inspect_kuma_tls.py'
spec = importlib.util.spec_from_file_location('kuma_tls', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KumaTLSTest(unittest.TestCase):
    def test_counts_only(self):
        result = SimpleNamespace(returncode=0, stdout='sqlite_module=missing\nembedded_mariadb_socket=present\ntcp_monitors=2 tcp_tls_candidates=1\n')
        output = io.StringIO()
        with patch.object(module.subprocess, 'run', return_value=result), contextlib.redirect_stdout(output):
            module.main()
        self.assertIn('tcp_tls_candidates=1', output.getvalue())

    def test_unexpected_output_suppressed(self):
        result = SimpleNamespace(returncode=0, stdout='sqlite_module=missing\nembedded_mariadb_socket=present\nsecret-monitor-name\n')
        output = io.StringIO()
        with patch.object(module.subprocess, 'run', return_value=result), contextlib.redirect_stdout(output):
            module.main()
        self.assertEqual(output.getvalue(), 'DIAGNOSTIC_UNAVAILABLE\n')
        self.assertNotIn('secret-monitor-name', output.getvalue())


if __name__ == '__main__':
    unittest.main()
