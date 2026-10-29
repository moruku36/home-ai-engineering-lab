import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).parents[1] / 'roles/grafana_service/files/classify_external_override.py'
spec = importlib.util.spec_from_file_location('external', source)
external = importlib.util.module_from_spec(spec)
spec.loader.exec_module(external)


class ClassificationTest(unittest.TestCase):
    def test_no_values(self):
        flags = external.classify_document({'services': {'grafana': {'environment': {'PASSWORD': 'secret-value'},
                                                                     'volumes': ['private-path']}}})
        self.assertEqual(flags['grafana_fields'], 'volumes,environment')
        self.assertNotIn('secret-value', str(flags))
        self.assertNotIn('private-path', str(flags))

    def test_other_service_and_sections(self):
        flags = external.classify_document({'services': {'other': {}}, 'networks': {}})
        self.assertTrue(flags['other_services'])
        self.assertTrue(flags['non_service_sections'])
        self.assertFalse(flags['grafana_mentioned'])


if __name__ == '__main__':
    unittest.main()
