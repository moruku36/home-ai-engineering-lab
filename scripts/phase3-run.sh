#!/usr/bin/env bash
# Phase 3 driver (re-runnable). On the NUC: bash phase3-run.sh   (stack files must be in ~/n8n-stack, kuma compose in ~/kuma-compose.yaml)
# - creates shared monitor network, generates ~/home-ai-lab/n8n/.env (chmod 600, values never printed)
# - re-creates Kuma attached to monitor-net, builds + starts python-jobs and n8n
# - imports the python-jobs credential + read-only sample workflow
set -euo pipefail
sudo -v
APP=~/home-ai-lab
mkdir -p "$APP/n8n"
cp -r ~/n8n-stack/. "$APP/n8n/"
cp ~/kuma-compose.yaml "$APP/uptime-kuma/compose.yaml"
cd "$APP/n8n"

if [ ! -f .env ]; then
  ( umask 077
    { echo "N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)"
      echo "JOBS_TOKEN=$(openssl rand -hex 32)"
      echo "ALLOWED_REPOS=moruku36/home-ai-engineering-lab"; } > .env )
  echo ">>> .env generated (values not shown)"
fi
if [ "${ROTATE_JOBS_TOKEN:-0}" = 1 ]; then
  sed -i "s/^JOBS_TOKEN=.*/JOBS_TOKEN=$(openssl rand -hex 32)/" .env
  echo ">>> JOBS_TOKEN rotated (value not shown)"
fi
chmod 600 .env
stat -c '%a %U %n' .env

sudo docker network inspect monitor-net >/dev/null 2>&1 || sudo docker network create --subnet 172.31.0.0/24 monitor-net >/dev/null
( cd "$APP/uptime-kuma" && sudo docker compose up -d )

sudo docker compose config -q && echo "compose OK"
sudo docker compose build python-jobs
sudo docker compose pull n8n
sudo docker compose up --no-start python-jobs   # ensures volume exists
# reports volume must be writable by the non-root job user (idempotent)
sudo docker run --rm --user 0 -v n8n_jobs-reports:/d --entrypoint chown home-ai-lab/python-jobs:1 -R 10001 /d
sudo docker compose up -d --force-recreate python-jobs
sudo docker compose up -d
for i in $(seq 1 24); do
  s=$(sudo docker inspect -f '{{.State.Health.Status}}' python-jobs); echo "python-jobs: $s"
  [ "$s" = healthy ] && break; sleep 5
done
for i in $(seq 1 36); do
  if sudo docker exec n8n wget -qO- http://127.0.0.1:5678/healthz >/dev/null 2>&1; then echo "n8n: healthz OK"; break; fi
  echo "n8n: waiting"; sleep 5
done

# --- import credential + workflow (token handled via shell variable, never echoed) ---
TOKEN=$(sed -n 's/^JOBS_TOKEN=//p' .env)
printf '[{"id":"pjtoken00000001","name":"python-jobs token","type":"httpHeaderAuth","data":{"name":"Authorization","value":"Bearer %s"}}]' "$TOKEN" \
  | sudo docker exec -i n8n sh -c 'cat > /tmp/cred.json'
unset TOKEN
sudo docker cp workflows/github-repo-readonly.json n8n:/tmp/wf.json
sudo docker exec n8n n8n import:credentials --input=/tmp/cred.json
sudo docker exec n8n n8n import:workflow --input=/tmp/wf.json
sudo docker exec n8n rm -f /tmp/cred.json /tmp/wf.json

echo "=== VERIFY ==="
sudo docker ps --filter name=n8n --filter name=python-jobs --filter name=uptime-kuma --format '{{.Names}} | {{.Status}} | {{.Ports}}'
echo "--- listeners (5678 must be 127.0.0.1 only)"; sudo ss -tlnp | grep -E ':(5678|3001)\b'
echo "--- python-jobs auth + jobs (token read inside container, not printed)"
sudo docker exec -i python-jobs python - <<'PY'
import os, json, urllib.request, urllib.error
def call(path, hdr=None, body=b"{}"):
    r = urllib.request.Request("http://127.0.0.1:8080" + path, data=body, headers=hdr or {}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=30) as x: return x.status, json.load(x)
    except urllib.error.HTTPError as e: return e.code, json.load(e)
t = {"Authorization": "Bearer " + os.environ["JOBS_TOKEN"]}
print("no token       ->", call("/jobs/github-repo-metadata")[0], "(expect 401)")
print("bad repo fmt   ->", call("/jobs/github-repo-metadata", t, b'{"repo":"../x"}')[0], "(expect 400)")
print("not allowlisted->", call("/jobs/github-repo-metadata", t, b'{"repo":"torvalds/linux"}')[0], "(expect 403)")
print("unknown job    ->", call("/jobs/nope", t)[0], "(expect 404)")
s, b = call("/jobs/github-repo-metadata", t, b'{"repo":"moruku36/home-ai-engineering-lab"}')
print("allowed repo   ->", s, b.get("data", b).get("full_name") if s == 200 else b)
PY
echo "--- n8n health"; sudo docker exec n8n wget -qO- http://127.0.0.1:5678/healthz; echo
echo "--- n8n workflows"; sudo docker exec n8n n8n list:workflow
echo "=== DONE ==="
