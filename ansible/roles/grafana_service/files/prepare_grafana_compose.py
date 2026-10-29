#!/usr/bin/env python3
"""Preserve existing Compose inputs; never print resolved configuration."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

EXTERNAL_SHA = 'c288dcdd370160b30aa145ac0c6f5d0ab304470ca26aef31c5b639df66247889'
IMAGE = 'grafana/grafana:12.4.14@sha256:1b59d2076a5e08e0e9929a1225f37869ee7719f4a11c004fbfcfa8b772858e89'


def run_json(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=True, timeout=30)
    if len(result.stdout) > 4000000:
        raise ValueError('oversize')
    return json.loads(result.stdout)


def digest(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4000000:
        raise ValueError('invalid source')
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def identity(root):
    data = run_json(['docker', 'inspect', 'grafana'])
    if len(data) != 1:
        raise ValueError('inspect')
    container = data[0]
    labels = container['Config']['Labels']
    if (labels.get('com.docker.compose.project') != 'observability'
            or labels.get('com.docker.compose.service') != 'grafana'
            or container['State']['Status'] != 'running'
            or os.path.normpath(labels.get('com.docker.compose.project.working_dir', '')) != root):
        raise ValueError('identity')
    files = [os.path.normpath(os.path.join(root, x)) for x in labels['com.docker.compose.project.config_files'].split(',') if x]
    base = os.path.join(root, 'compose.yaml')
    generated = os.path.join(root, '.home-lab-ansible-grafana.yml')
    if len(files) == 3 and files[-1] == generated:
        digest(generated)
        with open(generated, 'rb') as f:
            if not f.read(100).startswith(b'# Managed by HomeLab Ansible; Grafana image override only.\n'):
                raise ValueError('generated override')
        files = files[:-1]
    if len(files) != 2 or len(set(files)) != 2 or files.count(base) != 1:
        raise ValueError('file set')
    external = next(x for x in files if x != base)
    if os.path.basename(external) != 'compose.override.json' or os.lstat(external).st_uid != 0:
        raise ValueError('external source')
    checksums = [digest(f) for f in files]
    if checksums[files.index(external)] != EXTERNAL_SHA:
        raise ValueError('external checksum')
    return container, files, checksums


def compose(root, files):
    args = ['docker', 'compose', '-p', 'observability', '--project-directory', root]
    for file in files:
        args.extend(['-f', file])
    return run_json(args + ['config', '--format', 'json'])


def compare_runtime(config, container, root):
    if config.get('name') != 'observability':
        raise ValueError('project')
    service = config['services']['grafana']
    if service.get('container_name') != 'grafana':
        raise ValueError('container')
    mounts = service.get('volumes', [])
    expected = set()
    for item in mounts:
        kind, source = item['type'], item['source']
        if kind == 'volume':
            source = config['volumes'][source]['name']
        elif kind != 'bind':
            raise ValueError('mount type')
        expected.add((kind, source, item['target'], bool(item.get('read_only', False))))
    known = {('volume', 'observability_grafana-data', '/var/lib/grafana', False),
             ('bind', os.path.join(root, 'grafana/provisioning'), '/etc/grafana/provisioning', True)}
    actual = {(x['Type'], x['Name'] if x['Type'] == 'volume' else x['Source'],
               x['Destination'], not x['RW']) for x in container['Mounts']}
    if len(mounts) != 2 or expected != known or len(container['Mounts']) != 2 or actual != expected:
        raise ValueError('mounts')
    expected_ports = {(str(p.get('host_ip', '')), str(p['published']), str(p['target']), p.get('protocol', 'tcp'))
                      for p in service.get('ports', [])}
    if expected_ports != {('127.0.0.1', '3000', '3000', 'tcp')}:
        raise ValueError('ports')
    actual_ports = set()
    for target, bindings in container['NetworkSettings']['Ports'].items():
        number, protocol = target.split('/', 1)
        for binding in bindings or []:
            actual_ports.add((binding['HostIp'], binding['HostPort'], number, protocol))
    if actual_ports != expected_ports:
        raise ValueError('runtime ports')


def validate_image_only(original, revised):
    expected_config = copy.deepcopy(original)
    expected_config['services']['grafana']['image'] = IMAGE
    if revised != expected_config:
        raise ValueError('unexpected effective difference')


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ('baseline', 'verify') or not os.path.isabs(sys.argv[1]):
        raise ValueError('arguments')
    root = os.path.normpath(sys.argv[1])
    container, files, checksums = identity(root)
    original = compose(root, files)
    compare_runtime(original, container, root)
    if [digest(f) for f in files] != checksums:
        raise ValueError('changed source')
    if sys.argv[2] == 'baseline':
        print(json.dumps({'files': files, 'checksums': checksums}))
        return
    expected = json.loads(os.environ['GRAFANA_BASELINE'])
    if expected != {'files': files, 'checksums': checksums}:
        raise ValueError('baseline changed')
    override = os.path.join(root, '.home-lab-ansible-grafana.yml')
    digest(override)
    revised = compose(root, files + [override])
    validate_image_only(original, revised)
    if [digest(f) for f in files] != checksums:
        raise ValueError('changed source')
    print(json.dumps({'files': files + [override]}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError):
        print('SCOPE_REJECTED', file=sys.stderr)
        sys.exit(1)
