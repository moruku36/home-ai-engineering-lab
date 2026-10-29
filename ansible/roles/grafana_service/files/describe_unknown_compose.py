#!/usr/bin/env python3
"""Describe one unrecognized Compose source without disclosing its values."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import yaml


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        raise ValueError('path')
    root = Path(sys.argv[1]).resolve(strict=True)
    proc = subprocess.run(['docker', 'inspect', '--format', '{{json .Config.Labels}}', 'grafana'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
    if len(proc.stdout) > 100000:
        raise ValueError('labels')
    labels = json.loads(proc.stdout)
    if labels.get('com.docker.compose.project') != 'observability' or labels.get('com.docker.compose.service') != 'grafana':
        raise ValueError('identity')
    if Path(labels['com.docker.compose.project.working_dir']).resolve() != root:
        raise ValueError('working directory')
    known = {root / 'compose.yaml', root / '.home-lab-ansible-prometheus.yml', root / '.home-lab-ansible-grafana.yml'}
    files = [Path(p) if os.path.isabs(p) else root / p
             for p in labels['com.docker.compose.project.config_files'].split(',') if p]
    unknown = [p for p in files if Path(os.path.normpath(p)) not in known]
    if len(unknown) != 1:
        raise ValueError('expected exactly one unknown')
    source = unknown[0]
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', source.name):
        raise ValueError('unsafe basename')
    print('basename=' + source.name)
    if source.is_symlink() or not source.is_file():
        print('file=unavailable_or_symlink'); return
    resolved = source.resolve(strict=True)
    if not resolved.is_relative_to(root):
        print('file=outside_project; content_not_read'); return
    if resolved.stat().st_size > 1000000:
        print('file=oversize; content_not_read'); return
    data = resolved.read_bytes()
    print('sha256=' + hashlib.sha256(data).hexdigest())
    document = yaml.safe_load(data)
    if not isinstance(document, dict) or not isinstance(document.get('services', {}), dict):
        print('classification=unrecognized'); return
    services = document.get('services', {})
    grafana = services.get('grafana')
    safe_keys = ('image', 'volumes', 'ports', 'environment', 'env_file', 'networks',
                 'command', 'depends_on', 'secrets', 'configs')
    present = [key for key in safe_keys if isinstance(grafana, dict) and key in grafana]
    print('grafana_mentioned=' + str('grafana' in services).lower())
    print('grafana_fields=' + (','.join(present) if present else 'none'))
    print('grafana_other_fields=' + str(isinstance(grafana, dict) and bool(set(grafana) - set(safe_keys))).lower())
    print('other_services=' + str(bool(set(services) - {'grafana'})).lower())
    print('non_service_sections=' + str(bool(set(document) - {'services', 'name', 'version'})).lower())


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, yaml.YAMLError):
        print('DIAGNOSTIC_FAILED', file=sys.stderr)
        sys.exit(1)
