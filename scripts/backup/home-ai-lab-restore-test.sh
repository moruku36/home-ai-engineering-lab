#!/usr/bin/env bash
# Restore test: decrypt newest backup, verify checksum, inspect DBs, boot throwaway Kuma and n8n on the
# restored data (no published ports, no network). Never touches the live volumes.
# usage: sudo home-ai-lab-restore-test.sh [identity-file]
set -euo pipefail
umask 077
DEST=/var/backups/home-ai-lab
ID=${1:-/etc/home-ai-lab/backup-identity.key}
KIMG=louislam/uptime-kuma:2
NIMG=n8nio/n8n:2.43.5
TK=kuma-restore-test
TN=n8n-restore-test
latest=$(ls -1t "$DEST"/home-ai-lab-*.tar.age | head -n1)
echo "restoring: $latest"
( cd "$DEST" && sha256sum -c "$(basename "$latest").sha256" )
work=$(mktemp -d)
cleanup() {
  docker rm -f $TK $TN >/dev/null 2>&1 || true
  docker volume rm $TK $TN >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT
age -d -i "$ID" "$latest" | tar -C "$work" -xf -
echo "--- archive members"; ls "$work"
mkdir "$work/cfg"; tar -C "$work/cfg" -xf "$work/config.tar"
echo "--- restored config files (secrets excluded from listing)"; find "$work/cfg" -type f ! -name '.env' | sed "s|$work/cfg/||"
[ -f "$work/cfg/home-ai-lab/n8n/.env" ] && echo ".env present: $(stat -c '%a' "$work/cfg/home-ai-lab/n8n/.env")"

restore_vol() {  # name archive
  mkdir "$work/$1"; tar -C "$work/$1" -xf "$work/$2.tar"
  docker volume create "$3" >/dev/null
  docker run --rm --user 0 -v "$3":/d -v "$work/$1":/src:ro --entrypoint sh "$KIMG" -c 'cp -a /src/. /d/'
}

echo "=== Kuma ==="
mkdir "$work/kdb"; tar -C "$work/kdb" -xf "$work/kuma-data.tar"
sqlite3 "$work/kdb/kuma.db" 'select id, name, type from monitor;'
restore_vol kuma kuma-data $TK
docker run -d --name $TK --network none -v $TK:/app/data "$KIMG" >/dev/null
for i in $(seq 1 30); do
  s=$(docker inspect -f '{{.State.Health.Status}}' $TK); echo "health: $s"; [ "$s" = healthy ] && break; sleep 5
done
[ "$s" = healthy ] || { echo "RESTORE TEST (kuma): FAIL"; docker logs --tail 30 $TK; exit 1; }
echo "RESTORE TEST (kuma): PASS"

if [ -f "$work/n8n-data.tar" ]; then
  echo "=== n8n ==="
  mkdir "$work/ndb"; tar -C "$work/ndb" -xf "$work/n8n-data.tar"
  echo "integrity: $(sqlite3 "$work/ndb/database.sqlite" 'pragma integrity_check;')"
  echo "workflows:"; sqlite3 "$work/ndb/database.sqlite" 'select id, name from workflow_entity;'
  echo "credentials (names only): $(sqlite3 "$work/ndb/database.sqlite" 'select count(*) from credentials_entity;')"
  restore_vol n8n n8n-data $TN
  docker run --rm --user 0 -v $TN:/d --entrypoint chown "$NIMG" -R 1000:1000 /d
  # key from the restored .env, passed via the environment without printing it
  KEY=$(sed -n 's/^N8N_ENCRYPTION_KEY=//p' "$work/cfg/home-ai-lab/n8n/.env")
  docker run -d --name $TN --network none -e N8N_ENCRYPTION_KEY="$KEY" -v $TN:/home/node/.n8n "$NIMG" >/dev/null
  unset KEY
  ok=0
  for i in $(seq 1 24); do
    if docker exec $TN wget -qO- http://127.0.0.1:5678/healthz >/dev/null 2>&1; then ok=1; break; fi
    echo "n8n: waiting"; sleep 5
  done
  if [ $ok = 1 ]; then
    echo "workflows via n8n CLI:"; docker exec $TN n8n list:workflow 2>/dev/null
    echo "RESTORE TEST (n8n): PASS"
  else
    echo "RESTORE TEST (n8n): FAIL"; docker logs --tail 30 $TN; exit 1
  fi
else
  echo "(no n8n-data.tar in this backup - older backup format)"
fi
echo "RESTORE TEST: PASS"
