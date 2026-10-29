#!/usr/bin/env python3
"""Validate the n8n update without emitting resolved configuration."""
import copy
import hashlib
import json
import os
import stat
import subprocess
import sys

BASE_SHA = '00ec115da85bc8a73764ac1b06ef7936e137466038d5387bdd2751c6109a3d51'
IMAGE = 'n8nio/n8n:2.44.7@sha256:7a7708314f9b1d0656e2e7f697abb64fae5f76e1895f0a9ccb9036c3933a0394'


def run_json(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=30)
    if len(result.stdout) > 4000000:
        raise ValueError('oversize')
    return json.loads(result.stdout)


def digest(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4000000:
        raise ValueError('source')
    with open(path, 'rb') as file:
        return hashlib.sha256(file.read()).hexdigest()


def identity(root):
    data = run_json(['docker', 'inspect', 'n8n'])
    if len(data) != 1:
        raise ValueError('inspect')
    container = data[0]
    labels = container['Config']['Labels']
    if (labels.get('com.docker.compose.project') != 'n8n'
            or labels.get('com.docker.compose.service') != 'n8n'
            or container['State']['Status'] != 'running'
            or os.path.normpath(labels.get('com.docker.compose.project.working_dir', '')) != root):
        raise ValueError('identity')
    files = [os.path.normpath(os.path.join(root, p)) for p in labels['com.docker.compose.project.config_files'].split(',') if p]
    base = os.path.join(root, 'compose.yaml')
    override = os.path.join(root, '.home-lab-ansible-n8n.yml')
    if files == [base, override]:
        digest(override)
        with open(override, 'rb') as file:
            if not file.read(100).startswith(b'# Managed by HomeLab Ansible; n8n image override only.\n'):
                raise ValueError('override')
    elif files != [base]:
        raise ValueError('unexpected input files')
    if digest(base) != BASE_SHA:
        raise ValueError('source changed')
    return container, base, override


def compose(root, files):
    args = ['docker', 'compose', '-p', 'n8n', '--project-directory', root]
    for path in files:
        args += ['-f', path]
    return run_json(args + ['config', '--format', 'json'])


def compare_runtime(config, container):
    if config.get('name') != 'n8n':
        raise ValueError('project')
    service = config['services']['n8n']
    if service.get('container_name') != 'n8n':
        raise ValueError('container')
    mounts = service.get('volumes', [])
    if len(mounts) != 1:
        raise ValueError('mount count')
    m = mounts[0]
    if (m.get('type') != 'volume' or m.get('target') != '/home/node/.n8n'
            or m.get('read_only', False) or config['volumes'][m['source']]['name'] != 'n8n_n8n-data'):
        raise ValueError('configured volume')
    actual = container['Mounts']
    if len(actual) != 1 or not (actual[0].get('Type') == 'volume' and actual[0].get('Name') == 'n8n_n8n-data'
                                and actual[0].get('Destination') == '/home/node/.n8n' and actual[0].get('RW')):
        raise ValueError('runtime volume')
    ports = {(str(p.get('host_ip', '')), str(p['published']), str(p['target']), p.get('protocol', 'tcp'))
             for p in service.get('ports', [])}
    if ports != {('127.0.0.1', '5678', '5678', 'tcp')}:
        raise ValueError('configured port')
    runtime_ports = set()
    for target, bindings in container['NetworkSettings']['Ports'].items():
        number, protocol = target.split('/', 1)
        for binding in bindings or []:
            runtime_ports.add((binding['HostIp'], binding['HostPort'], number, protocol))
    if runtime_ports != ports:
        raise ValueError('runtime port')
    service_networks = service.get('networks', {})
    expected_networks = {config['networks'][name]['name'] for name in service_networks}
    actual_networks = set(container['NetworkSettings']['Networks'])
    if len(expected_networks) != 3 or expected_networks != actual_networks:
        raise ValueError('runtime networks')


def effective_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def image_only(original, revised):
    expected = copy.deepcopy(original)
    expected['services']['n8n']['image'] = IMAGE
    if revised != expected:
        raise ValueError('unexpected configuration change')


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ('baseline', 'verify') or not os.path.isabs(sys.argv[1]):
        raise ValueError('arguments')
    root = os.path.normpath(sys.argv[1])
    container, base, override = identity(root)
    original = compose(root, [base])
    compare_runtime(original, container)
    snapshot = {'base_sha': digest(base), 'effective_sha': effective_hash(original)}
    if sys.argv[2] == 'baseline':
        print(json.dumps(snapshot))
        return
    if json.loads(os.environ['N8N_BASELINE']) != snapshot or snapshot['base_sha'] != BASE_SHA:
        raise ValueError('source changed')
    digest(override)
    image_only(original, compose(root, [base, override]))
    if digest(base) != BASE_SHA or effective_hash(compose(root, [base])) != snapshot['effective_sha']:
        raise ValueError('source changed')
    print(json.dumps({'files': [base, override]}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('SCOPE_REJECTED', file=sys.stderr)
        sys.exit(1)
