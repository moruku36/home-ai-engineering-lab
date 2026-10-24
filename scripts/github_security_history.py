#!/usr/bin/env python3
"""Serve existing history plus dedicated aggregate files; never collect or authenticate."""
import argparse
import json
from pathlib import Path
import time

import github_history as base
import security_summary as codec


def absent(source, quality=0, reason='dedicated_summary_not_collected'):
    return dict(scope=source, quality=quality, risk=0, reason=reason,
                critical_high=None, medium_low=None, unknown_alerts=None,
                checked=None, expected=2 if source == 'dependabot' else None,
                unavailable=None, observed_utc=None, last_success_utc=None,
                age_seconds=None, coverage_scope='two_selected_public_repositories'
                if source == 'dependabot' else 'not_collected', model_status='not_used')


def history(snapshots, summaries, now=None):
    now = time.time() if now is None else now
    result = base.history(snapshots, now)
    row = absent('dependabot')
    try:
        views = codec.read_views(summaries, now)
        if 'dependabot' in views:
            row.update(views['dependabot'])
    except (OSError, ValueError, TypeError, OverflowError):
        row = absent('dependabot', 4, 'security_input_unavailable')
    # Do not use old snapshots as a fallback, or infer a Sidekick audit from Dependabot.
    result['security'] = [row, absent('sidekick_defender')]
    return result


class ReadOnlyAdapter(base.ReadOnlyAdapter):
    def __init__(self, snapshots, summaries):
        super().__init__(snapshots)
        self.summaries = summaries

    def payload(self):
        with self.lock:
            if self.cached is None or time.monotonic() - self.at > 10:
                self.cached = json.dumps(history(self.snapshots, self.summaries),
                                         ensure_ascii=False, allow_nan=False).encode('utf-8')
                self.at = time.monotonic()
            return self.cached


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshots', required=True, type=Path)
    p.add_argument('--security-summaries', required=True, type=Path)
    p.add_argument('--serve', action='store_true')
    p.add_argument('--bind', choices=('127.0.0.1', '0.0.0.0'), default='127.0.0.1')
    p.add_argument('--port', type=int, default=8081)
    args = p.parse_args(argv)
    if args.serve:
        base.ThreadingHTTPServer((args.bind, args.port), base.handler(
            ReadOnlyAdapter(args.snapshots, args.security_summaries))).serve_forever()
    else:
        print(json.dumps(history(args.snapshots, args.security_summaries), allow_nan=False))


if __name__ == '__main__':
    main()
