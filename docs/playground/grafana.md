# Grafana OSS — playground note

**Status:** running on the NUC since 2026-10-15. Admin login and a query through the provisioned Prometheus data source work (checked through the HTTP API on the NUC). Dashboards and the browser UI **not yet tried**.

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
| Login (`POST /login`, the endpoint the login form uses) | ✅ HTTP 200 `Logged in` with the admin user from `.env` (password read into a shell variable, never printed). Wrong password → HTTP 401 |
| `GET /api/user` | ✅ `login=admin`, `isGrafanaAdmin=true` |
| Data source (provisioned) | ✅ one data source `Prometheus`, type `prometheus`, `http://prometheus:9090`, default |
| Data source health | ✅ `OK` — "Successfully queried the Prometheus API." |
| Query through the data source (`POST /api/ds/query`, `expr=up`, instant) | ✅ HTTP 200, three series (`prometheus`, `grafana`, `node`), value `1` each |
| Memory after 1 h | 98 MiB / 512 MiB |
| Browser UI through the SSH tunnel, dashboards | ⬜ not tried (no dashboards are provisioned) |

## Findings

- **Lab bug (fixed in this repo):** the stack used `grafana/grafana-oss:12`, which is **not published on Docker Hub** (Grafana publishes full versions such as `12.4.3`). `docker compose up` failed with `not found`, so the first start failed. The compose file now pins exact tags for all three images. This is our mistake, not an upstream bug.

## Upstream issues / PRs

- None.
