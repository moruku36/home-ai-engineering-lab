# 全体アーキテクチャ / Architecture v0.1

## 役割分担
- **NUC = Control / Execution Plane:** ワークフロー起動、Webhook（将来）、軽量ジョブ、MCP/API、監視、ログ。GPU推論は担当しない。
- **Windows/Mac = Workstation:** VS Code Remote SSH、編集、保守。NUCにGUIを載せない。
- **GitHub = Source of Truth:** 設計、バージョン管理、Issue、PR。
- **External AI = Intelligence Layer:** OpenAI、Anthropic、Gemini API。RunPod GPUは必要時だけ起動。
- **Persistent Storage:** Dockerボリューム、ワークフロー、設定、必要な小規模DB。NAS主体にはしない。

## コンポーネントと導入順

| Component | Phase | Network | Value |
|---|---|---|---|
| Ubuntu Server LTS | 1 | SSH LAN限定 | Linux基盤 |
| Docker Engine + Compose | 2 | daemon TCP非公開 | 再現可能な環境 |
| Uptime Kuma | 2 | LAN限定 | 死活監視 |
| n8n + Python | 3 | LAN/内部のみ | 自動ジョブ |
| Open WebUI | 4 | LAN限定 | 外部AI統合画面 |
| MCP / APIs | 5 | Docker内ネットワーク | OSSツール連携 |
| Prometheus/Grafana | Optional | LAN限定 | メトリクス分析 |
| GitHub Runner | Optional | inbound不要 | 信頼済みCI |

## ネットワーク
同一ルーター配下の開発PCとNUCを想定。NUCのアドレスは可能ならルーターのDHCP予約。ホスト名は `home-ai-lab`（仮）。UIはLANかSSHトンネル経由のみ。外部アクセスが必要になったらVPN（Tailscale等）を検討。

**非公開:** Docker API、DB、exporter、Redis、MCP管理API。最初は公開Webhookを使わずポーリングで開始。

## データフロー
**AIジョブ:** Scheduler → n8n/Python → GitHub APIの許可済み読み取り → 必要最小限の情報だけ外部AIへ送信 → 結果の検証・保存・通知。書き込みは初期段階で承認必須。

**統合UI:** ブラウザ → Open WebUI → 外部AI APIまたはRunPodの認証付きHTTPS推論API。NUC側は推論処理を行わない。

**MCP:** テストクライアント → 内部MCPサービス → 許可リスト上のテスト環境。権限・タイムアウト・監査ログを設定。

## 性能計画
メモリ32GBは未確認。導入後に `lscpu`, `free -h`, `lsblk`, `df -h` で実測する。8GBなら自動化・監視中心、16GBなら統合UIも段階導入、32GBなら複数サービス並行を検討。メモリ上限とディスク逼迫監視を適用。

## Architecture Decisions
- ADR-001: ESXiではなくUbuntu直接導入を初期候補。VMが必要になったらProxmox再検討。
- ADR-002: NUCはLLM推論ではなくジョブ・オーケストレーション担当。
- ADR-003: 初期基盤はDocker Compose。Kubernetesは採用しない。
- ADR-004: LAN限定で始める。
- ADR-005: GitHub self-hosted Runnerは未信頼PR実行リスクのため初期対象外。
