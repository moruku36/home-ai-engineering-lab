#!/usr/bin/env bash
# Phase 4 driver (re-runnable). On the NUC: bash phase4-run.sh   (stack files in ~/webui-stack)
# Deploys Open WebUI (loopback only), generates ~/home-ai-lab/open-webui/.env (chmod 600, values not shown),
# starts it WITHOUT any provider key, then verifies listeners and that provider endpoints are reachable
# (credential-free requests only; a 401/403 means "reachable, key required").
set -euo pipefail
sudo -v
APP=~/home-ai-lab/open-webui
mkdir -p "$APP"
cp -r ~/webui-stack/. "$APP/"
chmod +x "$APP/owui-admin.sh"
cd "$APP"
if [ ! -f .env ]; then
  ( umask 077; { echo "WEBUI_SECRET_KEY=$(openssl rand -hex 32)"; echo "ENABLE_SIGNUP=true"; } > .env )
  echo ">>> .env generated (values not shown)"
fi
chmod 600 .env
mkdir -p secrets config; chmod 700 secrets
./owui-admin.sh status | tail -3
sudo docker network inspect monitor-net >/dev/null 2>&1 || sudo docker network create --subnet 172.31.0.0/24 monitor-net >/dev/null
# first run only: provider lines start empty (owui-admin.sh set-key renders them later)
grep -q '^OPENAI_API_KEYS=' .env || printf 'ENABLE_OPENAI_API=false\nOPENAI_API_BASE_URLS=\nOPENAI_API_KEYS=\n' >> .env
sudo docker compose config -q && echo "compose OK"
sudo docker compose pull
sudo docker compose up -d
for i in $(seq 1 60); do
  s=$(sudo docker inspect -f '{{.State.Health.Status}}' open-webui 2>/dev/null || echo none); echo "open-webui: $s"
  [ "$s" = healthy ] && break; sleep 5
done
echo "=== VERIFY ==="
sudo docker ps --filter name=open-webui --format '{{.Names}} | {{.Status}} | {{.Ports}}'
echo "--- listeners (8300 must be 127.0.0.1 only)"; sudo ss -tlnp | grep -E ':8300\b'
echo "--- /health from inside the container"; sudo docker exec open-webui python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8080/health',timeout=5).read().decode())"
echo "--- provider endpoint reachability (no credentials sent; 401/403/404 = reachable)"
sudo docker exec -i open-webui python - <<'PY'
import urllib.request, urllib.error
urls = {
 "openai":    "https://api.openai.com/v1/models",
 "anthropic": "https://api.anthropic.com/v1/models",
 "gemini":    "https://generativelanguage.googleapis.com/v1beta/openai/models",
 "runpod":    "https://api.runpod.ai/v2/",
}
for name, u in urls.items():
    try:
        code = urllib.request.urlopen(u, timeout=10).status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        code = type(e).__name__
    print(f"{name:10} {code}")
PY
echo "--- env hardening visible in container (names only)"
sudo docker exec open-webui sh -c 'env | grep -E "^(ENABLE_PERSISTENT_CONFIG|ENABLE_OLLAMA_API|ANONYMIZED_TELEMETRY|DO_NOT_TRACK|DEFAULT_USER_ROLE|ENABLE_OPENAI_API|ENABLE_SIGNUP)="'
echo "=== DONE ==="
