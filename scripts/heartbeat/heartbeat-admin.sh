#!/usr/bin/env bash
# Enable / disable the external heartbeat. On the NUC: bash heartbeat-admin.sh enable|disable|status
# `enable` asks for the ping URL at a HIDDEN prompt (create the free check yourself, e.g. at healthchecks.io;
# period 5 min, grace 15 min; add your e-mail as the alert channel there). Nothing is stored in Git.
set -euo pipefail
sudo -v
D=$(cd "$(dirname "$0")" && pwd)
case "${1:-status}" in
  enable)
    read -rsp "Paste the ping URL (https://…, input hidden): " u; echo
    u=$(printf '%s' "$u" | tr -d '\r\n[:space:]')
    [[ "$u" =~ ^https://[A-Za-z0-9._~:/?=\&%-]{12,200}$ ]] || { echo "rejected: expected an https URL"; exit 1; }
    sudo install -d -m 700 /etc/home-ai-lab
    printf '%s\n' "$u" | sudo tee /etc/home-ai-lab/heartbeat.url >/dev/null; sudo chmod 600 /etc/home-ai-lab/heartbeat.url; unset u
    sudo install -m 755 "$D/home-ai-lab-heartbeat.sh" /usr/local/sbin/home-ai-lab-heartbeat
    sudo tee /etc/systemd/system/home-ai-lab-heartbeat.service >/dev/null <<'U'
[Unit]
Description=home-ai-lab external heartbeat
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/home-ai-lab-heartbeat
U
    sudo tee /etc/systemd/system/home-ai-lab-heartbeat.timer >/dev/null <<'U'
[Unit]
Description=home-ai-lab external heartbeat every 5 min
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
U
    sudo systemctl daemon-reload; sudo systemctl enable --now home-ai-lab-heartbeat.timer
    sudo systemctl start home-ai-lab-heartbeat.service && echo "first ping sent (check the external dashboard)" ;;
  disable)
    sudo systemctl disable --now home-ai-lab-heartbeat.timer 2>/dev/null || true
    sudo rm -f /etc/systemd/system/home-ai-lab-heartbeat.{service,timer} /usr/local/sbin/home-ai-lab-heartbeat /etc/home-ai-lab/heartbeat.url
    sudo systemctl daemon-reload; echo "heartbeat removed (also delete the check at the provider)" ;;
  status)
    systemctl list-timers home-ai-lab-heartbeat.timer --no-pager 2>/dev/null | head -3
    [ -s /etc/home-ai-lab/heartbeat.url ] && echo "url: configured (hidden)" || echo "url: not configured (heartbeat inactive)"
    journalctl -t home-ai-lab-heartbeat --no-pager -n 5 2>/dev/null | cut -c1-160 ;;
  *) sed -n '2,5p' "$0"; exit 1 ;;
esac
