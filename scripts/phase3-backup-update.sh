#!/usr/bin/env bash
# Install the extended backup/restore-test scripts (now incl. n8n + python-jobs volumes and n8n/.env),
# run one backup and one restore test. On the NUC: bash phase3-backup-update.sh  (scripts in ~/backup/)
set -euo pipefail
sudo -v
D=$(cd "$(dirname "$0")" && pwd)/backup
sudo install -m 755 "$D/home-ai-lab-backup.sh" /usr/local/sbin/home-ai-lab-backup
sudo install -m 755 "$D/home-ai-lab-restore-test.sh" /usr/local/sbin/home-ai-lab-restore-test
sudo /usr/local/sbin/home-ai-lab-backup
sudo /usr/local/sbin/home-ai-lab-restore-test
sudo ls -l /var/backups/home-ai-lab
sudo docker ps --format '{{.Names}} | {{.Status}}'
