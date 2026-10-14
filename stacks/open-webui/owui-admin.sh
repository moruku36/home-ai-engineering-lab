#!/usr/bin/env bash
# Open WebUI admin helper (runs on the NUC). Keys are entered with a hidden prompt, stored only in
# secrets/<provider>.key (chmod 600) and rendered into .env. Nothing is printed or logged.
#   ./owui-admin.sh status
#   ./owui-admin.sh set-key openai|anthropic|gemini|runpod
#   ./owui-admin.sh remove-key <provider>
#   ./owui-admin.sh lock-signup | unlock-signup
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
umask 077
mkdir -p secrets config
chmod 700 secrets
declare -A BASE=( [openai]="https://api.openai.com/v1" [anthropic]="https://api.anthropic.com/v1" [gemini]="https://generativelanguage.googleapis.com/v1beta/openai" )
ORDER="openai anthropic gemini runpod"

runpod_base() { [ -s config/runpod.endpoint ] && echo "https://api.runpod.ai/v2/$(cat config/runpod.endpoint)/openai/v1" || true; }

render() {
  local urls="" keys="" n=0 b p tmp
  for p in $ORDER; do
    [ -s "secrets/$p.key" ] || continue
    if [ "$p" = runpod ]; then b=$(runpod_base); [ -n "$b" ] || continue; else b=${BASE[$p]}; fi
    urls+="${urls:+;}$b"; keys+="${keys:+;}$(cat "secrets/$p.key")"; n=$((n+1))
  done
  tmp=$(mktemp .env.XXXXXX)
  grep -vE '^(OPENAI_API_BASE_URLS|OPENAI_API_KEYS|ENABLE_OPENAI_API)=' .env > "$tmp" || true
  { echo "ENABLE_OPENAI_API=$([ "$n" -gt 0 ] && echo true || echo false)"
    echo "OPENAI_API_BASE_URLS=$urls"
    echo "OPENAI_API_KEYS=$keys"; } >> "$tmp"
  chmod 600 "$tmp"; mv "$tmp" .env
  echo "providers enabled: $n"
}
apply() { render; sudo docker compose up -d; }
valid_provider() { case " $ORDER " in *" $1 "*) ;; *) echo "unknown provider: $1 (use: $ORDER)"; exit 1;; esac; }

case "${1:-}" in
  status)
    for p in $ORDER; do
      if [ -s "secrets/$p.key" ]; then echo "$p: key configured ($(stat -c '%a' "secrets/$p.key"))"; else echo "$p: not configured"; fi
    done
    [ -s config/runpod.endpoint ] && echo "runpod endpoint id: set" || echo "runpod endpoint id: not set"
    echo "signup: $(sed -n 's/^ENABLE_SIGNUP=//p' .env)"
    stat -c '.env mode %a owner %U' .env ;;
  set-key)
    p=${2:-}; valid_provider "$p"
    if [ "$p" = runpod ]; then
      read -rp "RunPod serverless endpoint ID (not secret): " id
      [[ "$id" =~ ^[A-Za-z0-9]{6,40}$ ]] || { echo "invalid endpoint id"; exit 1; }
      printf '%s' "$id" > config/runpod.endpoint
    fi
    read -rsp "Paste $p API key (input hidden): " k; echo
    k=$(printf '%s' "$k" | tr -d '\r\n')
    if [ "${#k}" -lt 20 ] || [[ "$k" =~ [[:space:]\;\$\"\'\`\\] ]]; then
      echo "rejected: key too short or contains whitespace/; \$ quote backslash"; unset k; exit 1
    fi
    printf '%s' "$k" > "secrets/$p.key"; chmod 600 "secrets/$p.key"; unset k
    apply; echo "$p key stored (not displayed)." ;;
  remove-key)
    p=${2:-}; valid_provider "$p"
    if [ -f "secrets/$p.key" ]; then shred -u "secrets/$p.key" 2>/dev/null || rm -f "secrets/$p.key"; fi
    [ "$p" = runpod ] && rm -f config/runpod.endpoint
    apply; echo "$p removed. Also revoke the key in the provider console." ;;
  lock-signup)   sed -i 's/^ENABLE_SIGNUP=.*/ENABLE_SIGNUP=false/' .env; sudo docker compose up -d; echo "signup disabled" ;;
  unlock-signup) sed -i 's/^ENABLE_SIGNUP=.*/ENABLE_SIGNUP=true/' .env; sudo docker compose up -d; echo "signup enabled" ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
