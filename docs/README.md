# Documentation index / ドキュメント索引

English first, Japanese second. "Language" tells you what the document is written in.
英語が先、日本語が後。「言語」はその文書の記述言語です。

[English overview](../README.md) · [日本語の概要](../README.ja.md)

README pages are separate; topic guides retain their existing languages.
READMEは言語別ページです。詳細資料は各資料の既存の言語で記載しています。

Latest improvement record / 最新の改善記録：[2026-11-09 クロッチの改善記録](kurotchi-improvements-2026-11-09.ja.md)（JA）。Verified branch push/CI and repaired lounge reception/scheduled delivery; merge approval and natural-language sharing remain under verification. / ブランチ push・CI とラウンジ受信・定期配送の修復を確認。マージ承認と自然文での状態共有は検証継続中。

Construction report / 構築レポート：[2026-11-08 ホームラボとクロッチの構築レポート](home-lab-kurotchi-build-report-2026-11-08.ja.md)（JA）。NUC lessons, CLI generation, GitHub test results, lounge reception, and unresolved approval registration. / NUC の構築経験、CLI 生成、GitHub 専用試験、ラウンジ受信と未解決の承認登録問題。Full operations acceptance remains incomplete. / 正式な運用受入れは未完了。

Earlier integration record / 以前の連携記録：[2026-11-06 OpenClaw／クロッチ導入・検証記録](openclaw-status-2026-11-06.ja.md)（JA）。

## Start here / まずここから

| Doc | Language | About / 内容 |
|---|---|---|
| [English README](../README.md) · [日本語 README](../README.ja.md) | EN / JA | What the lab is, what it can do, architecture, status / 全体像・できること・構成図・状態 |
| [use-cases.md](use-cases.md) | EN + JA | Use cases with verified status / 用途と検証状態 |
| [architecture.md](architecture.md) | EN + JA | System, network, data-flow and backup diagrams / 各種構成図 |
| [github-monitoring.md](github-monitoring.md) | EN + JA | The daily GitHub report: scope, API budget, token, alerts / GitHub日次レポート |
| [monitoring-notifications.md](monitoring-notifications.md) | EN + JA | Alert policy, notification channels, external heartbeat / 通知と外部監視 |
| [ops-runbook.md](ops-runbook.md) | EN + JA | Stop/start, resource baseline, updates, manual recovery / 運用手順書 |
| [offsite-backup-options.md](offsite-backup-options.md) | EN + JA | Off-device backup options (no decision made) / NUC外バックアップの選択肢 |
| [playground.md](playground.md) | EN + JA | OSS playground: Prometheus, Grafana, Kubernetes (kind) / OSSプレイグラウンド |
| [playground-kyverno-design.md](playground-kyverno-design.md) | EN + JA | Design for adding Kyverno (not implemented) / Kyverno追加の設計（未実装） |

## REA reference / REA の参照資料

| Doc | Language | About / 内容 |
|---|---|---|
| [rea-usage-resources.md](rea-usage-resources.md) | EN + JA | Official resources, concrete uses and community discovery; separate from local validation / 公式リンク・用途別事例・コミュニティ一覧。ラボの検証状態とは区別 |

## Planning & Inactive designs / 計画・提案段階の設計

| Doc | Language | About / 内容 |
|---|---|---|
| [local-gpu-security-analysis-design.md](local-gpu-security-analysis-design.md) | JA + EN | Local GPU AI security log analysis architecture and security boundaries / ローカルGPU AI セキュリティログ解析の設計と境界 |
| [local-gpu-deployment-guide.md](local-gpu-deployment-guide.md) | JA + EN | Inactive deployment guide, tunnel setup, and deployment gates / デプロイ手順案・トンネル設計・承認ゲート |
| [local-gpu-ops-runbook.md](local-gpu-ops-runbook.md) | JA + EN | Operations runbook, handling Windows offline, human triage / 運用手順書・Windows停止時対応・トリアージ |
| [local-gpu-benchmark-results.md](local-gpu-benchmark-results.md) | JA + EN | Unmeasured status, confirmed specs, and future benchmark protocol / ベンチマーク結果（未測定）と測定プロトコル案 |
| [Mac mini plan (English)](mac-mini-local-ai-plan.md) · [日本語](mac-mini-local-ai-plan.ja.md) | EN / JA | Historical pre-purchase assumptions, not a current inventory / 購入前の想定記録。現在の実機台帳ではない |
| [OpenClaw operations (English)](home-ai-lab-openclaw-operations.md) · [日本語](home-ai-lab-openclaw-operations.ja.md) | EN / JA | Post-Phase-4 roles and gated handover; design only, no execution authority / Phase 4後の役割分担と段階的引継ぎ。設計のみ、実行許可とは別 |
| [openclaw-trial-idea.md](openclaw-trial-idea.md) | JA + EN | OpenClaw trial idea for the lab: isolated, no personal credentials, not scheduled / OpenClaw のラボ実験アイデア（隔離・資格情報なし・時期未定） |
| [offline-oss-trial-preparation.md](offline-oss-trial-preparation.md) | EN + JA | Offline model-output comparison and untested OpenClaw probe / オフライン比較と未実行の検証案 |

## Network visibility / 家庭ネットワーク可視化

| Doc | Language | About / 内容 |
|---|---|---|
| [network-visibility.md](network-visibility.md) | EN + JA | Phase 1–4 scope; Phase 1–2 implementation in progress / 概要・実装中の範囲 |
| [network-visibility-runbook.md](network-visibility-runbook.md) | JA | Implementation, offline verification and approval-dependent deployment; live display unverified / 実装・検証・適用手順（実機表示は未検証） |

## Operations (current) / 運用（最新）

| Doc | Language | About / 内容 |
|---|---|---|
| [security-collection-trial-2026-10.md](security-collection-trial-2026-10.md) | EN | Defender and Dependabot trial observations, review candidate and outstanding checks |
| [security-operations.md](security-operations.md) | JA | Security controls, credential handling, what to do if a secret leaks / セキュリティ運用・漏えい時の対応 |
| [security-analysis-vm.md](security-analysis-vm.md) | JA | Current VM architecture, limited results and acceptance boundaries / VMの現在構成・限定試験結果・受入れ範囲（A条件付き受入れ、B未受入れ） |
| [ai-api-key-management.md](ai-api-key-management.md) | JA | Storing / rotating LLM API keys, cost limits. **Open WebUI is stopped, so this is parked** / APIキー管理（Open WebUI停止中のため保留） |
| [mcp-internal-api.md](mcp-internal-api.md) | JA | MCP server design, controls, verification / MCPの設計・制御・検証 |
| [backup-restore.md](backup-restore.md) | JA | Backup, restore test, recovery / バックアップ・復元・復旧 |
| [build-progress.md](build-progress.md) | JA | Checklist, final report, incidents, open items / チェックリスト・最終報告・障害記録・残課題 |

## Build records / 構築記録

| Doc | Language | Status |
|---|---|---|
| [implementation-plan.md](implementation-plan.md) | JA | Runbook plus per-phase results (Phase 2–5 results appended at the end) / ランブックと各フェーズの結果 |
| [physical-setup-guide.md](physical-setup-guide.md) | JA | Hardware and Ubuntu installation (done; kept for rebuilds). Example IPs there are placeholders / 物理セットアップ（完了済み・再構築用。IPは例） |
| [mac-mini-kitting-record-2026-11.md](mac-mini-kitting-record-2026-11.md) | JA | Mac mini as-built kitting record: Phase 0–1 done, Phase 2–3 in progress, open items listed / Mac mini 実機のキッティング記録（Phase 0・1 完了、2・3 進行中、残項目明記） |

## Historical / 過去の資料

| Doc | Why |
|---|---|
| [next-thread-master-prompt.md](next-thread-master-prompt.md) | Old hand-off prompt, **outdated** (predates Docker). Not the current state / 古い引き継ぎプロンプト。**現状と異なる** |

## Samples / サンプル

- [samples/github-daily-sample.md](samples/github-daily-sample.md) — a **synthetic** daily GitHub report (fake data) / 合成データの日次レポート例

Topic-specific updates take precedence over older build records; implementation is not deployment verification.
各テーマの新しい記録を過去の構築記録より優先し、実装済みと実機検証済みを区別します。

## Rules for documents / 文書のルール

- **EN:** Never put secrets, real LAN addresses, MACs or serial numbers here. Mark anything unverified as unverified.
- **JA:** 秘密情報・実際のLANアドレス・MAC・シリアルは書かない。未検証のものは未検証と明記する。
- Check before committing / コミット前の確認: `bash scripts/scan-secrets.sh`
