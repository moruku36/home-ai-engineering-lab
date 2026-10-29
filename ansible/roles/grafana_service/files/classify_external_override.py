#!/usr/bin/env python3
"""Classify Grafana's one external Compose file without printing configuration."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def classify_document(document):
    if not isinstance(document, dict) or not isinstance(document.get('services', {}), dict):
        raise ValueError('unsupported structure')
    services = document.get('services', {})
    grafana = services.get('grafana')
    known = ('image', 'volumes', 'ports', 'environment', 'env_file', 'networks',
             'command', 'depends_on', 'secrets', 'configs', 'labels', 'deploy')
    if grafana is not None and not isinstance(grafana, dict):
        raise ValueError('unsupported grafana structure')
    return {
        'grafana_mentioned': 'grafana' in services,
        'grafana_fields': ','.join(k for k in known if isinstance(grafana, dict) and k in grafana) or 'none',
        'grafana_other_fields': isinstance(grafana, dict) and bool(set(grafana) - set(known)),
        'other_services': bool(set(services) - {'grafana'}),
        'non_service_sections': bool(set(document) - {'services', 'name', 'version'}),
    }


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        raise ValueError('project')
    root = Path(sys.argv[1]).resolve(strict=True)
    inspected = subprocess.run(['docker', 'inspect', '--format', '{{json .Config.Labels}}', 'grafana'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
    if len(inspected.stdout) > 100000:
        raise ValueError('labels')
    labels = json.loads(inspected.stdout)
    if (labels.get('com.docker.compose.project') != 'observability'
            or labels.get('com.docker.compose.service') != 'grafana'
            or Path(labels['com.docker.compose.project.working_dir']).resolve() != root):
        raise ValueError('identity')
    known = {root / 'compose.yaml', root / '.home-lab-ansible-prometheus.yml', root / '.home-lab-ansible-grafana.yml'}
    paths = [Path(p) if os.path.isabs(p) else root / p
             for p in labels['com.docker.compose.project.config_files'].split(',') if p]
    unknown = [p for p in paths if Path(os.path.normpath(p)) not in known]
    if len(unknown) != 1 or unknown[0].name != 'compose.override.json':
        raise ValueError('unexpected source')
    source = unknown[0]
    path = os.path.normpath(str(source))
    if path.startswith(('/tmp/', '/var/tmp/')):
        location = 'temporary'
    elif path.startswith('/run/'):
        location = 'runtime'
    elif path.startswith('/home/'):
        location = 'home'
    else:
        location = 'other'
    print('basename=compose.override.json location=' + location)
    parts = source.parts
    print('ansible_path_component=' + str(any(x == '.ansible' or x.startswith('ansible-') for x in parts)).lower())
    try:
        info = source.lstat()
    except FileNotFoundError:
        print('file=missing'); return
    if not stat.S_ISREG(info.st_mode):
        print('file=not_regular'); return
    print('file=regular owner=' + ('root' if info.st_uid == 0 else 'nonroot'))
    if info.st_size > 1000000:
        print('content=oversize'); return
    data = source.read_bytes()
    print('sha256=' + hashlib.sha256(data).hexdigest())
    flags = classify_document(json.loads(data))
    print(' '.join(k + '=' + str(v).lower() for k, v in flags.items()))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('DIAGNOSTIC_FAILED', file=sys.stderr)
        sys.exit(1)
