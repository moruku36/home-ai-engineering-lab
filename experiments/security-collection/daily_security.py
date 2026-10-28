"""Unregistered candidate: deterministic scheduling and aggregate-only alerts.

No credential discovery, network transport, scheduler registration or live-panel writes.
Transport is supplied by the future approved integration and must enforce a 10s
timeout and 1 MiB response bound. It receives a repo and page, never an arbitrary URL.
"""
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
from pathlib import Path
import re

SEVERITIES = ('critical', 'high', 'medium', 'low', 'unknown')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
MAX_REPOS, MAX_PAGES, MAX_REQUESTS = 150, 3, 150


def utc(value):
    if value.tzinfo is None:
        raise ValueError('timezone_required')
    return value.astimezone(timezone.utc)


def due_slot(now):
    """Most recent existing 22:00 UTC / 07:00 JST trigger; one catch-up only."""
    now = utc(now)
    slot = now.replace(hour=22, minute=0, second=0, microsecond=0)
    if slot > now:
        slot -= timedelta(days=1)
    return slot.strftime('%Y%m%dT220000Z')


def collect(repositories, transport, now, configured=True, max_pages=3, max_requests=150):
    """Collect only explicitly approved targets, no automatic discovery/enrollment.

    transport(repo, page) -> (HTTP status, alert list, has_next).
    Raw alerts are reduced in memory; only aggregate counts leave this function.
    403/404 cannot establish whether alerts are disabled or access is missing.
    """
    if not 1 <= max_pages <= MAX_PAGES or not 1 <= max_requests <= MAX_REQUESTS:
        raise ValueError('budget')
    if (not isinstance(repositories, (list, tuple)) or len(repositories) > MAX_REPOS
            or any(not isinstance(r, str) or not REPO.fullmatch(r) for r in repositories)
            or len(set(repositories)) != len(repositories)):
        raise ValueError('targets')
    row = dict(schema=2, source='dependabot', model_status='not_used',
               observed_utc=utc(now).isoformat(), quality='unconfigured',
               expected=len(repositories), checked=0, complete_repositories=0,
               unavailable=0, failed=0, not_attempted=len(repositories),
               requests=0, page_limit_reached=False, request_limit_reached=False,
               reasons=[], counts=None)
    if not configured or not repositories:
        row['reasons'] = ['credential_unconfigured' if not configured else 'targets_unconfigured']
        return row
    totals = dict.fromkeys(SEVERITIES, 0)
    reasons = set()
    stop = False
    for repo in repositories:
        if stop or row['requests'] >= max_requests:
            row['request_limit_reached'] |= not stop
            if not stop:
                reasons.add('request_limit')
            break
        row['not_attempted'] -= 1
        subtotal = dict.fromkeys(SEVERITIES, 0)
        seen = set()
        accepted = False
        for page in range(1, max_pages + 1):
            if row['requests'] >= max_requests:
                row['request_limit_reached'] = True
                reasons.add('request_limit')
                break
            row['requests'] += 1
            try:
                status, items, more = transport(repo, page)
                if status in (403, 404):
                    if not accepted:
                        row['unavailable'] += 1
                    reasons.add('access_or_feature_unavailable')
                    reasons.add('http_403' if status == 403 else 'http_404')
                    break
                if status in (401, 429):
                    if not accepted:
                        row['failed'] += 1
                    reasons.add('authentication_failed' if status == 401 else 'rate_limited')
                    stop = True
                    break
                if status != 200:
                    if not accepted:
                        row['failed'] += 1
                    reasons.update(('api_or_schema_failed', 'http_other'))
                    break
                if not isinstance(items, list) or len(items) > 100 or type(more) is not bool:
                    raise ValueError('page')
                page_counts = dict.fromkeys(SEVERITIES, 0)
                page_ids = set()
                for item in items:
                    if not isinstance(item, dict) or type(item.get('number')) is not int:
                        raise ValueError('alert')
                    number = item['number']
                    if number <= 0 or number in seen or number in page_ids:
                        raise ValueError('duplicate_or_invalid_alert')
                    page_ids.add(number)
                    vulnerability = item.get('security_vulnerability') or {}
                    if not isinstance(vulnerability, dict):
                        raise ValueError('severity')
                    severity = vulnerability.get('severity')
                    severity = severity.lower() if isinstance(severity, str) else 'unknown'
                    page_counts[severity if severity in SEVERITIES else 'unknown'] += 1
                seen.update(page_ids)
                for key in SEVERITIES:
                    subtotal[key] += page_counts[key]
                accepted = True
                if not more:
                    row['complete_repositories'] += 1
                    break
                if page == max_pages:
                    row['page_limit_reached'] = True
                    reasons.add('page_limit')
            except (OSError, http.client.HTTPException):
                if not accepted:
                    row['failed'] += 1
                reasons.update(('api_or_schema_failed', 'transport_error'))
                break
            except (ValueError, TypeError):
                if not accepted:
                    row['failed'] += 1
                reasons.update(('api_or_schema_failed', 'schema_or_protocol_error'))
                break
            except Exception:
                if not accepted:
                    row['failed'] += 1
                reasons.update(('api_or_schema_failed', 'internal_error'))
                break
        if accepted:
            row['checked'] += 1
            for key in SEVERITIES:
                totals[key] += subtotal[key]
    if row['checked']:
        row['counts'] = totals
    if totals['unknown']:
        reasons.add('unknown_severity')
    row['quality'] = ('complete' if row['complete_repositories'] == row['expected']
                      and not reasons else 'partial' if row['checked'] else
                      'unavailable' if row['unavailable'] and not row['failed'] else 'failed')
    row['reasons'] = sorted(reasons)
    return row


def view(row, now):
    """A stale zero never becomes a current green result."""
    result = dict(row)
    observed = datetime.fromisoformat(row['observed_utc'])
    age = (utc(now) - utc(observed)).total_seconds()
    if age < -300:
        raise ValueError('future_timestamp')
    result['age_seconds'] = max(0, int(age))
    if age > 26 * 3600:
        result.update(quality='stale', counts=None)
    return result


def run_once(directory, source, now, action):
    """Per-slot exclusive claim. Crash leaves an explicit attempt with no result.

    Retriggers do not repeat API collection. Next slot resumes normally; operator
    inspects interrupted claims instead of automatic retry storms. This is local
    state only, in a dedicated trusted directory separate from the live summary
    reader. The approved action must validate aggregate-only output before return;
    this helper is not a sanitizer for arbitrary provider payloads.
    """
    if source not in ('dependabot', 'sidekick_defender'):
        raise ValueError('source')
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('directory')
    stem = source + '-' + due_slot(now)
    claim, output = directory / (stem + '.claim'), directory / (stem + '.json')
    if output.exists() or output.is_symlink():
        return {'status': 'existing_result_refused', 'result_present': True}
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {'status': 'already_attempted', 'result_present': output.is_file()}
    with os.fdopen(fd, 'w') as stream:
        json.dump({'attempted_utc': utc(now).isoformat()}, stream)
    if output.exists() or output.is_symlink():
        return {'status': 'existing_result_refused', 'result_present': True}
    try:
        result = action()
    except Exception:
        result = {'source': source, 'quality': 'failed', 'reason': 'collector_failed',
                  'observed_utc': utc(now).isoformat(), 'counts': None}
    raw = json.dumps(result, allow_nan=False, separators=(',', ':')).encode()
    if len(raw) > 16384:
        raise ValueError('aggregate_size')
    temporary = directory / (stem + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, output)
    return {'status': 'saved', 'quality': result.get('quality')}


def retention_candidates(directory, now):
    """Review-only list; no deletion. 14 days keeps this separate store bounded."""
    cutoff = utc(now) - timedelta(days=14)
    pattern = re.compile(r'^(dependabot|sidekick_defender)-(\d{8}T220000Z)\.(json|claim|tmp)$')
    result = []
    for path in Path(directory).iterdir():
        match = pattern.fullmatch(path.name)
        if match and path.is_file() and not path.is_symlink():
            slot = datetime.strptime(match[2], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            if slot < cutoff:
                result.append(path.name)
    return sorted(result)
