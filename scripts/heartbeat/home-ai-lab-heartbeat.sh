#!/usr/bin/env bash
# Dead-man's-switch heartbeat to an EXTERNAL free monitor (e.g. Healthchecks.io). Runs as root every 5 minutes.
# It only sends an OUTBOUND HTTPS request - nothing is opened on the NUC.
#   healthy  -> GET <url>          (the external service marks the check "up")
#   unhealthy-> GET <url>/fail     (the external service alerts you immediately)
#   no ping at all for longer than the check's grace period -> the external service alerts you (NUC/network/power is down)
# The ping URL is a secret-ish capability URL: it lives only in /etc/home-ai-lab/heartbeat.url (root, 600).
set -uo pipefail
URL_FILE=/etc/home-ai-lab/heartbeat.url
[ -s "$URL_FILE" ] || exit 0                       # not configured -> do nothing
URL=$(head -n1 "$URL_FILE")
ok=1
systemctl is-active --quiet docker || ok=0
systemctl is-active --quiet ssh.socket || systemctl is-active --quiet ssh || ok=0
[ "$(docker inspect -f '{{.State.Health.Status}}' uptime-kuma 2>/dev/null)" = healthy ] || ok=0   # Kuma itself is watched from outside
if [ "$ok" = 1 ]; then T="$URL"; else T="${URL%/}/fail"; fi
curl -fsS -m 10 --retry 3 --retry-delay 2 -o /dev/null "$T" || logger -t home-ai-lab-heartbeat "ping failed (ok=$ok)"
