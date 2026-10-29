#!/usr/bin/env python3
"""Read-only parse validation of non-secret candidate PromQL."""
import json
from pathlib import Path
import urllib.parse
import urllib.request
import yaml

rules = yaml.safe_load((Path(__file__).parents[1] / 'roles/prometheus_alerts_candidate/files/target-alerts.yml').read_text())
expressions = [rule['expr'] for group in rules['groups'] for rule in group['rules']]
for expression in expressions:
    url = 'http://127.0.0.1:9090/api/v1/parse_query?' + urllib.parse.urlencode({'query': expression})
    with urllib.request.urlopen(url, timeout=5) as response:
        if json.load(response).get('status') != 'success':
            raise ValueError('PromQL parse failed')
print('PromQL parse OK:', len(expressions), 'expressions')
