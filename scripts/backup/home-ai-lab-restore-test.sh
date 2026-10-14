#!/usr/bin/env bash
# Restore test: decrypt newest backup, verify checksum, inspect DB, boot a throwaway Kuma on the
# restored data (no published port, isolated network). Never touches the live volume.
# usage: sudo home-ai-lab-restore-test.sh [identity-file]
set -euo pipefail
umask 077
DEST=/var/backups/home-ai-lab
ID=${1:-/etc/home-ai-lab/backup-identity.key}
IMG=louislam/uptime-kuma:2
T=kuma-restore-test
latest=$(ls -1t "$DEST"/home-ai-lab-*.tar.age | head -n1)
echo "restoring: $latest"
( cd "$DEST" && sha256sum -c "$(basename "$latest").sha256" )
work=$(mktemp -d)
cleanup() { docker rm -f $T >/dev/null 2>&1 || true; docker volume rm $T >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
age -d -i "$ID" "$latest" | tar -C "$work" -xf -
mkdir "$work/data" "$work/cfg"
tar -C "$work/data" -xf "$work/kuma-data.tar"
tar -C "$work/cfg" -xf "$work/config.tar"
echo "--- restored config files"; find "$work/cfg" -type f | sed "s|$work/cfg/||"
echo "--- restored monitors (from kuma.db)"
cp -r "$work/data" "$work/dbcopy"
sqlite3 "$work/dbcopy/kuma.db" 'select id, name, type from monitor;'
echo "--- boot throwaway Kuma on restored data"
docker volume create $T >/dev/null
docker run --rm -v $T:/d -v "$work/data":/src:ro --entrypoint sh "$IMG" -c 'cp -a /src/. /d/'
docker run -d --name $T --network none -v $T:/app/data "$IMG" >/dev/null
for i in $(seq 1 30); do
  s=$(docker inspect -f '{{.State.Health.Status}}' $T); echo "health: $s"; [ "$s" = healthy ] && break; sleep 5
done
[ "$s" = healthy ] && echo "RESTORE TEST: PASS" || { echo "RESTORE TEST: FAIL"; docker logs --tail 30 $T; exit 1; }
