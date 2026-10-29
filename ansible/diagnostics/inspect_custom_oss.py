#!/usr/bin/env python3
"""Read-only, non-secret Docker and KVM attachment inventory."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

PUBLIC_MAIN = '5b5764a1fe40340823885a6b7b842cdc985fe276'
SOURCES = {
    'mcp_server': ('stacks/mcp/mcp-server/server.py', 'b9193138aeda59b443245f17419ecbdce3339098'),
    'jobs_server': ('stacks/n8n/python-jobs/server.py', '2af75cee360543cb441fae0c700e820ac6b83127'),
    'jobs_snapshot': ('stacks/n8n/python-jobs/github_snapshot.py', '165e51091ff42db5e7fc976921175d33ddeda892'),
    'history': ('scripts/github_history.py', 'ee4c0c9b7699d3f0337964b2d255fc04b6d47be7'),
    'metrics': ('scripts/github_snapshot_metrics.py', '55d39a13588a9f562bd962a8f61e61024d439081'),
}
CONTAINERS = ('python-jobs', 'mcp-server', 'observability-github-history-1')
BIND_TARGETS = {'/app/github_history.py': 'history', '/app/github_snapshot_metrics.py': 'metrics'}


def blob_match(path, expected):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 5000000:
            return 'unsupported'
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        return 'matches' if blob == expected else 'differs'
    except FileNotFoundError:
        return 'missing'
    except OSError:
        return 'unavailable'


def inspect(name):
    template = '{{json .Config.Image}}\n{{json .Image}}\n{{json .State.Status}}\n{{json .Config.Labels}}\n{{json .Mounts}}'
    process = subprocess.run(['docker', 'inspect', '--format', template, name], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=15)
    if process.returncode != 0 or len(process.stdout) > 1000000:
        print(name + ' inspection=unavailable'); return
    parts = process.stdout.decode('utf-8').splitlines()
    if len(parts) != 5:
        raise ValueError('inspect')
    reference, image, state, labels, mounts = [json.loads(x) for x in parts]
    if not isinstance(image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('image')
    project = labels.get('com.docker.compose.project', '')
    service = labels.get('com.docker.compose.service', '')
    project = project if project in ('n8n', 'mcp', 'observability') else 'other'
    service = service if service in ('python-jobs', 'mcp-server', 'github-history') else 'other'
    ref_kind = 'expected_local_image' if reference in ('home-ai-lab/python-jobs:1', 'home-ai-lab/mcp-server:1') else 'other'
    safe_state = state if state in ('running', 'exited', 'created', 'paused', 'restarting', 'dead') else 'other'
    print(name + ' state=' + safe_state + ' image_id=' + image + ' image_ref=' + ref_kind
          + ' project=' + project + ' service=' + service)
    print(name + ' volume_mounts=' + str(sum(m.get('Type') == 'volume' for m in mounts))
          + ' bind_mounts=' + str(sum(m.get('Type') == 'bind' for m in mounts)))
    for mount in mounts:
        key = BIND_TARGETS.get(mount.get('Destination'))
        if key and mount.get('Type') == 'bind':
            result = blob_match(Path(mount['Source']), SOURCES[key][1])
            print(name + ' bind_' + key + '_vs_public=' + result
                  + ' readonly=' + str(not bool(mount.get('RW'))).lower())


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        raise ValueError('repository')
    root = Path(sys.argv[1])
    print('public_main_snapshot=' + PUBLIC_MAIN)
    for key, (relative, expected) in SOURCES.items():
        print('source_' + key + '_vs_public=' + blob_match(root / relative, expected))
    for name in CONTAINERS:
        try:
            inspect(name)
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError):
            print(name + ' inspection=unavailable')
    try:
        mode = os.lstat('/run/rea-vm/serial.sock').st_mode
        print('guest_serial=' + ('socket' if stat.S_ISSOCK(mode) else 'unexpected_type'))
    except FileNotFoundError:
        print('guest_serial=absent')
    except PermissionError:
        print('guest_serial=permission_denied')
    print('runtime_image_source_correspondence=unverified')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError):
        print('DIAGNOSTIC_INCOMPLETE', file=sys.stderr)
        sys.exit(1)
