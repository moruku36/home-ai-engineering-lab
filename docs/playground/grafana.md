# Grafana OSS — playground note

**Status:** running on the NUC since 2026-10-15 (first start). UI login and dashboards **not yet tried**.

## Version tested

| Image | Tag | Digest |
|---|---|---|
| `grafana/grafana-oss` | `12.4.3` (commit `86c83248`) | `sha256:2e986801428cd689c2358605289c90ab37d2b39e24808874971f54c99bcdc412` |

Stack: `stacks/observability`. The admin password is generated into `stacks/observability/.env` (`chmod 600`, git-ignored, never printed).

## What was checked (2026-10-15, on the NUC)

| Check | Result |
|---|---|
| `GET /api/health` from the host | ✅ `"database": "ok"`, `"version": "12.4.3"` |
| Published port | ✅ `127.0.0.1:3000` only (`docker port`, `ss -ltn`) |
| Memory | 108 MiB / 512 MiB limit, a few seconds after start |
| Login, Prometheus data source, dashboards | ⬜ not tried yet |

## Findings

- **Lab bug (fixed in this repo):** the stack used `grafana/grafana-oss:12`, which is **not published on Docker Hub** (Grafana publishes full versions such as `12.4.3`). `docker compose up` failed with `not found`, so the first start failed. The compose file now pins exact tags for all three images. This is our mistake, not an upstream bug.

## Upstream issues / PRs

- None.
