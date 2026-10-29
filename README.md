# Home AI Engineering Lab

**English** | [日本語](README.ja.md)

A home Intel NUC lab for GitHub automation, monitoring and hands-on OSS experiments. The always-on platform uses Ubuntu Server and Docker Compose; a separate QEMU/KVM guest provides an offline security-analysis workspace.

The automation platform does not run an LLM or use paid LLM APIs. Open WebUI is intentionally stopped with its data retained. No additional paid service has been introduced (electricity and existing subscriptions excluded).

**Start here:** [Capabilities and status](#capabilities-and-status) · [Use the lab](#use-the-lab) · [Build or develop](#build-or-develop) · [Documentation index](docs/README.md)

## Capabilities and status

Based on repository code and recorded verification as of **2026-10-20 JST**, not a fresh check of the live NUC. Implementation, deployment and acceptance are separate milestones.

| Area | Available functionality | Recorded status / remaining gap |
|---|---|---|
| [GitHub daily report](docs/github-monitoring.md) | n8n → Python collector → Markdown/JSON; configured for 07:00 JST | Manual n8n execution verified. First scheduled run and its live failure cause unverified; source fix and freshness detector not deployed. |
| [Previous-day activity](docs/github-monitoring.md) | PR opened/merged/closed counts, Issue counts, repositories whose latest push falls in the previous JST day | Implemented in source; see the guide for verification scope. Push-event and commit counts not implemented. API coverage and search-index delay limit figures. |
| [Read-only MCP](docs/mcp-internal-api.md) | Authenticated, audited access to saved reports | Reading from n8n verified. Official client/Inspector compatibility and live negative tests unverified. |
| [Monitoring and notifications](docs/monitoring-notifications.md) | Uptime Kuma checks, collector push monitor, optional external heartbeat | Detection verified; notification channel and push token not configured. External heartbeat not enabled. |
| [Backup and restore](docs/backup-restore.md) | Encrypted local backup and restore test | Manual backup/restore verified. First automatic timer run unobserved; off-device copy missing. |
| [OSS playground](docs/playground.md) | Prometheus, Grafana, node_exporter, two-node kind cluster | Startup, scrape targets, Grafana API query and kind readiness verified. Browser dashboards and kind workloads unverified; Kyverno is design only. |
| [Network visibility](docs/network-visibility.md) | Host metrics, approved manual inventory, dashboard definition, limited DNS-trial template | Phase 1–2 implementation in progress; deployment/display unverified. IDS and blocking are future work. |
| [Security-analysis VM](docs/security-analysis-vm.md) | NIC-less guest, read-only ISO transfer, independent Workbench and REA/Ghidra tools | Scope A (VM foundation/basic operations) conditionally owner-accepted. Scope B (REA → Ghidra analysis capability) not accepted; original `FAIL` / `REPORT=UNVERIFIED` retained. |
| [Local GPU security analysis](docs/local-gpu-security-analysis-design.md) | Separate offline log preprocessing and optional LLM analysis design | Inactive Phase 1 proposal; synthetic validation only. No deployment or GPU benchmark. |
| [Open WebUI](docs/ops-runbook.md#1-open-webui-stop--start) | Preserved chat UI stack | Intentionally stopped; data retained. Real LLM API connections unverified. |

Detailed evidence: [build progress](docs/build-progress.md). Newer topic-specific records linked above take precedence over older build entries.

Latest maintenance record: [Brotli security response and n8n update, 2026-10-25](docs/brotli-n8n-update-2026-10-25.md) (Japanese; verified scope and remaining checks).

Shared configuration observations and Ansible integration status: [configuration status](docs/configuration-status.md).

Availability monitoring proposal: [Prometheus alerting candidate](docs/prometheus-alerts-candidate.md).

Custom component update review: [custom OSS candidate](docs/custom-oss-update-candidate.md).

## Architecture

| Layer | Components and boundary |
|---|---|
| Access | PC → SSH key authentication → NUC. Admin UIs bind to loopback and use SSH tunnels; no Internet-facing UI or router port forwarding. |
| Automation | n8n calls internal `python-jobs`; the collector reads GitHub and saves reports/snapshots. |
| Report access | n8n or a compatible client reads saved reports through the internal, read-only MCP server. |
| Observability | Kuma checks services; Prometheus/node_exporter feed Grafana. The network-visibility extension is not deployment-verified. |
| Recovery | Local `age`-encrypted backups; off-device destination undecided. Observability volumes are outside the existing encrypted backup. |
| Analysis | Separate QEMU/KVM guest with no virtual NIC. Workbench and REA are independent MCP servers; integration not implemented. |

[System, network and backup diagrams](docs/architecture.md) · [VM architecture and acceptance boundaries](docs/security-analysis-vm.md)

## Use the lab

Open a tunnel from your PC using your own account and NUC address. Real LAN addresses are intentionally omitted.

```bash
ssh -N -L 3001:127.0.0.1:3001 -L 5678:127.0.0.1:5678 -L 9090:127.0.0.1:9090 -L 3000:127.0.0.1:3000 <user>@<nuc-address>
```

| UI | Local URL | Guide |
|---|---|---|
| Uptime Kuma | <http://localhost:3001> | [Notifications and heartbeat](docs/monitoring-notifications.md) |
| n8n | <http://localhost:5678> | [GitHub report operations](docs/github-monitoring.md) |
| Prometheus | <http://localhost:9090> | [Prometheus notes](docs/playground/prometheus.md) |
| Grafana | <http://localhost:3000> | [Grafana notes](docs/playground/grafana.md) |

- **Generate a report:** n8n → `GitHub daily report (read-only)` → Execute. Unauthenticated API budgets can produce partial data; a fuller same-day report is protected from a poorer replacement.
- **Read a report:** n8n → `MCP read-only test`, or MCP `read_report` for `github-daily-latest.md`. [Synthetic report sample](docs/samples/github-daily-sample.md).
- **Investigate missing scheduled runs:** follow the read-only checks in [GitHub monitoring §11](docs/github-monitoring.md#11-scheduled-run-investigation-task-122-2026-10-18). Do not use the deployment script as a status check.
- **Stop/start, update or recover:** [operations runbook](docs/ops-runbook.md).

- **Explore REA use cases:** [Official guides, examples and resource map](docs/rea-usage-resources.md). Upstream capabilities are separate from this lab's unaccepted REA → Ghidra scope.

## Build or develop

1. **Rebuild the host:** [physical setup](docs/physical-setup-guide.md) → [implementation plan and phase results](docs/implementation-plan.md). These are rebuild records, not a one-command installer.
2. **Change a component:** inspect `stacks/`, `scripts/` and the relevant [topic guide](docs/README.md).
3. **Verify locally:** run relevant offline tests and the secret scan from the repository root. These do not prove deployment or live acceptance.

```bash
python3 -m unittest discover -s tests -p '*_test.py'
python3 tests/mcp_selftest.py
bash scripts/scan-secrets.sh
```

Setup and operations scripts can modify the host; read their runbooks before executing them on the NUC. Original stacks and the later playground use different deployment paths: see [operations](docs/ops-runbook.md) and [playground setup](docs/playground.md).

| Path | Contents |
|---|---|
| [`stacks/`](stacks/) | Compose stacks, workflows, collector, MCP, observability and kind definitions |
| [`scripts/`](scripts/) | Setup, operations, backup, heartbeat, network reports and secret scanning |
| [`tests/`](tests/) | Offline collector, freshness, MCP and network-visibility checks |
| [`docs/`](docs/README.md) | Design, topic runbooks, samples, progress and historical records |

## Operational priorities and boundaries

- Verify the scheduled GitHub run and deploy source fixes using the investigation guide.
- Configure notification delivery, collector push and optional external heartbeat; choose an [off-device backup destination](docs/offsite-backup-options.md).
- Keep network-visibility and VM acceptance gaps explicit; code or limited tool output is not proof of deployed functionality.
- Maintain SSH key-only access, loopback UIs and read-only collection. Never commit secrets, real LAN addresses, MACs or serial numbers. [Security operations](docs/security-operations.md).
- External writes, credentials, paid services and network changes follow their documented approval boundaries.

License: not yet specified.
