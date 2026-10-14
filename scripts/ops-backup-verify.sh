#!/usr/bin/env bash
# Backup / recovery verification + MCP test-workflow update. Re-runnable. On the NUC: bash ops-backup-verify.sh
# - imports the extended MCP test workflow (reads the latest GitHub report through MCP)
# - runs one backup with the fixed script, then a restore test (never touches live volumes)
# - proves a deliberately stopped stack (Open WebUI) stays stopped after the backup
# - records timers, journal, disk, log rotation and automatic-update settings; dry-runs unattended-upgrades
set -euo pipefail
sudo -v
APP=~/home-ai-lab

echo "######## 1. update MCP test workflow (same id, overwritten)"
cp ~/mcp-readonly-test.json "$APP/mcp/workflows/mcp-readonly-test.json"
sudo docker cp "$APP/mcp/workflows/mcp-readonly-test.json" n8n:/tmp/mcpwf.json
sudo docker exec n8n n8n import:workflow --input=/tmp/mcpwf.json 2>&1 | grep -v 'license SDK'
sudo docker exec n8n rm -f /tmp/mcpwf.json

echo "######## 2. which backup script is installed / timer"
grep -c "left stopped" /usr/local/sbin/home-ai-lab-backup | sed 's/^/fixed script marker lines: /'
systemctl cat home-ai-lab-backup.timer | grep -E "OnCalendar|Persistent|RandomizedDelay"
systemctl list-timers home-ai-lab-backup.timer --no-pager | head -3

echo "######## 3. backup now (stops running stacks briefly)"
sudo docker ps --format '{{.Names}}' | sort | tr '\n' ' '; echo "<- running before"
sudo /usr/local/sbin/home-ai-lab-backup
sudo docker ps --format '{{.Names}}' | sort | tr '\n' ' '; echo "<- running after"
sudo docker ps -a --filter name=open-webui --format 'open-webui after backup: {{.Status}}'

echo "######## 4. restore test"
sudo /usr/local/sbin/home-ai-lab-restore-test
sudo docker ps -a --filter name=open-webui --format 'open-webui after restore test: {{.Status}}'

echo "######## 5. backups on disk"
sudo ls -l /var/backups/home-ai-lab; sudo du -sh /var/backups/home-ai-lab; df -h / | tail -1

echo "######## 6. automatic updates (dry run - changes nothing)"
sudo unattended-upgrade --dry-run 2>&1 | tail -4 || true
echo "reboot pending: $([ -e /var/run/reboot-required ] && echo YES || echo no)"
grep -hE "^Unattended-Upgrade::(Automatic-Reboot|Remove-Unused)" /etc/apt/apt.conf.d/50unattended-upgrades || true
echo "(Automatic-Reboot is off unless a line above says \"true\" uncommented; container images are pinned and never auto-updated)"

echo "######## 7. state snapshot"
bash ~/ops-status.sh after-backup 2>&1 | sed -n '/== resource usage/,/== backups/p'
echo "######## DONE"
