#!/usr/bin/env bash
# Phase 2-C driver (re-runnable). Run on NUC from ~/ : bash phase2c-run.sh
# Installs age+sqlite3, creates key pair if absent (prints PUBLIC key only), installs scripts and a
# daily systemd timer, runs one backup, then a restore test.
set -euo pipefail
sudo -v
D=$(cd "$(dirname "$0")" && pwd)/backup
sudo apt-get install -y age sqlite3
sudo install -d -m 700 /etc/home-ai-lab /var/backups/home-ai-lab
if [ ! -f /etc/home-ai-lab/backup-identity.key ]; then
  sudo sh -c 'umask 077; age-keygen -o /etc/home-ai-lab/backup-identity.key 2>/dev/null'
  echo ">>> NEW identity created (private key NOT shown). Copy it to your password manager (see docs)."
fi
sudo sh -c 'age-keygen -y /etc/home-ai-lab/backup-identity.key > /etc/home-ai-lab/backup-recipient.pub'
echo "recipient (public): $(sudo cat /etc/home-ai-lab/backup-recipient.pub)"
sudo install -m 755 "$D/home-ai-lab-backup.sh" /usr/local/sbin/home-ai-lab-backup
sudo install -m 755 "$D/home-ai-lab-restore-test.sh" /usr/local/sbin/home-ai-lab-restore-test
sudo tee /etc/systemd/system/home-ai-lab-backup.service >/dev/null <<'U'
[Unit]
Description=home-ai-lab encrypted local backup
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/home-ai-lab-backup
U
sudo tee /etc/systemd/system/home-ai-lab-backup.timer >/dev/null <<'U'
[Unit]
Description=Daily home-ai-lab backup
[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=10min
Persistent=true
[Install]
WantedBy=timers.target
U
sudo systemctl daemon-reload
sudo systemctl enable --now home-ai-lab-backup.timer
systemctl list-timers home-ai-lab-backup.timer --no-pager
sudo /usr/local/sbin/home-ai-lab-backup
sudo /usr/local/sbin/home-ai-lab-restore-test
sudo ls -l /var/backups/home-ai-lab
