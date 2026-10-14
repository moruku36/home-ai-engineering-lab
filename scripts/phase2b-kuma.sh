#!/usr/bin/env bash
# Phase 2-B: start Uptime Kuma (re-runnable). Run on the NUC: bash phase2b-kuma.sh
set -euo pipefail
cd ~/home-ai-lab/uptime-kuma
sudo docker compose config -q && echo "compose OK"
sudo docker compose pull
sudo docker compose up -d
for i in $(seq 1 30); do
  s=$(sudo docker inspect -f '{{.State.Health.Status}}' uptime-kuma 2>/dev/null || echo none)
  echo "health: $s"; [ "$s" = healthy ] && break; sleep 5
done
sudo docker ps --filter name=uptime-kuma --format '{{.Names}} {{.Status}} {{.Ports}}'
echo "--- listening sockets on 3001 (expect 127.0.0.1 only) ---"
sudo ss -tlnp | grep 3001
curl -fsS -o /dev/null -w "local HTTP %{http_code}\n" http://127.0.0.1:3001/
