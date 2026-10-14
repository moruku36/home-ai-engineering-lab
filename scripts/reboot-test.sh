#!/usr/bin/env bash
# Reboot test. On NUC: bash reboot-test.sh pre   (snapshot, then reboots)
#                     bash reboot-test.sh post  (snapshot after boot, diff vs before)
set -uo pipefail
snap() {
  echo "boot_id=$(cat /proc/sys/kernel/random/boot_id)"; uptime -p
  echo "--- services"; for s in ssh docker containerd ufw; do echo "$s enabled=$(systemctl is-enabled $s) active=$(systemctl is-active $s)"; done
  echo "--- sshd"; sudo sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication) '
  echo "--- ufw"; sudo ufw status numbered
  echo "--- containers"; sudo docker ps -a --format '{{.Names}} | {{.Status}} | {{.Ports}}'
  echo "--- listeners (3001 must be 127.0.0.1 only; no 2375/2376)"; sudo ss -tlnp | grep -E ':(22|3001|2375|2376)\b'
  echo "--- kuma data"; sudo docker run --rm -v uptime-kuma_uptime-kuma-data:/d:ro --entrypoint sh louislam/uptime-kuma:2 -c 'ls -l /d | grep -Ei "kuma|sqlite|db"; ' 2>&1 | awk '{print $5, $9}'
}
case "${1:-}" in
pre)  sudo -v; snap > ~/reboot-before.txt; cat ~/reboot-before.txt; echo ">>> rebooting in 5s"; sleep 5; sudo systemctl reboot ;;
post) sudo -v; snap > ~/reboot-after.txt; cat ~/reboot-after.txt
      echo "=== DIFF (expect only boot_id/uptime/Status-time/size lines) ==="; diff ~/reboot-before.txt ~/reboot-after.txt || true ;;
*) echo "usage: $0 pre|post"; exit 1;;
esac
