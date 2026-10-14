#!/usr/bin/env bash
# Stop / start / inspect Open WebUI WITHOUT touching its data. On the NUC: bash ops-open-webui.sh stop|start|status
#  stop   : `docker compose stop` - container, volume (chats/users), .env and secrets/ are all kept
#  start  : `docker compose start` - brings the same container back (use after `stop`)
#  status : shows container state, restart policy and the data volume
# Restart policy is `unless-stopped`: a container you stopped manually stays stopped after a reboot.
# Nothing here deletes anything. (Never use `docker compose down -v` - it would delete the volume.)
set -euo pipefail
cd ~/home-ai-lab/open-webui
sudo -v
case "${1:-status}" in
  stop)   sudo docker compose stop; echo "Open WebUI stopped. Data kept (volume open-webui_open-webui-data)." ;;
  start)  sudo docker compose start
          for i in $(seq 1 24); do s=$(sudo docker inspect -f '{{.State.Health.Status}}' open-webui 2>/dev/null || echo none); echo "open-webui: $s"; [ "$s" = healthy ] && break; sleep 5; done ;;
  status) ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
sudo docker ps -a --filter name=open-webui --format 'container: {{.Names}} | {{.Status}} | {{.Ports}}'
sudo docker inspect -f 'restart policy: {{.HostConfig.RestartPolicy.Name}} | running: {{.State.Running}}' open-webui
sudo docker volume ls --filter name=open-webui --format 'volume: {{.Name}}'
