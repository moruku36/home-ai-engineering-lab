#!/usr/bin/env bash
# Record service state and resource usage (read-only). On the NUC: bash ops-status.sh [label]
# Output is also saved to ~/ops-status-<label>-<timestamp>.txt (contains no secrets).
set -uo pipefail
sudo -v
label=${1:-snapshot}
out=~/ops-status-$label-$(date -u +%Y%m%dT%H%M%SZ).txt
{
echo "== time (UTC)";           date -u
echo "== host";                 uptime; free -h | head -2; df -h / | tail -2
echo "== containers (all, incl. stopped)"; sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "== restart policy / state"; for c in $(sudo docker ps -aq); do sudo docker inspect -f '{{.Name}} restart={{.HostConfig.RestartPolicy.Name}} running={{.State.Running}}' "$c"; done
echo "== resource usage (running containers)"; sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}'
echo "== docker disk usage"; sudo docker system df
echo "== volumes"; sudo docker system df -v | sed -n '/Local Volumes space usage/,/^$/p'
echo "== container log sizes (json-file, rotated 10m x 3)"; for c in $(sudo docker ps -aq); do p=$(sudo docker inspect -f '{{.LogPath}}' "$c"); n=$(sudo docker inspect -f '{{.Name}}' "$c"); echo "$n $(sudo du -sh "$p" 2>/dev/null | cut -f1)"; done
echo "== journald";             journalctl --disk-usage
echo "== backups";              sudo ls -l /var/backups/home-ai-lab 2>/dev/null; sudo du -sh /var/backups/home-ai-lab 2>/dev/null
echo "== timers";               systemctl list-timers --no-pager 2>/dev/null | grep -E "NEXT|home-ai-lab|apt-daily|unattended" || true
echo "== backup service journal (last 15)"; journalctl -u home-ai-lab-backup --no-pager -n 15 2>&1 | cut -c1-200
echo "== automatic updates";    apt-config dump | grep -E "^APT::Periodic::(Update-Package-Lists|Unattended-Upgrade)|Unattended-Upgrade::Automatic-Reboot " ; ls /var/run/reboot-required 2>/dev/null && echo "REBOOT REQUIRED" || echo "no reboot pending"
echo "== last unattended-upgrades log"; sudo tail -n 5 /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null | cut -c1-200
echo "== UFW";                  sudo ufw status numbered
echo "== host listeners (TCP)"; sudo ss -tln | awk 'NR==1 || /LISTEN/' | awk '{print $4}' | sort -u | tr '\n' ' '; echo
} 2>&1 | tee "$out"
echo; echo "saved: $out"
