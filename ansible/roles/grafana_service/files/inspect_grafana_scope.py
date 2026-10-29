#!/usr/bin/env python3
"""Report only fixed, non-secret Grafana Compose identity categories."""
import json
import os
import posixpath
import subprocess
import sys


def classify(labels, state, root):
    root = posixpath.normpath(root)
    base = posixpath.join(root, 'compose.yaml')
    known = {
        base: 'base',
        posixpath.join(root, '.home-lab-ansible-prometheus.yml'): 'prometheus_override',
        posixpath.join(root, '.home-lab-ansible-grafana.yml'): 'grafana_override',
    }
    working_dir = posixpath.normpath(labels.get('com.docker.compose.project.working_dir', ''))
    raw = labels.get('com.docker.compose.project.config_files', '')
    files = [posixpath.normpath(posixpath.join(working_dir, v)) for v in raw.split(',') if v]
    names = {known[f] for f in files if f in known}
    flags = {
        'project_ok': labels.get('com.docker.compose.project') == 'observability',
        'service_ok': labels.get('com.docker.compose.service') == 'grafana',
        'running': state == 'running',
        'working_dir_ok': working_dir == root,
        'base': 'base' in names,
        'prometheus_override': 'prometheus_override' in names,
        'grafana_override': 'grafana_override' in names,
        'unknown_files': sum(f not in known for f in files),
        'duplicate_files': len(files) - len(set(files)),
    }
    accepted = (all(flags[k] for k in ('project_ok', 'service_ok', 'running', 'working_dir_ok', 'base'))
                and not flags['unknown_files'] and not flags['duplicate_files'])
    return flags, accepted


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith('/'):
        raise ValueError('path')
    result = subprocess.run(['docker', 'inspect', '--format', '{{json .Config.Labels}}|{{.State.Status}}', 'grafana'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=15, check=True)
    if len(result.stdout) > 100000:
        raise ValueError('oversize')
    labels, state = result.stdout.strip().rsplit('|', 1)
    flags, accepted = classify(json.loads(labels), state, sys.argv[1])
    print(' '.join(str(k) + '=' + str(v).lower() for k, v in flags.items()))
    print('SCOPE_OK' if accepted else 'SCOPE_REJECTED')
    return 0 if accepted else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        print('INSPECTION_FAILED', file=sys.stderr)
        sys.exit(1)
