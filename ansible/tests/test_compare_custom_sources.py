import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

path = Path(__file__).parents[1] / 'diagnostics/compare_custom_sources.py'
spec = importlib.util.spec_from_file_location('custom_compare', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CompareTest(unittest.TestCase):
    def test_runtime_digest_only(self):
        for output, expected in ((b'a' * 40 + b'\n', 'a' * 40), (b'secret data\n', None)):
            with self.subTest(output=output), patch.object(module.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=output)):
                self.assertEqual(module.runtime_hash('python-jobs', '/app/server.py'), expected)

    def test_local_regular_file_and_relation(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            source.write_text('synthetic source')
            digest = module.local_hash(source)
            self.assertEqual(module.relation(digest, digest), 'matches')
            self.assertEqual(module.relation(digest, '0' * 40), 'differs')
            self.assertEqual(module.relation(None, digest), 'unavailable')


if __name__ == '__main__':
    unittest.main()
