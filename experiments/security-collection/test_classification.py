import unittest
from datetime import datetime, timezone

import daily_security as core
from mock_integration import validate_aggregate

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


class ClassificationTests(unittest.TestCase):
    def test_categories_and_coverage(self):
        outcomes = [(200, [], False), (403, None, False), (404, None, False),
                    (500, None, False), TimeoutError(), (200, {}, False), RuntimeError()]
        repos = [f'example/r{i}' for i in range(len(outcomes))]
        def transport(repo, page):
            outcome = outcomes[repos.index(repo)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        row = core.collect(repos, transport, NOW)
        validate_aggregate(row, NOW)
        self.assertEqual((row['checked'], row['unavailable'], row['failed'], row['requests']), (1, 2, 4, 7))
        self.assertTrue({'http_403', 'http_404', 'http_other', 'transport_error',
                         'schema_or_protocol_error', 'internal_error'} <= set(row['reasons']))
        self.assertNotIn('example/', str(row))

    def test_rate_limit_stops_without_extra_requests(self):
        row = core.collect(['a/a', 'a/b'], lambda *_: (429, None, False), NOW)
        validate_aggregate(row, NOW)
        self.assertEqual((row['requests'], row['failed'], row['not_attempted']), (1, 1, 1))
        self.assertEqual(row['reasons'], ['rate_limited'])

    def test_existing_reason_remains_accepted(self):
        row = core.collect(['a/a'], lambda *_: (404, None, False), NOW)
        row['reasons'].remove('http_404')
        validate_aggregate(row, NOW)

if __name__ == '__main__':
    unittest.main()
