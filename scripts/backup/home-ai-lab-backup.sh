#!/usr/bin/env bash
# Encrypted local backup of compose definitions + Uptime Kuma data volume. Runs as root.
# Encrypts to the age PUBLIC key only: this host cannot decrypt without the separately-held identity.
set -euo pipefail
umask 077
SRC=/home/moruku/home-ai-lab
COMPOSE=$SRC/uptime-kuma/compose.yaml
DEST=/var/backups/home-ai-lab
RECIP=/etc/home-ai-lab/backup-recipient.pub
VOL=uptime-kuma_uptime-kuma-data
IMG=louislam/uptime-kuma:2
KEEP=${KEEP:-7}
ts=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$DEST"
work=$(mktemp -d "$DEST/.work.XXXXXX")
cleanup() { rm -rf "$work"; docker compose -f "$COMPOSE" start >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Stop Kuma briefly so the SQLite DB (+WAL) is copied consistently.
docker compose -f "$COMPOSE" stop
docker run --rm -v "$VOL":/d:ro -v "$work":/out --entrypoint tar "$IMG" -C /d -cf /out/kuma-data.tar .
tar -C "$(dirname "$SRC")" -cf "$work/config.tar" "$(basename "$SRC")"
docker compose -f "$COMPOSE" start >/dev/null

out="$DEST/home-ai-lab-$ts.tar.age"
tar -C "$work" -cf - kuma-data.tar config.tar | age -R "$RECIP" -o "$out"
( cd "$DEST" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256" )
echo "backup written: $out ($(du -h "$out" | cut -f1))"

# Retention: keep newest $KEEP backups.
ls -1t "$DEST"/home-ai-lab-*.tar.age | tail -n +$((KEEP+1)) | while read -r f; do
  echo "pruning old backup: $f"; rm -f -- "$f" "$f.sha256"
done
