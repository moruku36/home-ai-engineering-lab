#!/usr/bin/env python3
"""Compare public, checkout and running image source without printing content."""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

PUBLIC_MAIN = '5b5764a1fe40340823885a6b7b842cdc985fe276'
ITEMS = (
    ('jobs_server', 'python-jobs', '/app/server.py', 'stacks/n8n/python-jobs/server.py', '2af75cee360543cb441fae0c700e820ac6b83127'),
    ('jobs_snapshot', 'python-jobs', '/app/github_snapshot.py', 'stacks/n8n/python-jobs/github_snapshot.py', '165e51091ff42db5e7fc976921175d33ddeda892'),
    ('mcp_server', 'mcp-server', '/app/server.py', 'stacks/mcp/mcp-server/server.py', 'b9193138aeda59b443245f17419ecbdce3339098'),
    ('mcp_policy', 'mcp-server', '/app/policy.json', 'stacks/mcp/mcp-server/policy.json', 'f3fff737895a0f87ebfe3d13bebca9ce45786bba'),
)
RUNNER = "import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); d=p.read_bytes(); print(hashlib.sha1(b'blob '+str(len(d)).encode()+bytes([0])+d).hexdigest())"


def local_hash(path):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 5000000:
            return None
        data = path.read_bytes()
        return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    except OSError:
        return None


def runtime_hash(container, path):
    result = subprocess.run(['docker', 'exec', '--env', 'PYTHONDONTWRITEBYTECODE=1', container, 'python3', '-c', RUNNER, path],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
    value = result.stdout.decode('ascii', errors='ignore').strip()
    return value if result.returncode == 0 and re.fullmatch(r'[0-9a-f]{40}', value) else None


def relation(left, right):
    if left is None or right is None:
        return 'unavailable'
    return 'matches' if left == right else 'differs'


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        raise ValueError('repository')
    root = Path(sys.argv[1])
    print('public_main_snapshot=' + PUBLIC_MAIN)
    for label, container, inside, local, public in ITEMS:
        try:
            current = runtime_hash(container, inside)
        except (OSError, subprocess.SubprocessError):
            current = None
        checkout = local_hash(root / local)
        print(label + ' runtime_vs_public=' + relation(current, public)
              + ' runtime_vs_checkout=' + relation(current, checkout))
    print('comparison_scope=selected_files_only')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, TypeError):
        print('DIAGNOSTIC_INCOMPLETE', file=sys.stderr)
        sys.exit(1)
