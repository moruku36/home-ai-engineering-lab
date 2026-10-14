#!/usr/bin/env bash
# Encrypted local backup of compose definitions (+ .env secrets) and the Kuma / n8n / python-jobs
# data volumes. Runs as root. Encrypts to the age PUBLIC key only: this host cannot decrypt without
# the separately-held identity.
set -euo pipefail
umask 077
SRC=/home/moruku/home-ai-lab
KUMA_COMPOSE=$SRC/uptime-kuma/compose.yaml
N8N_COMPOSE=$SRC/n8n/compose.yaml
DEST=/var/backups/home-ai-lab
RECIP=/etc/home-ai-lab/backup-recipient.pub
IMG=louislam/uptime-kuma:2        # any image with tar; already present on the host
KEEP=${KEEP:-7}
# name:volume pairs archived (volume names are compose-project prefixed)
VOLS="kuma-data:uptime-kuma_uptime-kuma-data n8n-data:n8n_n8n-data jobs-reports:n8n_jobs-reports owui-data:open-webui_open-webui-data mcp-audit:mcp_mcp-audit"
WEBUI_COMPOSE=$SRC/open-webui/compose.yaml
MCP_COMPOSE=$SRC/mcp/compose.yaml
ts=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$DEST"
work=$(mktemp -d "$DEST/.work.XXXXXX")
start_all() {
  docker compose -f "$KUMA_COMPOSE" start >/dev/null 2>&1 || true
  [ -f "$N8N_COMPOSE" ] && docker compose -f "$N8N_COMPOSE" start >/dev/null 2>&1 || true
  [ -f "$WEBUI_COMPOSE" ] && docker compose -f "$WEBUI_COMPOSE" start >/dev/null 2>&1 || true
  [ -f "$MCP_COMPOSE" ] && docker compose -f "$MCP_COMPOSE" start >/dev/null 2>&1 || true
}
cleanup() { rm -rf "$work"; start_all; }
trap cleanup EXIT

# Stop services briefly so SQLite DBs (+WAL) are copied consistently.
[ -f "$N8N_COMPOSE" ] && docker compose -f "$N8N_COMPOSE" stop
[ -f "$WEBUI_COMPOSE" ] && docker compose -f "$WEBUI_COMPOSE" stop
[ -f "$MCP_COMPOSE" ] && docker compose -f "$MCP_COMPOSE" stop
docker compose -f "$KUMA_COMPOSE" stop
for pair in $VOLS; do
  name=${pair%%:*}; vol=${pair#*:}
  if docker volume inspect "$vol" >/dev/null 2>&1; then
    docker run --rm -v "$vol":/d:ro -v "$work":/out --entrypoint tar "$IMG" -C /d -cf "/out/$name.tar" .
  else
    echo "skip (volume not found): $vol"
  fi
done
tar -C "$(dirname "$SRC")" -cf "$work/config.tar" "$(basename "$SRC")"   # includes n8n/.env and open-webui/{.env,secrets/} (secrets; archive is encrypted)
start_all

out="$DEST/home-ai-lab-$ts.tar.age"
( cd "$work" && tar -cf - *.tar ) | age -R "$RECIP" -o "$out"
( cd "$DEST" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256" )
echo "backup written: $out ($(du -h "$out" | cut -f1))"

# Retention: keep newest $KEEP backups.
ls -1t "$DEST"/home-ai-lab-*.tar.age | tail -n +$((KEEP+1)) | while read -r f; do
  echo "pruning old backup: $f"; rm -f -- "$f" "$f.sha256"
done
