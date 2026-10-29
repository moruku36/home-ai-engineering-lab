import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

source = Path(__file__).parents[1] / 'diagnostics/inspect_custom_oss.py'
spec = importlib.util.spec_from_file_location('inspect_custom', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiagnosticTest(unittest.TestCase):
    def test_blob_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'source.py'
            path.write_bytes(b'abc')
            expected = hashlib.sha1(b'blob 3\0abc').hexdigest()
            self.assertEqual(module.blob_match(path, expected), 'matches')
            self.assertEqual(module.blob_match(path, '0' * 40), 'differs')

    def test_mount_source_and_other_labels_not_printed(self):
        fields = ['home-ai-lab/python-jobs:1', 'sha256:' + 'a' * 64, 'running',
                  {'com.docker.compose.project': 'observability',
                   'com.docker.compose.service': 'github-history', 'secret': 'secret-label'},
                  [{'Type': 'bind', 'Source': '/private/sensitive-source', 'Destination': '/unrelated', 'RW': False}]]
        result = SimpleNamespace(returncode=0, stdout=('\n'.join(json.dumps(x) for x in fields)).encode())
        output = io.StringIO()
        with patch.object(module.subprocess, 'run', return_value=result), contextlib.redirect_stdout(output):
            module.inspect('observability-github-history-1')
        self.assertIn('bind_mounts=1', output.getvalue())
        self.assertNotIn('secret-label', output.getvalue())
        self.assertNotIn('/private/sensitive-source', output.getvalue())


if __name__ == '__main__':
    unittest.main()
