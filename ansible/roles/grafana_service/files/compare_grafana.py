#!/usr/bin/env python3
"""Check Grafana mounts and ports without logging secrets or resolved config."""
import json
import posixpath
import subprocess
import sys


def compare(config, container, root):
    if config.get('name') != 'observability':
        raise ValueError('project')
    service = config['services']['grafana']
    if service.get('container_name') != 'grafana':
        raise ValueError('container')
    expected = set()
    for item in service.get('volumes', []):
        kind, src = item['type'], item['source']
        if kind == 'volume':
            src = config['volumes'][src]['name']
        elif kind != 'bind':
            raise ValueError('mount type')
        expected.add((kind, src, item['target'], bool(item.get('read_only', False))))
    known = {('volume', 'observability_grafana-data', '/var/lib/grafana', False),
             ('bind', posixpath.join(root, 'grafana/provisioning'), '/etc/grafana/provisioning', True)}
    if expected != known or len(service.get('volumes', [])) != 2:
        raise ValueError('unknown mounts')
    actual = {(x['Type'], x['Name'] if x['Type'] == 'volume' else x['Source'],
               x['Destination'], not x['RW']) for x in container['Mounts']}
    if actual != expected or len(container['Mounts']) != len(actual):
        raise ValueError('runtime mounts differ')
    expected_ports = {(str(x.get('host_ip', '')), str(x['published']), str(x['target']),
                       x.get('protocol', 'tcp')) for x in service.get('ports', [])}
    if expected_ports != {('127.0.0.1', '3000', '3000', 'tcp')}:
        raise ValueError('unknown port')
    actual_ports = set()
    for target, bindings in container['NetworkSettings']['Ports'].items():
        number, protocol = target.split('/', 1)
        for binding in bindings or []:
            actual_ports.add((binding['HostIp'], binding['HostPort'], number, protocol))
    if actual_ports != expected_ports:
        raise ValueError('runtime ports differ')


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith('/'):
        raise ValueError('path')
    root = sys.argv[1]
    commands = [
        ['docker', 'compose', '-p', 'observability', '--project-directory', root,
         '-f', posixpath.join(root, 'compose.yaml'), 'config', '--format', 'json'],
        ['docker', 'inspect', 'grafana'],
    ]
    values = []
    for cmd in commands:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                check=True, timeout=30)
        if len(result.stdout) > 4000000:
            raise ValueError('oversize')
        values.append(json.loads(result.stdout))
    if len(values[1]) != 1:
        raise ValueError('inspect')
    compare(values[0], values[1][0], root)
    print('SCOPE_OK')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        print('SCOPE_REJECTED', file=sys.stderr)
        sys.exit(1)
