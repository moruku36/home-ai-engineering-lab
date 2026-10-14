#!/usr/bin/env bash
# Re-apply the Kuma compose (default route pinned to the UFW-allowed subnet) and verify host:22 from the Kuma network.
# On the NUC: bash fix-kuma-gw.sh   (new compose in ~/kuma-compose.yaml)
set -euo pipefail
sudo -v
cp ~/kuma-compose.yaml ~/home-ai-lab/uptime-kuma/compose.yaml
cd ~/home-ai-lab/uptime-kuma
sudo docker compose config -q && echo "compose OK"
sudo docker compose up -d
for i in $(seq 1 24); do
  s=$(sudo docker inspect -f '{{.State.Health.Status}}' uptime-kuma); echo "kuma: $s"; [ "$s" = healthy ] && break; sleep 5
done
echo "--- default route inside Kuma (expect via 172.30.0.x)"
sudo docker exec uptime-kuma sh -c 'ip route 2>/dev/null | head -5 || cat /proc/net/route | head -5'
echo "--- host:22 reachability from Kuma (host.docker.internal)"
sudo docker exec uptime-kuma sh -c 'timeout 5 bash -c "echo > /dev/tcp/host.docker.internal/22" && echo REACHABLE || echo BLOCKED'
