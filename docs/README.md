# Documentation index / ドキュメント索引

English first, Japanese second. "Language" tells you what the document is written in.
英語が先、日本語が後。「言語」はその文書の記述言語です。

## Start here / まずここから

| Doc | Language | About / 内容 |
|---|---|---|
| [../README.md](../README.md) | EN + JA | What the lab is, what it can do, architecture, status / 全体像・できること・構成図・状態 |
| [use-cases.md](use-cases.md) | EN + JA | Use cases with verified status / 用途と検証状態 |
| [architecture.md](architecture.md) | EN + JA | System, network, data-flow and backup diagrams / 各種構成図 |
| [github-monitoring.md](github-monitoring.md) | EN + JA | The daily GitHub report: scope, API budget, token, alerts / GitHub日次レポート |
| [monitoring-notifications.md](monitoring-notifications.md) | EN + JA | Alert policy, notification channels, external heartbeat / 通知と外部監視 |
| [ops-runbook.md](ops-runbook.md) | EN + JA | Stop/start, resource baseline, updates, manual recovery / 運用手順書 |
| [offsite-backup-options.md](offsite-backup-options.md) | EN + JA | Off-device backup options (no decision made) / NUC外バックアップの選択肢 |
| [playground.md](playground.md) | EN + JA | OSS playground: Prometheus, Grafana, Kubernetes (kind) / OSSプレイグラウンド |
| [playground-kyverno-design.md](playground-kyverno-design.md) | EN + JA | Design for adding Kyverno (not implemented) / Kyverno追加の設計（未実装） |

## Planning & Inactive designs / 計画・提案段階の設計

| Doc | Language | About / 内容 |
|---|---|---|
| [local-gpu-security-analysis-design.md](local-gpu-security-analysis-design.md) | JA + EN | Local GPU AI security log analysis architecture and security boundaries / ローカルGPU AI セキュリティログ解析の設計と境界 |
| [local-gpu-deployment-guide.md](local-gpu-deployment-guide.md) | JA + EN | Inactive deployment guide, tunnel setup, and deployment gates / デプロイ手順案・トンネル設計・承認ゲート |
| [local-gpu-ops-runbook.md](local-gpu-ops-runbook.md) | JA + EN | Operations runbook, handling Windows offline, human triage / 運用手順書・Windows停止時対応・トリアージ |
| [local-gpu-benchmark-results.md](local-gpu-benchmark-results.md) | JA + EN | Unmeasured status, confirmed specs, and future benchmark protocol / ベンチマーク結果（未測定）と測定プロトコル案 |

## Operations (current) / 運用（最新）

| Doc | Language | About / 内容 |
|---|---|---|
| [security-operations.md](security-operations.md) | JA | Security controls, credential handling, what to do if a secret leaks / セキュリティ運用・漏えい時の対応 |
| [security-analysis-vm.md](security-analysis-vm.md) | JA | Dedicated security analysis VM design and phases / 専用セキュリティ解析VMの設計と段階 |
| [ai-api-key-management.md](ai-api-key-management.md) | JA | Storing / rotating LLM API keys, cost limits. **Open WebUI is stopped, so this is parked** / APIキー管理（Open WebUI停止中のため保留） |
| [mcp-internal-api.md](mcp-internal-api.md) | JA | MCP server design, controls, verification / MCPの設計・制御・検証 |
| [backup-restore.md](backup-restore.md) | JA | Backup, restore test, recovery / バックアップ・復元・復旧 |
| [build-progress.md](build-progress.md) | JA | Checklist, final report, incidents, open items / チェックリスト・最終報告・障害記録・残課題 |

## Build records / 構築記録

| Doc | Language | Status |
|---|---|---|
| [implementation-plan.md](implementation-plan.md) | JA | Runbook plus per-phase results (Phase 2–5 results appended at the end) / ランブックと各フェーズの結果 |
| [physical-setup-guide.md](physical-setup-guide.md) | JA | Hardware and Ubuntu installation (done; kept for rebuilds). Example IPs there are placeholders / 物理セットアップ（完了済み・再構築用。IPは例） |

## Historical / 過去の資料

| Doc | Why |
|---|---|
| [next-thread-master-prompt.md](next-thread-master-prompt.md) | Old hand-off prompt, **outdated** (predates Docker). Not the current state / 古い引き継ぎプロンプト。**現状と異なる** |

## Samples / サンプル

- [samples/github-daily-sample.md](samples/github-daily-sample.md) — a **synthetic** daily GitHub report (fake data) / 合成データの日次レポート例

## Rules for documents / 文書のルール

- **EN:** Never put secrets, real LAN addresses, MACs or serial numbers here. Mark anything unverified as unverified.
- **JA:** 秘密情報・実際のLANアドレス・MAC・シリアルは書かない。未検証のものは未検証と明記する。
- Check before committing / コミット前の確認: `bash scripts/scan-secrets.sh`
