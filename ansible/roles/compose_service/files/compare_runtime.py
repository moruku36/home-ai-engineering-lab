#!/usr/bin/env python3
"""Compare selected Prometheus mounts and published ports without printing data."""
import json
from pathlib import Path
import posixpath
import subprocess
import sys


def compare(config, container, project_dir):
    if config.get('name') != 'observability':
        raise ValueError('project')
    service = config['services']['prometheus']
    if service.get('container_name') != 'prometheus':
        raise ValueError('container')
    mounts = service.get('volumes', [])
    if len(mounts) != 2:
        raise ValueError('mount count')
    expected_mounts = set()
    for mount in mounts:
        kind, target = mount['type'], mount['target']
        source = mount['source']
        if kind == 'volume':
            source = config['volumes'][source]['name']
        elif kind != 'bind':
            raise ValueError('mount type')
        expected_mounts.add((kind, source, target, bool(mount.get('read_only', False))))
    expected_known = {
        ('volume', 'observability_prometheus-data', '/prometheus', False),
        ('bind', posixpath.join(project_dir, 'prometheus/prometheus.yml'), '/etc/prometheus/prometheus.yml', True),
    }
    if expected_mounts != expected_known:
        raise ValueError('unknown mount')
    actual_mounts = set()
    for mount in container['Mounts']:
        kind = mount['Type']
        source = mount['Name'] if kind == 'volume' else mount['Source']
        actual_mounts.add((kind, source, mount['Destination'], not mount['RW']))
    if len(actual_mounts) != len(container['Mounts']) or actual_mounts != expected_mounts:
        raise ValueError('runtime mounts differ')

    ports = service.get('ports', [])
    expected_ports = set()
    for port in ports:
        expected_ports.add((str(port.get('host_ip', '')), str(port['published']),
                            str(port['target']), port.get('protocol', 'tcp')))
    if expected_ports != {('127.0.0.1', '9090', '9090', 'tcp')}:
        raise ValueError('unknown port')
    actual_ports = set()
    for target, bindings in container['NetworkSettings']['Ports'].items():
        target_port, protocol = target.split('/', 1)
        for binding in bindings or []:
            actual_ports.add((binding['HostIp'], binding['HostPort'], target_port, protocol))
    if actual_ports != expected_ports:
        raise ValueError('runtime ports differ')


def main():
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_absolute():
        raise ValueError('path')
    root = sys.argv[1]
    compose = subprocess.run(['docker', 'compose', '-p', 'observability', '--project-directory', root,
                              '-f', str(Path(root) / 'compose.yaml'), 'config', '--format', 'json'],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=30)
    inspect = subprocess.run(['docker', 'inspect', 'prometheus'], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, check=True, timeout=30)
    if len(compose.stdout) > 4000000 or len(inspect.stdout) > 4000000:
        raise ValueError('oversize')
    result = json.loads(inspect.stdout)
    if len(result) != 1:
        raise ValueError('inspect')
    compare(json.loads(compose.stdout), result[0], root)
    print('SCOPE_OK')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        print('SCOPE_REJECTED', file=sys.stderr)
        sys.exit(1)
