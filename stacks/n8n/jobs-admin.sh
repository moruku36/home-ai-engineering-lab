#!/usr/bin/env bash
# Admin helper for the GitHub monitoring job (runs on the NUC, in ~/home-ai-lab/n8n).
# Secrets are typed at a HIDDEN prompt, stored only in .env (chmod 600) and never printed.
#   ./jobs-admin.sh status
#   ./jobs-admin.sh set-github-token      read-only fine-grained PAT (see docs/github-monitoring.md for the exact permissions)
#   ./jobs-admin.sh check-github-token    calls GET /user with the stored token (prints login + rate limit only)
#   ./jobs-admin.sh remove-github-token
#   ./jobs-admin.sh set-kuma-push         paste the push URL (or token) of the Uptime Kuma push monitor
#   ./jobs-admin.sh remove-kuma-push
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
umask 077
[ -f .env ] || { echo ".env not found (run scripts/phase3-run.sh first)"; exit 1; }

setenv() {   # key value  (value may be empty -> line kept, value cleared)
  local tmp; tmp=$(mktemp .env.XXXXXX)
  grep -v "^$1=" .env > "$tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$tmp"
  chmod 600 "$tmp"; mv "$tmp" .env
}
getenv() { sed -n "s/^$1=//p" .env | head -1; }
apply() { sudo docker compose up -d python-jobs; }
bad_chars() { [[ "$1" =~ [[:space:]\;\$\"\'\`\\] ]]; }

case "${1:-}" in
  status)
    t=$(getenv GITHUB_TOKEN);     echo "github token : $([ -n "$t" ] && echo "configured (${#t} chars, value hidden)" || echo "not configured (public data only, 60 API calls/hour)")"
    k=$(getenv KUMA_PUSH_TOKEN);  echo "kuma push   : $([ -n "$k" ] && echo configured || echo "not configured (no heartbeat/alert push)")"
    echo "owners      : $(getenv GITHUB_OWNERS)"
    stat -c '.env mode %a owner %U' .env ;;
  set-github-token)
    read -rsp "Paste READ-ONLY fine-grained GitHub token (input hidden): " v; echo
    v=$(printf '%s' "$v" | tr -d '\r\n')
    if [ "${#v}" -lt 30 ] || bad_chars "$v" || ! [[ "$v" =~ ^(github_pat_|ghp_)[A-Za-z0-9_]+$ ]]; then
      echo "rejected: expected a GitHub token (github_pat_… / ghp_…) with no spaces or special characters"; unset v; exit 1
    fi
    case "$v" in ghp_*) echo "NOTE: this is a classic token. Prefer a fine-grained, read-only token (classic tokens cannot be limited per repository).";; esac
    setenv GITHUB_TOKEN "$v"; unset v
    apply; echo "GitHub token stored (not displayed). Run './jobs-admin.sh check-github-token' next." ;;
  check-github-token)
    sudo docker exec -i python-jobs python - <<'PY'
import os, json, urllib.request, urllib.error
t = os.environ.get("GITHUB_TOKEN", "")
if not t:
    raise SystemExit("no token configured")
req = urllib.request.Request("https://api.github.com/user", headers={"Authorization": "Bearer " + t, "Accept": "application/vnd.github+json", "User-Agent": "home-ai-lab-check"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print("token OK for GitHub user:", json.load(r).get("login"), "| rate limit:", r.headers.get("X-RateLimit-Limit"), "/h")
except urllib.error.HTTPError as e:
    print("token check failed: HTTP", e.code, "(expired, revoked or lacking access)")
PY
    ;;
  remove-github-token)
    setenv GITHUB_TOKEN ""; apply; echo "GitHub token removed from .env. Also revoke it in GitHub > Settings > Developer settings." ;;
  set-kuma-push)
    read -rsp "Paste the Kuma push URL (…/api/push/<token>?…) or just the token (input hidden): " v; echo
    t=$(printf '%s' "$v" | sed -n 's#.*/api/push/\([A-Za-z0-9]\{8,\}\).*#\1#p'); [ -n "$t" ] || t=$(printf '%s' "$v" | tr -d '\r\n[:space:]'); unset v
    if ! [[ "$t" =~ ^[A-Za-z0-9]{8,64}$ ]]; then echo "rejected: could not find a push token"; exit 1; fi
    setenv KUMA_PUSH_TOKEN "$t"; unset t
    apply; echo "Kuma push token stored (not displayed)." ;;
  remove-kuma-push)
    setenv KUMA_PUSH_TOKEN ""; apply; echo "Kuma push token removed." ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
