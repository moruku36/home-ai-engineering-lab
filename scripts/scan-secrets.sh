#!/usr/bin/env bash
# Scan this repository for credentials and private identifiers BEFORE committing/pushing.
#   bash scripts/scan-secrets.sh             # tracked + staged files
#   bash scripts/scan-secrets.sh --history   # every commit on every ref (slow, thorough)
# Exit code 1 if anything suspicious is found. Matches are printed with the secret part masked.
# This is a safety net, not a guarantee: GitHub secret scanning is also enabled on the repo.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

# High-confidence credential shapes
SECRET_RE='[0-9a-fA-F]{40,}|Bearer [A-Za-z0-9._~+/=-]{16,}|sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AGE-SECRET-KEY-[A-Z0-9]+|age1[a-z0-9]{50,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ssh-(ed25519|rsa) AAAA[0-9A-Za-z+/]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|rpa_[A-Za-z0-9]{20,}|(password|passwd|secret|token|api[_-]?key)[ \t]*[=:][ \t]*["'"'"']?[A-Za-z0-9/+_.-]{16,}'
# Private identifiers: host-specific LAN addresses (a bare /NN network such as 192.168.x.0/24 is allowed), MAC addresses
ID_RE='\b(192\.168|10\.[0-9]{1,3})\.[0-9]{1,3}\.[0-9]{1,3}\b(?!/)|\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
# File names that should never be committed
NAME_RE='(^|/)(\.env(\..*)?|id_(rsa|ed25519|ecdsa)(\.pub)?|.*\.(pem|key|ppk|p12|pfx|sqlite3?|db))$|(^|/)secrets/|backup-identity'

# Known harmless examples / documentation placeholders
ALLOW='192\.168\.1\.50|\.env\.example|<64 hex|<[a-z-]+>|github_pat_TESTTOKEN0123456789abcdef|^docs/playground/[^:]+:[0-9]+:.*`sha256:[0-9a-f]{64}`|^scripts/playground-run\.sh:[0-9]+:.*kindest/node:v[0-9.]+@sha256:[0-9a-f]{64}'   # dummy token used only by tests/github_snapshot_test.py; public container image digests in playground notes and the pinned kind node image

FLAG=$(mktemp -u)   # report() runs inside pipelines (subshells), so signal findings via a file
trap 'rm -f "$FLAG"' EXIT
report() { # label, lines on stdin  -> mask long tokens
  local out
  out=$(grep -vE "$ALLOW" | sed -E 's/([A-Za-z0-9+/_=-]{6})[A-Za-z0-9+/_=-]{10,}/\1…[masked]/g' | cut -c1-200)
  if [ -n "$out" ]; then echo "== $1"; echo "$out"; : > "$FLAG"; fi
}

if [ "${1:-}" = "--history" ]; then
  echo "Scanning ALL commits on ALL refs…"
  for c in $(git rev-list --all); do
    git grep -InE "$SECRET_RE" "$c" -- . 2>/dev/null | sed "s/^\(.\{8\}\)[0-9a-f]*:/\1:/" | report "secret-like text (commit ${c:0:8})"
    git grep -InP "$ID_RE" "$c" -- . 2>/dev/null | sed "s/^\(.\{8\}\)[0-9a-f]*:/\1:/" | report "private identifier (commit ${c:0:8})"
  done
  git log --all --name-only --pretty=format: | sort -u | grep -E "$NAME_RE" | grep -vE "$ALLOW" | report "sensitive file names ever committed"
else
  FILES=$( (git ls-files; git diff --cached --name-only) | sort -u)
  echo "$FILES" | grep -E "$NAME_RE" | grep -vE "$ALLOW" | report "sensitive file names tracked/staged"
  # shellcheck disable=SC2086
  git grep -InE "$SECRET_RE" -- $FILES 2>/dev/null | report "secret-like text"
  git grep -InP "$ID_RE" -- $FILES 2>/dev/null | report "private identifier"
fi

if [ ! -e "$FLAG" ]; then echo "OK: nothing suspicious found."; exit 0; fi
echo; echo "FOUND suspicious content. If a real secret was committed: ROTATE it first, then remove it (see docs/security-operations.md)."
exit 1
