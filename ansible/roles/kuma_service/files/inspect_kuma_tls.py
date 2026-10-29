#!/usr/bin/env python3
"""Diagnose Kuma's aggregate TCP/TLS use without reading credentials."""
import re
import subprocess
import sys

NODE = r'''
const fs = require('fs');
const os = require('os');
let sqlite = false;
try { require.resolve('sqlite3'); sqlite = true; } catch (_) {}
console.log('sqlite_module=' + (sqlite ? 'present' : 'missing'));
const socket = '/app/data/run/mariadb.sock';
let exists = false;
try { exists = fs.statSync(socket).isSocket(); } catch (_) {}
console.log('embedded_mariadb_socket=' + (exists ? 'present' : 'absent'));
if (!exists) { console.log('monitor_tls_usage=unconfirmed'); process.exit(0); }
(async () => {
  let conn;
  try {
    const mysql = require('mysql2/promise');
    conn = await mysql.createConnection({socketPath:socket, user:os.userInfo().username, database:'kuma', connectTimeout:5000});
    await conn.query('START TRANSACTION READ ONLY');
    const [columns] = await conn.query("SELECT COLUMN_NAME AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='monitor' AND COLUMN_NAME IN ('type','smtp_security','expected_tls_alert')");
    if (columns.length !== 3) { console.log('monitor_tls_usage=schema_unconfirmed'); return; }
    const [rows] = await conn.query("SELECT COUNT(*) AS total, SUM(CASE WHEN LOWER(COALESCE(smtp_security,'')) IN ('secure','starttls') OR LOWER(COALESCE(expected_tls_alert,'')) NOT IN ('','none') THEN 1 ELSE 0 END) AS tls FROM monitor WHERE type='port'");
    const total = Number(rows[0].total), tls = Number(rows[0].tls || 0);
    if (!Number.isSafeInteger(total) || !Number.isSafeInteger(tls)) throw new Error('count');
    console.log('tcp_monitors=' + total + ' tcp_tls_candidates=' + tls);
  } catch (_) { console.log('monitor_tls_usage=connection_or_query_unavailable'); }
  finally { if (conn) { try { await conn.rollback(); await conn.end(); } catch (_) {} } }
})();
'''


def main():
    result = subprocess.run(['docker', 'exec', '-w', '/app', '--user', 'node',
                             'uptime-kuma', 'node', '-e', NODE], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, timeout=20)
    lines = result.stdout.strip().splitlines()
    safe = (result.returncode == 0 and len(lines) == 3
            and re.fullmatch(r'sqlite_module=(present|missing)', lines[0])
            and re.fullmatch(r'embedded_mariadb_socket=(present|absent)', lines[1])
            and re.fullmatch(
                r'(monitor_tls_usage=(unconfirmed|schema_unconfirmed|connection_or_query_unavailable)|'
                r'tcp_monitors=[0-9]+ tcp_tls_candidates=[0-9]+)', lines[2]))
    if not safe:
        print('DIAGNOSTIC_UNAVAILABLE')
        return
    print('\n'.join(lines))


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.SubprocessError):
        print('DIAGNOSTIC_UNAVAILABLE', file=sys.stderr)
        sys.exit(1)
