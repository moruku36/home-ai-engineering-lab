#!/usr/bin/env bash
# Rebuild/redeploy only the python-jobs container from ~/n8n-stack (code change). RUN_JOB=1 also runs the snapshot job once.
# On the NUC: bash ops-update-jobs.sh   (sudo password once). Does not touch other services or any data.
set -euo pipefail
sudo -v
APP=~/home-ai-lab
cp -r ~/n8n-stack/. "$APP/n8n/"
chmod +x "$APP/n8n/jobs-admin.sh"
cd "$APP/n8n"
sudo docker compose config -q && echo "compose OK"
sudo docker compose build python-jobs >/dev/null && echo "image built"
sudo docker compose up -d --force-recreate python-jobs
for i in $(seq 1 24); do s=$(sudo docker inspect -f '{{.State.Health.Status}}' python-jobs); echo "python-jobs: $s"; [ "$s" = healthy ] && break; sleep 5; done
./jobs-admin.sh status
if [ "${RUN_JOB:-0}" = 1 ]; then
echo "--- run the snapshot job once (RUN_JOB=1). Unauthenticated GitHub API: 60 calls/hour shared with your PC"
sudo docker exec -i python-jobs python - <<'PY'
import os, json, urllib.request, urllib.error
req = urllib.request.Request("http://127.0.0.1:8080/jobs/github-dev-snapshot", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + os.environ["JOBS_TOKEN"], "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=200) as r:
        d = json.load(r); print("HTTP", r.status); print(json.dumps({k: d.get(k) for k in ("ok", "partial", "kept_previous", "counts", "notes", "kuma_pushed")}, indent=1))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:300])
PY
fi
sudo docker exec python-jobs sh -c 'ls -l /data/reports | tail -4'
sudo docker ps -a --filter name=open-webui --format 'open-webui: {{.Status}}'
sudo docker ps --format '{{.Names}} | {{.Status}}'
echo "--- resource usage BEFORE the change (recorded while Open WebUI was still running)"
sed -n '/== host/,/== containers/p;/== resource usage/,/== docker disk/p' ~/ops-status-before-*.txt 2>/dev/null | head -24
echo "--- host memory / disk now"; free -h | head -2; df -h / | tail -1
