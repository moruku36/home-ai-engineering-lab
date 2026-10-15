#!/usr/bin/env bash
# Playground driver (re-runnable). On the NUC: bash scripts/playground-run.sh [observability|kubernetes|all|status|down]
# - observability: Prometheus + Grafana + node-exporter (stacks/observability), loopback-only UIs
# - kubernetes:    kind cluster "playground" (1 control-plane + 1 worker), API on 127.0.0.1:6443
# Uptime Kuma is already part of the lab (stacks/uptime-kuma). Secrets are generated locally, never printed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KIND_VERSION="${KIND_VERSION:-v0.27.0}"
BIN="${BIN:-/usr/local/bin}"
D="sudo docker"

obs_up() {
  cd "$ROOT/stacks/observability"
  if [ ! -f .env ]; then
    ( umask 077
      { echo "GF_SECURITY_ADMIN_USER=admin"
        echo "GF_SECURITY_ADMIN_PASSWORD=$(openssl rand -hex 16)"; } > .env )
    echo ">>> .env generated (value not shown; read it with: sudo -u \$USER cat $PWD/.env)"
  fi
  chmod 600 .env
  $D network inspect monitor-net >/dev/null 2>&1 || $D network create monitor-net >/dev/null
  $D compose config -q && echo "compose OK"
  $D compose up -d
  for i in $(seq 1 24); do
    if $D exec prometheus wget -qO- http://127.0.0.1:9090/-/ready >/dev/null 2>&1; then echo "prometheus: ready"; break; fi
    echo "prometheus: waiting"; sleep 5
  done
  for i in $(seq 1 24); do
    if $D exec grafana wget -qO- http://127.0.0.1:3000/api/health 2>/dev/null | grep -q '"database": "ok"'; then echo "grafana: ok"; break; fi
    echo "grafana: waiting"; sleep 5
  done
  echo "--- published ports (expect 127.0.0.1 only)"; $D port prometheus; $D port grafana
}

install_bin() { # name url sha256_url
  [ -x "$BIN/$1" ] && return 0
  local t; t="$(mktemp -d)"
  curl -fsSL "$2" -o "$t/$1"
  local want; want="$(curl -fsSL "$3" | awk '{print $1}')"
  echo "$want  $t/$1" | sha256sum -c - >/dev/null || { echo "checksum mismatch for $1" >&2; exit 1; }
  sudo install -m 0755 "$t/$1" "$BIN/$1"; rm -rf "$t"
}

k8s_up() {
  install_bin kind "https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64" "https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64.sha256sum"
  local kv; kv="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
  install_bin kubectl "https://dl.k8s.io/release/$kv/bin/linux/amd64/kubectl" "https://dl.k8s.io/release/$kv/bin/linux/amd64/kubectl.sha256"
  if sudo kind get clusters 2>/dev/null | grep -qx playground; then echo "cluster exists"; else
    sudo kind create cluster --name playground --config "$ROOT/stacks/kubernetes/kind-config.yaml" --wait 180s
  fi
  sudo kind get kubeconfig --name playground > "$HOME/.kube-playground" 2>/dev/null || true
  chmod 600 "$HOME/.kube-playground" 2>/dev/null || true
  KUBECONFIG="$HOME/.kube-playground" kubectl get nodes -o wide
  echo "--- API server listener (expect 127.0.0.1:6443 only)"; ss -ltn | grep 6443 || true
}

status() {
  $D ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|prometheus|grafana|node-exporter|uptime-kuma|playground' || true
}

down() {
  ( cd "$ROOT/stacks/observability" && $D compose down )   # volumes kept
  sudo kind delete cluster --name playground 2>/dev/null || true
}

case "${1:-all}" in
  observability) obs_up ;;
  kubernetes) k8s_up ;;
  all) obs_up; k8s_up; status ;;
  status) status ;;
  down) down ;;
  *) echo "usage: $0 [observability|kubernetes|all|status|down]" >&2; exit 2 ;;
esac
