# Kubernetes (kind) — playground note

**Status:** cluster `playground` (1 control-plane + 1 worker) created on the NUC on 2026-10-15 with `bash scripts/playground-run.sh kubernetes`. Both nodes `Ready`, API server on `127.0.0.1:6443` only.

## Version tested

| Component | Version |
|---|---|
| kind | `v0.27.0` (go1.23.6, pinned in `scripts/playground-run.sh`) |
| Node image | `kindest/node:v1.32.2` (kind's default for v0.27.0) |
| Kubernetes server | `v1.32.2`, containerd `2.0.2`, Debian 12 node image |
| kubectl (client) | `v1.37.1` (the script installs the current `stable.txt` release) |

Config: `stacks/kubernetes/kind-config.yaml`. Kubeconfig: `~/.kube-playground` (mode `-rw-------`).

## What was checked (2026-10-15, on the NUC)

| Check | Result |
|---|---|
| Cluster creation | ✅ `kind create cluster --wait 180s` finished; control-plane `Ready after 7s` |
| Nodes | ✅ both `Ready` about 1.5 min after creation (`kubectl get nodes`). Right after the script, the worker was still `NotReady` (see findings) |
| System pods | ✅ all 11 pods in `kube-system` and `local-path-storage` `1/1 Running` (coredns ×2, etcd, kindnet ×2, kube-apiserver, kube-controller-manager, kube-proxy ×2, kube-scheduler, local-path-provisioner) |
| API listener | ✅ `127.0.0.1:6443` only (`ss -ltnp`: `docker-proxy`; `docker port playground-control-plane` → `6443/tcp -> 127.0.0.1:6443`) |
| Memory | control-plane 489 MiB, worker 113 MiB (no container limit; the limit column shows the host's 30.98 GiB). Host used memory 1.6 → 2.2 GiB of 31 GiB, about 2 min after creation |
| Workloads, Ingress, NetworkPolicy, upgrades | ⬜ not tried |

## Impressions

- Creation took a few minutes, most of it pulling `kindest/node`. Much lighter than the 1.5–2 GB estimated in the docs: about 0.6 GiB for two idle nodes.

## Findings

- **Lab issue (not fixed yet): kubectl/server version skew.** The script installs the latest stable kubectl (`v1.37.1`), while kind `v0.27.0` creates a `v1.32.2` cluster. kubectl only supports ±1 minor version against the API server, so this is outside the supported range. Basic `get` commands worked. Fix options: pin kubectl to the cluster's minor version, or bump kind (and the node image) together with kubectl.
- **Worker `NotReady` right after the script.** `--wait 180s` waits for the control-plane only, so the script's `kubectl get nodes` can show the worker as `NotReady`. It became `Ready` within about 1.5 min. Not a bug, but the script output looks like a failure; waiting with `kubectl wait --for=condition=Ready node --all` would make it clearer.
- Nodes run as privileged containers on the NUC's Docker (by design of kind). Treat the cluster as disposable.

## Upstream issues / PRs

- None.
