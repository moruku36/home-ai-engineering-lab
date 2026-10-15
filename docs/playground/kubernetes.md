# Kubernetes (kind) — playground note

**Status:** cluster `playground` (1 control-plane + 1 worker) created on the NUC on 2026-10-15 with `bash scripts/playground-run.sh kubernetes`. Both nodes `Ready`, API server on `127.0.0.1:6443` only.

## Version tested

| Component | Version |
|---|---|
| kind | `v0.27.0` (go1.23.6, pinned in `scripts/playground-run.sh`) |
| Node image | `kindest/node:v1.32.2` (kind's default for v0.27.0; now pinned by digest in the script) |
| Kubernetes server | `v1.32.2`, containerd `2.0.2`, Debian 12 node image |
| kubectl (client) | `v1.37.1` in this run (the script then installed the current `stable.txt` release). The script now pins `v1.32.13` — fixed in repo, not re-run on the NUC |

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

- **Lab issue (fixed in repo, not re-run on the NUC): kubectl/server version skew.** The script installed the latest stable kubectl (`v1.37.1`), while kind `v0.27.0` creates a `v1.32.2` cluster. kubectl only supports ±1 minor version against the API server, so this was outside the supported range (basic `get` commands still worked). The script now pins `KUBECTL_VERSION=v1.32.13` (sha256-checked as before) and passes `--image kindest/node:v1.32.2@sha256:f226…3142f` to `kind create`, so the three versions are changed together. An already-installed kubectl of a different version (such as the `v1.37.1` on the NUC) is replaced on the next run.
- **Worker `NotReady` right after the script (fixed in repo, not re-run on the NUC).** `--wait 180s` waits for the control-plane only, so the script's `kubectl get nodes` could show the worker as `NotReady`. It became `Ready` within about 1.5 min. The script now runs `kubectl wait --for=condition=Ready node --all --timeout=180s` before `kubectl get nodes`, and prints `kubectl version` (client and server) at the end.
- Nodes run as privileged containers on the NUC's Docker (by design of kind). Treat the cluster as disposable.

## Upstream issues / PRs

- None.
