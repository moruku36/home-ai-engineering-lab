#!/usr/bin/env bash
# Phase 5 driver (re-runnable). On the NUC: bash phase5-run.sh
# Needs in $HOME: mcp-stack/ n8n-compose.yaml webui-compose.yaml kuma-compose.yaml
# - creates the INTERNAL network mcp-net, generates mcp/.env (chmod 600, values never printed)
# - builds/starts mcp-server (no published ports), attaches n8n / Open WebUI / Kuma to mcp-net
# - imports the n8n credential + read-only test workflow, then runs exposure/isolation checks
set -euo pipefail
sudo -v
APP=~/home-ai-lab
mkdir -p "$APP/mcp"
cp -r ~/mcp-stack/. "$APP/mcp/"
cp ~/n8n-compose.yaml "$APP/n8n/compose.yaml"
cp ~/webui-compose.yaml "$APP/open-webui/compose.yaml"
cp ~/kuma-compose.yaml "$APP/uptime-kuma/compose.yaml"
cd "$APP/mcp"

if [ ! -f .env ]; then
  ( umask 077
    { echo "MCP_TOKEN_N8N=$(openssl rand -hex 32)"
      echo "MCP_TOKEN_OPENWEBUI=$(openssl rand -hex 32)"; } > .env )
  echo ">>> .env generated (values not shown)"
fi
if [ "${ROTATE_MCP_TOKENS:-0}" = 1 ]; then
  sed -i "s/^MCP_TOKEN_N8N=.*/MCP_TOKEN_N8N=$(openssl rand -hex 32)/; s/^MCP_TOKEN_OPENWEBUI=.*/MCP_TOKEN_OPENWEBUI=$(openssl rand -hex 32)/" .env
  echo ">>> MCP tokens rotated (values not shown)"
fi
chmod 600 .env; stat -c '%a %U %n' .env

sudo docker network inspect mcp-net >/dev/null 2>&1 || sudo docker network create --internal --subnet 172.32.0.0/24 mcp-net >/dev/null
sudo docker compose config -q && echo "compose OK"
sudo docker compose build mcp-server
# audit dir must be writable by the non-root user (idempotent)
sudo docker compose up --no-start mcp-server
sudo docker run --rm --user 0 -v mcp_mcp-audit:/d --entrypoint chown home-ai-lab/mcp-server:1 -R 10002 /d
sudo docker compose up -d --force-recreate mcp-server
for i in $(seq 1 24); do
  s=$(sudo docker inspect -f '{{.State.Health.Status}}' mcp-server); echo "mcp-server: $s"; [ "$s" = healthy ] && break; sleep 5
done
# clients join mcp-net (recreates them briefly)
( cd "$APP/n8n" && sudo docker compose up -d )
( cd "$APP/open-webui" && sudo docker compose up -d )
( cd "$APP/uptime-kuma" && sudo docker compose up -d )
for i in $(seq 1 36); do
  if sudo docker exec n8n wget -qO- http://127.0.0.1:5678/healthz >/dev/null 2>&1; then echo "n8n: healthz OK"; break; fi
  echo "n8n: waiting"; sleep 5
done

# --- import n8n credential + workflow (token via shell variable only, never echoed) ---
TOKEN=$(sed -n 's/^MCP_TOKEN_N8N=//p' .env)
printf '[{"id":"mcptoken0000001","name":"mcp token (n8n)","type":"httpHeaderAuth","data":{"name":"Authorization","value":"Bearer %s"}}]' "$TOKEN" \
  | sudo docker exec -i n8n sh -c 'cat > /tmp/cred.json'
unset TOKEN
sudo docker cp workflows/mcp-readonly-test.json n8n:/tmp/wf.json
sudo docker exec n8n n8n import:credentials --input=/tmp/cred.json 2>&1 | grep -v 'license SDK'
sudo docker exec n8n n8n import:workflow --input=/tmp/wf.json 2>&1 | grep -v 'license SDK'
sudo docker exec n8n rm -f /tmp/cred.json /tmp/wf.json

echo; echo "=================== EXPOSURE / ISOLATION CHECKS ==================="
echo "--- 1. published ports of mcp-server (expect: empty)"
sudo docker port mcp-server || true
echo "ports json: $(sudo docker inspect -f '{{json .NetworkSettings.Ports}}' mcp-server)"
echo "--- 2. host listeners owned by docker-proxy (expect only 127.0.0.1 ports; none for mcp)"
sudo ss -tlnp | grep docker-proxy | awk '{print $4}' | sort
echo "--- 3. mcp-net is internal; attached containers"
sudo docker network inspect mcp-net -f 'internal={{.Internal}} subnet={{range .IPAM.Config}}{{.Subnet}}{{end}} members={{range .Containers}}{{.Name}} {{end}}'
echo "--- 4. mcp-server egress (expect all BLOCKED)"
sudo docker exec -i mcp-server python - <<'PY'
import socket
for host, port in [("1.1.1.1", 443), ("api.github.com", 443), ("172.17.0.1", 22)]:
    s = socket.socket(); s.settimeout(4)
    try:
        s.connect((host, port)); print(f"{host}:{port} REACHABLE  <-- unexpected")
    except Exception as e:
        print(f"{host}:{port} BLOCKED ({type(e).__name__})")
    finally:
        s.close()
PY
echo "--- 5. unauthenticated access from client containers (expect healthz 200, /mcp 401)"
echo -n "n8n healthz: "; sudo docker exec n8n wget -qO- http://mcp-server:8080/healthz; echo
echo -n "n8n POST no token: "; sudo docker exec n8n sh -c "wget -S -O /dev/null --post-data='{}' --header='Content-Type: application/json' http://mcp-server:8080/mcp 2>&1 | grep -m1 'HTTP/'"
sudo docker exec -i open-webui python - <<'PY'
import urllib.request, urllib.error
for path, data in [("/healthz", None), ("/mcp", b"{}")]:
    try:
        r = urllib.request.urlopen(urllib.request.Request("http://mcp-server:8080" + path, data=data), timeout=5); c = r.status
    except urllib.error.HTTPError as e:
        c = e.code
    print(f"open-webui -> {path}: {c}")
PY
echo "--- 6. other containers must NOT see mcp-server (python-jobs, expect unresolved)"
sudo docker exec python-jobs python -c "import socket; socket.gethostbyname('mcp-server'); print('RESOLVED <-- unexpected')" 2>&1 | tail -1 || true
echo "--- 7. Kuma default route + host:22 still OK (lesson from Phase 3/4)"
sudo docker exec uptime-kuma sh -c 'ip route | head -3; timeout 5 bash -c "echo > /dev/tcp/host.docker.internal/22" && echo "host:22 REACHABLE" || echo "host:22 BLOCKED"'
echo "--- 8. UFW unchanged"
sudo ufw status numbered
echo "--- 9. audit log (last 6 lines; no tokens/argument values)"
sudo docker exec mcp-server sh -c 'tail -n 6 /var/log/mcp/audit.jsonl'
echo "--- containers"
sudo docker ps --format '{{.Names}} | {{.Status}} | {{.Ports}}'
echo "=== DONE ==="
