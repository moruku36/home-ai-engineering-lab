#!/usr/bin/env bash
# Phase 2-A: preflight + Docker Engine/Compose install (Ubuntu 24.04). Re-runnable.
# Run on the NUC:  bash phase2a-docker.sh   (prompts for sudo password once)
# Does NOT add any user to the docker group, and does NOT touch UFW/SSH/LVM.
set -euo pipefail
sudo -v

echo "=== PREFLIGHT (read-only) ==="
hostnamectl | sed -n '1,8p'
lscpu | grep -E 'Model name|^CPU\(s\)'
free -h
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
df -h /
sudo vgs; sudo lvs
sudo sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication) '
sudo ufw status verbose
for p in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  dpkg -s "$p" >/dev/null 2>&1 && echo "CONFLICT installed: $p" || true
done

echo "=== DOCKER OFFICIAL APT REPO ==="
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "=== VERIFY ==="
sudo systemctl enable --now docker containerd
systemctl is-enabled docker; systemctl is-active docker
sudo docker --version
sudo docker compose version
sudo docker run --rm hello-world
sudo docker info --format 'DockerRootDir={{.DockerRootDir}} Driver={{.Driver}}'
sudo du -sh /var/lib/docker; df -h /var/lib/docker
sudo ss -tlnp | grep -E 'dockerd|:2375|:2376' || echo "no docker TCP listener (good)"
echo "=== DONE ==="
