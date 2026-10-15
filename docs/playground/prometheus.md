# Prometheus (+ node-exporter) — playground note

**Status:** running on the NUC since 2026-10-15. All three scrape targets (`prometheus`, `node`, `grafana`) are `up` (checked about 1 h after start).

## Version tested

| Image | Tag | Digest |
|---|---|---|
| `prom/prometheus` | `v3.15.0` | `sha256:efd719c99d83b060d9daefdcf00360461adf279f45ef5391f8d111892118753e` |
| `prom/node-exporter` | `v1.12.1` | `sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0` |

Stack: `stacks/observability`, started with `bash scripts/playground-run.sh observability` from a clone at `~/home-ai-engineering-lab` on the NUC.

## What was checked (2026-10-15, on the NUC)

| Check | Result |
|---|---|
| Clone synced to `main` (`52e156e`, after PR #8); `docker compose up -d` recreated nothing | ✅ |
| `GET /-/ready` from the host | ✅ HTTP 200 (also the script's in-container check: `prometheus: ready`) |
| Published port | ✅ `127.0.0.1:9090` only (`docker port`, `ss -ltn`) |
| node-exporter port | ✅ not published (`9100/tcp` inside the stack network only) |
| Memory | prometheus 31 MiB / 512 MiB limit, node-exporter 3.5 MiB / 128 MiB, a few seconds after start |
| Scrape targets (`prometheus`, `node`, `grafana`) | ✅ all `health: up`, `lastError` empty (`GET /api/v1/targets`, about 1 h after start). Scrape durations 6 ms / 37 ms / 11 ms. Right after start (5 s) they were still `unknown` because the first scrape (interval 30 s) had not run |
| `up` query | ✅ `GET /api/v1/query?query=up` → `1` for all three jobs |
| Memory after 1 h | prometheus 51 MiB / 512 MiB, node-exporter 9 MiB / 128 MiB |
| Web UI in a browser (`/targets` through the SSH tunnel) | ⬜ not opened; checked through the HTTP API on the NUC only |

## Impressions

- Starting was uneventful once the image tags existed; the stack came up in seconds.

## Findings

- None in Prometheus itself yet.

## Upstream issues / PRs

- None.
