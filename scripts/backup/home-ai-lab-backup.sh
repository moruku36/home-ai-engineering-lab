#!/usr/bin/env bash
# Encrypted local backup of compose definitions (+ .env secrets) and every data volume. Runs as root.
# Encrypts to the age PUBLIC key only: this host cannot decrypt without the separately-held identity.
#
# Services are stopped briefly so SQLite files are consistent. ONLY stacks that were running before the
# backup are stopped, and ONLY those are started again - a stack you stopped on purpose (e.g. Open WebUI)
# stays stopped, but its volume is still backed up.
set -euo pipefail
umask 077
SRC=/home/moruku/home-ai-lab
DEST=/var/backups/home-ai-lab
RECIP=/etc/home-ai-lab/backup-recipient.pub
IMG=louislam/uptime-kuma:2        # any image with tar; already present on the host
KEEP=${KEEP:-7}
# stack name -> compose file (stop order = listed order, start order = reverse)
STACKS="mcp:$SRC/mcp/compose.yaml open-webui:$SRC/open-webui/compose.yaml n8n:$SRC/n8n/compose.yaml uptime-kuma:$SRC/uptime-kuma/compose.yaml"
# name:volume pairs archived (volume names are compose-project prefixed)
VOLS="kuma-data:uptime-kuma_uptime-kuma-data n8n-data:n8n_n8n-data jobs-reports:n8n_jobs-reports jobs-state:n8n_jobs-state owui-data:open-webui_open-webui-data mcp-audit:mcp_mcp-audit"
ts=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$DEST"
work=$(mktemp -d "$DEST/.work.XXXXXX")

WAS_RUNNING=()
for s in $STACKS; do
  name=${s%%:*}; file=${s#*:}
  [ -f "$file" ] || continue
  if [ -n "$(docker compose -f "$file" ps --status running -q 2>/dev/null)" ]; then WAS_RUNNING+=("$name:$file"); else echo "not running before backup (left stopped): $name"; fi
done
restart_running() {
  local i s
  for ((i=${#WAS_RUNNING[@]}-1; i>=0; i--)); do
    s=${WAS_RUNNING[$i]}; docker compose -f "${s#*:}" start >/dev/null 2>&1 || echo "WARNING: could not start ${s%%:*}"
  done
  WAS_RUNNING=()
}
cleanup() { rm -rf "$work"; restart_running; }
trap cleanup EXIT

for s in "${WAS_RUNNING[@]}"; do docker compose -f "${s#*:}" stop >/dev/null; done
for pair in $VOLS; do
  name=${pair%%:*}; vol=${pair#*:}
  if docker volume inspect "$vol" >/dev/null 2>&1; then
    docker run --rm -v "$vol":/d:ro -v "$work":/out --entrypoint tar "$IMG" -C /d -cf "/out/$name.tar" .
  else
    echo "skip (volume not found): $vol"
  fi
done
tar -C "$(dirname "$SRC")" -cf "$work/config.tar" "$(basename "$SRC")"   # includes .env files and secrets/ (archive is encrypted)
restart_running

out="$DEST/home-ai-lab-$ts.tar.age"
( cd "$work" && tar -cf - *.tar ) | age -R "$RECIP" -o "$out"
( cd "$DEST" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256" )
echo "backup written: $out ($(du -h "$out" | cut -f1))"

# Retention: keep newest $KEEP backups.
ls -1t "$DEST"/home-ai-lab-*.tar.age | tail -n +$((KEEP+1)) | while read -r f; do
  echo "pruning old backup: $f"; rm -f -- "$f" "$f.sha256"
done
