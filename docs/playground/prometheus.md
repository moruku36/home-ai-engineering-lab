# Prometheus (+ node-exporter) — playground note

**Status:** running on the NUC since 2026-10-15 (first start). Scraping of the targets is **not yet confirmed** (see below).

## Version tested

| Image | Tag | Digest |
|---|---|---|
| `prom/prometheus` | `v3.15.0` | `sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e` |
| `prom/node-exporter` | `v1.12.1` | `sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0` |

Stack: `stacks/observability`, started with `bash scripts/playground-run.sh observability` from a clone at `~/home-ai-engineering-lab` on the NUC.

## What was checked (2026-10-15, on the NUC)

| Check | Result |
|---|---|
| `GET /-/ready` from the host | ✅ HTTP 200 (also the script's in-container check: `prometheus: ready`) |
| Published port | ✅ `127.0.0.1:9090` only (`docker port`, `ss -ltn`) |
| node-exporter port | ✅ not published (`9100/tcp` inside the stack network only) |
| Memory | prometheus 31 MiB / 512 MiB limit, node-exporter 3.5 MiB / 128 MiB, a few seconds after start |
| Scrape targets (`prometheus`, `node`, `grafana`) | ⬜ **not confirmed**: queried 5 s after start, all three were still `health: unknown` (first scrape not done; interval 30 s). Check `http://localhost:9090/targets` through the SSH tunnel |

## Impressions

- Starting was uneventful once the image tags existed; the stack came up in seconds.

## Findings

- None in Prometheus itself yet.

## Upstream issues / PRs

- None.
