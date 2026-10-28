"""Offline-only contracts. No sockets, credentials, filesystem writes or endpoints."""
import copy
from datetime import datetime
import json
import daily_security as core

MAX_BODY = 1024 * 1024
MAX_AGGREGATE = 16384
FIELDS = {'schema','source','model_status','observed_utc','quality','expected',
          'checked','complete_repositories','unavailable','failed','not_attempted',
          'requests','page_limit_reached','request_limit_reached','reasons','counts'}
REASONS = {'credential_unconfigured','targets_unconfigured','request_limit',
           'access_or_feature_unavailable','authentication_failed','rate_limited',
           'page_limit','api_or_schema_failed','unknown_severity',
           'http_403','http_404','http_other','transport_error',
           'schema_or_protocol_error','internal_error'}


class MemoryTransport:
    """Scripted HTTP-shaped responses: (status, bytes, headers, has_next).

    No actual HTTP request is possible. Timeout is injected as an exception.
    Real integration would additionally need fixed-host GET/auth/timeout enforcement.
    """
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, repository, page):
        self.calls.append((repository, page))
        response = self.responses[(repository, page)]
        if isinstance(response, Exception):
            raise response
        status, body, headers, more = response
        if len(body) > MAX_BODY:
            raise ValueError('body_bound')
        if status == 403 and (headers.get('x-ratelimit-remaining') == '0'
                              or 'retry-after' in headers):
            return 429, None, False
        if status != 200:
            return status, None, False
        return status, json.loads(body), more


def validate_aggregate(row, now):
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError('aggregate_fields')
    if row['schema'] != 2 or type(row['schema']) is not int or row['source'] != 'dependabot' or row['model_status'] != 'not_used':
        raise ValueError('aggregate_identity')
    if row['quality'] not in ('complete','partial','unavailable','failed','unconfigured'):
        raise ValueError('aggregate_quality')
    for key in ('expected','checked','complete_repositories','unavailable','failed','not_attempted','requests'):
        if type(row[key]) is not int or not 0 <= row[key] <= 150:
            raise ValueError('aggregate_count')
    if not (row['complete_repositories'] <= row['checked'] <= row['expected']
            and row['not_attempted'] <= row['expected']
            and row['checked'] + row['not_attempted'] <= row['expected']):
        raise ValueError('aggregate_coverage')
    if any(type(row[k]) is not bool for k in ('page_limit_reached','request_limit_reached')):
        raise ValueError('aggregate_flag')
    if (not isinstance(row['reasons'], list) or any(not isinstance(x, str) or x not in REASONS for x in row['reasons'])
            or len(set(row['reasons'])) != len(row['reasons'])):
        raise ValueError('aggregate_reason')
    counts = row['counts']
    if row['checked']:
        if not isinstance(counts, dict) or set(counts) != set(core.SEVERITIES):
            raise ValueError('aggregate_severity')
        if any(type(x) is not int or not 0 <= x <= 15000 for x in counts.values()) or sum(counts.values()) > row['requests'] * 100:
            raise ValueError('aggregate_severity_bound')
    elif counts is not None:
        raise ValueError('aggregate_missing')
    if row['quality'] == 'complete' and (row['expected'] == 0 or row['complete_repositories'] != row['expected']
            or row['not_attempted'] or row['failed'] or row['unavailable'] or row['reasons']
            or row['page_limit_reached'] or row['request_limit_reached'] or counts['unknown']):
        raise ValueError('aggregate_incomplete')
    if row['quality'] == 'unconfigured' and (row['requests'] or row['checked'] or counts is not None):
        raise ValueError('aggregate_unconfigured')
    core.view(row, now)  # validates timestamp timezone and future bound
    return row


def display_preview(existing, row, now):
    """Display-shaped proposal outside live security array. Never upgrades schema 1.

    Existing Dependabot two-repository row, Defender row and all panels are copied
    unchanged. A future explicit display migration must choose the preview field.
    """
    validate_aggregate(row, now)
    current = core.view(row, now)
    counts = current['counts']
    result = copy.deepcopy(existing)
    result['security_preview'] = [{
        'scope': 'dependabot_proposed', 'quality': current['quality'],
        'expected': row['expected'], 'checked': row['checked'],
        'complete_repositories': row['complete_repositories'],
        'critical_high': None if counts is None else counts['critical'] + counts['high'],
        'medium_low': None if counts is None else counts['medium'] + counts['low'],
        'unknown_alerts': None if counts is None else counts['unknown'],
        'observed_utc': row['observed_utc'], 'age_seconds': current['age_seconds'],
        'coverage_scope': 'proposed_explicit_allowlist', 'model_status': 'not_used'}]
    return result


def no_duplicates(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError('duplicate')
        row[key] = value
    return row


class MemoryTransfer:
    """Aggregate validation/idempotency simulation, explicitly NOT authentication.

    No SSH, shared folder, HTTP endpoint or automatic transfer is implemented.
    A repeated source+observed timestamp must have byte-identical aggregate data.
    """
    def __init__(self):
        self.received = {}

    def receive(self, body, now):
        if not isinstance(body, bytes) or len(body) > MAX_AGGREGATE:
            raise ValueError('aggregate_size')
        row = json.loads(body, object_pairs_hook=no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('constant')))
        validate_aggregate(row, now)
        canonical = json.dumps(row, sort_keys=True, allow_nan=False).encode()
        key = (row['source'], row['observed_utc'])
        if key in self.received:
            if self.received[key] != canonical:
                raise ValueError('conflicting_repeat')
            return 'duplicate_unchanged'
        self.received[key] = canonical
        return 'accepted_in_memory'
