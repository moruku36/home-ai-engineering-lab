#!/usr/bin/env bash
# Deploy: stop Open WebUI (data kept) + GitHub monitoring job + daily-report workflow. Re-runnable.
# On the NUC:  bash ops-deploy.sh      (needs ~/n8n-stack uploaded; asks for the sudo password once)
set -euo pipefail
sudo -v
APP=~/home-ai-lab

echo "######## 0. state BEFORE changes"
bash ~/ops-status.sh before >/dev/null 2>&1 || true
echo "(saved ~/ops-status-before-*.txt)"

echo "######## 1. stop Open WebUI (nothing deleted)"
( cd "$APP/open-webui" && sudo docker compose stop )
sudo docker ps -a --filter name=open-webui --format '{{.Names}} | {{.Status}}'
sudo docker volume ls --filter name=open-webui --format 'volume kept: {{.Name}}'

echo "######## 1b. install the fixed backup scripts NOW (the old one would restart Open WebUI at the next nightly run)"
sudo install -m 755 ~/backup/home-ai-lab-backup.sh /usr/local/sbin/home-ai-lab-backup
sudo install -m 755 ~/backup/home-ai-lab-restore-test.sh /usr/local/sbin/home-ai-lab-restore-test
grep -c "left stopped" /usr/local/sbin/home-ai-lab-backup | sed 's/^/new backup script installed (marker lines: /;s/$/)/'

echo "######## 2. update n8n stack (python-jobs + GitHub snapshot)"
cp -r ~/n8n-stack/. "$APP/n8n/"
chmod +x "$APP/n8n/jobs-admin.sh"
cd "$APP/n8n"
grep -q '^GITHUB_OWNERS=' .env || echo "GITHUB_OWNERS=moruku36" >> .env
chmod 600 .env
sudo docker compose config -q && echo "compose OK"
sudo docker compose build python-jobs
sudo docker compose up --no-start python-jobs
sudo docker run --rm --user 0 -v n8n_jobs-state:/d -v n8n_jobs-reports:/r --entrypoint chown home-ai-lab/python-jobs:1 -R 10001 /d /r
sudo docker compose up -d --force-recreate python-jobs
for i in $(seq 1 24); do s=$(sudo docker inspect -f '{{.State.Health.Status}}' python-jobs); echo "python-jobs: $s"; [ "$s" = healthy ] && break; sleep 5; done

echo "######## 3. import + activate the daily workflow"
sudo docker cp workflows/github-daily-report.json n8n:/tmp/gdr.json
sudo docker exec n8n n8n import:workflow --input=/tmp/gdr.json 2>&1 | grep -v 'license SDK'
sudo docker exec n8n rm -f /tmp/gdr.json
( sudo docker exec n8n n8n publish:workflow --id=GithubDailyRpt01 2>&1 || sudo docker exec n8n n8n update:workflow --id=GithubDailyRpt01 --active=true 2>&1 ) | grep -v 'license SDK' || true
sudo docker restart n8n >/dev/null
for i in $(seq 1 36); do sudo docker exec n8n wget -qO- http://127.0.0.1:5678/healthz >/dev/null 2>&1 && { echo "n8n: healthz OK"; break; }; sleep 5; done
sudo docker exec n8n n8n list:workflow 2>&1 | grep -v 'license SDK'
sudo docker exec n8n sh -c 'n8n list:workflow --active=true 2>&1 | grep -v "license SDK"' || true

echo "######## 4. run the snapshot job once (inside python-jobs; token read from its env, never printed)"
sudo docker exec -i python-jobs python - <<'PY'
import os, json, urllib.request, urllib.error
req = urllib.request.Request("http://127.0.0.1:8080/jobs/github-dev-snapshot", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + os.environ["JOBS_TOKEN"], "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=200) as r:
        print("HTTP", r.status); print(json.dumps(json.load(r), indent=1)[:1500])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:400])
PY
echo "--- report files (names only)"; sudo docker exec python-jobs sh -c 'ls -l /data/reports | tail -5; ls -l /data/state/snapshots | tail -3'
echo "--- first 40 lines of latest report"; sudo docker exec python-jobs sh -c 'head -40 /data/reports/github-daily-latest.md'

echo "######## 5. services + resources AFTER"
bash ~/ops-status.sh after | sed -n '/== containers/,/== docker disk/p'
echo "######## DONE"
