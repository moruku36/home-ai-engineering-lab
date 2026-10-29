#!/usr/bin/env python3
"""Report Kuma Compose metadata and aggregate TCP/TLS usage only."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import yaml

NODE_READONLY = r'''
const sqlite3 = require('sqlite3');
const db = new sqlite3.Database('/app/data/kuma.db', sqlite3.OPEN_READONLY, err => {
  if (err) { console.log('MONITOR_CHECK_UNAVAILABLE'); process.exitCode = 1; return; }
  db.all('PRAGMA table_info(monitor)', (error, cols) => {
    if (error || !['type', 'smtp_security', 'expected_tls_alert'].every(x => cols.some(c => c.name === x))) {
      console.log('MONITOR_SCHEMA_UNCONFIRMED'); db.close(); process.exitCode = 1; return;
    }
    const sql = "SELECT COUNT(*) AS total, SUM(CASE WHEN lower(coalesce(smtp_security,'')) IN ('secure','starttls') OR lower(coalesce(expected_tls_alert,'')) NOT IN ('','none') THEN 1 ELSE 0 END) AS tls FROM monitor WHERE type='port'";
    db.get(sql, (e, row) => {
      if (e) { console.log('MONITOR_CHECK_UNAVAILABLE'); process.exitCode = 1; }
      else console.log('tcp_monitors=' + row.total + ' tcp_tls_candidates=' + (row.tls || 0));
      db.close();
    });
  });
});
'''


def inspect(template):
    p = subprocess.run(['docker', 'inspect', '--format', template, 'uptime-kuma'],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
    if len(p.stdout) > 1000000:
        raise ValueError('oversize')
    return json.loads(p.stdout)


def main():
    labels = inspect('{{json .Config.Labels}}')
    state = inspect('{{json .State.Status}}')
    mounts = inspect('{{json .Mounts}}')
    ports = inspect('{{json .NetworkSettings.Ports}}')
    print('project_uptime_kuma=' + str(labels.get('com.docker.compose.project') == 'uptime-kuma').lower())
    print('service_uptime_kuma=' + str(labels.get('com.docker.compose.service') == 'uptime-kuma').lower())
    print('running=' + str(state == 'running').lower())
    print('expected_volume=' + str(any(m.get('Type') == 'volume' and m.get('Name') == 'uptime-kuma_uptime-kuma-data'
                                       and m.get('Destination') == '/app/data' and m.get('RW') for m in mounts)).lower())
    bindings = ports.get('3001/tcp') or []
    print('loopback_port=' + str(len(bindings) == 1 and bindings[0].get('HostIp') == '127.0.0.1'
                                 and bindings[0].get('HostPort') == '3001').lower())
    working = Path(labels['com.docker.compose.project.working_dir'])
    paths = [Path(p) if os.path.isabs(p) else working / p
             for p in labels.get('com.docker.compose.project.config_files', '').split(',') if p]
    print('compose_file_count=' + str(len(paths)))
    for index, path in enumerate(paths, 1):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', path.name):
            raise ValueError('basename')
        print('file_' + str(index) + '_basename=' + path.name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            print('file_' + str(index) + '_status=missing'); continue
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1000000:
            print('file_' + str(index) + '_status=unsupported'); continue
        data = path.read_bytes()
        print('file_' + str(index) + '_sha256=' + hashlib.sha256(data).hexdigest())
        doc = yaml.safe_load(data)
        if not isinstance(doc, dict) or not isinstance(doc.get('services', {}), dict):
            print('file_' + str(index) + '_classification=unrecognized'); continue
        services = doc.get('services', {})
        item = services.get('uptime-kuma')
        keys = ('image', 'volumes', 'ports', 'environment', 'env_file', 'networks', 'command',
                'depends_on', 'secrets', 'configs', 'labels', 'deploy')
        fields = [key for key in keys if isinstance(item, dict) and key in item]
        print('file_' + str(index) + '_kuma_fields=' + (','.join(fields) if fields else 'none'))
        print('file_' + str(index) + '_other_services=' + str(bool(set(services) - {'uptime-kuma'})).lower())
        print('file_' + str(index) + '_other_sections=' + str(bool(set(doc) - {'services', 'name', 'version'})).lower())
    result = subprocess.run(['docker', 'exec', '-w', '/app', 'uptime-kuma', 'node', '-e', NODE_READONLY],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=20)
    safe = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r'tcp_monitors=[0-9]+ tcp_tls_candidates=[0-9]+', safe):
        print('monitor_tls_usage=unconfirmed')
    else:
        print(safe)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, yaml.YAMLError):
        print('DIAGNOSTIC_FAILED', file=sys.stderr)
        sys.exit(1)
