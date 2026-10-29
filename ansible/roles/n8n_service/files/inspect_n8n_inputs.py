#!/usr/bin/env python3
"""Report n8n Compose input metadata and key categories without values."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import yaml


def inspect(format_string):
    r = subprocess.run(['docker', 'inspect', '--format', format_string, 'n8n'],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
    if len(r.stdout) > 1000000:
        raise ValueError('oversize')
    return json.loads(r.stdout)


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        raise ValueError('path')
    root = Path(sys.argv[1]).resolve(strict=True)
    labels = inspect('{{json .Config.Labels}}')
    state = inspect('{{json .State.Status}}')
    mounts = inspect('{{json .Mounts}}')
    ports = inspect('{{json .NetworkSettings.Ports}}')
    working = Path(labels.get('com.docker.compose.project.working_dir', '/')).resolve()
    print('project_n8n=' + str(labels.get('com.docker.compose.project') == 'n8n').lower())
    print('service_n8n=' + str(labels.get('com.docker.compose.service') == 'n8n').lower())
    print('running=' + str(state == 'running').lower())
    print('working_dir_matches=' + str(working == root).lower())
    expected_volume = any(m.get('Type') == 'volume' and m.get('Name') == 'n8n_n8n-data'
                          and m.get('Destination') == '/home/node/.n8n' and m.get('RW') for m in mounts)
    print('expected_volume=' + str(expected_volume).lower())
    bindings = ports.get('5678/tcp') or []
    print('loopback_port=' + str(len(bindings) == 1 and bindings[0].get('HostIp') == '127.0.0.1'
                                 and bindings[0].get('HostPort') == '5678').lower())
    paths = [Path(p) if os.path.isabs(p) else working / p
             for p in labels.get('com.docker.compose.project.config_files', '').split(',') if p]
    print('compose_file_count=' + str(len(paths)))
    for index, path in enumerate(paths):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', path.name):
            raise ValueError('unsafe basename')
        print('file_' + str(index + 1) + '_basename=' + path.name)
        try:
            st = path.lstat()
        except FileNotFoundError:
            print('file_' + str(index + 1) + '_status=missing'); continue
        if not stat.S_ISREG(st.st_mode) or st.st_size > 1000000:
            print('file_' + str(index + 1) + '_status=unsupported'); continue
        data = path.read_bytes()
        print('file_' + str(index + 1) + '_sha256=' + hashlib.sha256(data).hexdigest())
        document = yaml.safe_load(data)
        if not isinstance(document, dict) or not isinstance(document.get('services', {}), dict):
            print('file_' + str(index + 1) + '_classification=unrecognized'); continue
        services = document.get('services', {})
        entry = services.get('n8n')
        keys = ('image', 'volumes', 'ports', 'environment', 'env_file', 'networks',
                'command', 'depends_on', 'secrets', 'configs', 'labels', 'deploy')
        present = [x for x in keys if isinstance(entry, dict) and x in entry]
        print('file_' + str(index + 1) + '_n8n_fields=' + (','.join(present) if present else 'none'))
        print('file_' + str(index + 1) + '_other_services=' + str(bool(set(services) - {'n8n'})).lower())
        print('file_' + str(index + 1) + '_other_sections=' + str(bool(set(document) - {'services', 'name', 'version'})).lower())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, yaml.YAMLError):
        print('DIAGNOSTIC_FAILED', file=sys.stderr)
        sys.exit(1)
