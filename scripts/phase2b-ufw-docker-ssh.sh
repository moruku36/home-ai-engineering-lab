#!/usr/bin/env bash
# Allow ONLY the Uptime Kuma Docker network (pinned 172.30.0.0/24) to reach host TCP/22
# so the "NUC SSH (host)" TCP monitor works. Run on NUC: bash phase2b-ufw-docker-ssh.sh [apply|rollback]
set -euo pipefail
SUBNET=172.30.0.0/24
COMMENT="uptime-kuma-to-host-ssh"
case "${1:-}" in
apply)
  sudo -v
  sudo mkdir -p /root/ufw-backup
  sudo cp -a /etc/ufw/user.rules /etc/ufw/user6.rules "/root/ufw-backup/" 2>/dev/null || true
  sudo ufw status numbered > /tmp/ufw-before.txt; cat /tmp/ufw-before.txt
  # 1) recreate Kuma on the pinned subnet (volume/data is preserved)
  cd ~/home-ai-lab/uptime-kuma
  sudo docker compose up -d --force-recreate
  sudo docker network inspect uptime-kuma_default -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
  # 2) add the single rule
  sudo ufw allow from "$SUBNET" to any port 22 proto tcp comment "$COMMENT"
  sudo ufw status numbered
  echo "Verify in Kuma: 'NUC SSH (host)' should turn Up within ~60s."
  ;;
rollback)
  sudo -v
  sudo ufw delete allow from "$SUBNET" to any port 22 proto tcp
  sudo ufw status numbered
  echo "Rolled back. (Compose pinned subnet is harmless; revert compose.yaml in git if desired.)"
  ;;
*) echo "usage: $0 apply|rollback"; exit 1;;
esac
