# Home AI Engineering Lab

[English](README.md) | **日本語**

自宅の Intel NUC で、GitHub の開発支援を自動化し、監視と OSS の実験を行うラボです。常設基盤は Ubuntu Server と Docker Compose で構成し、別の QEMU/KVM ゲストにオフラインのセキュリティ解析環境を用意しています。

常設の自動化基盤では LLM を動かさず、有料 LLM API も使いません。Open WebUI はデータを保持して意図的に停止中です。追加の有料サービスは導入していません（電気代・既存のサブスクリプション料金は除きます）。

**入口：** [機能と現在の状態](#機能と現在の状態) · [使い方](#使い方) · [構築・開発](#構築開発) · [ドキュメント索引](docs/README.md)

## 機能と現在の状態

**2026-10-20 JST 時点のコードと検証記録**に基づく概要です。今回 NUC の稼働状況を再確認したものではありません。実装・実機への反映・受入れを分けて記載します。

| 分野 | できること・実装内容 | 記録上の状態／残課題 |
|---|---|---|
| [GitHub 日次レポート](docs/github-monitoring.md) | n8n → Python 収集 → Markdown/JSON 保存。07:00 JST に実行する設定 | n8n からの手動実行は実機確認済み。定期実行の初回と実機での未実行原因は未確認。ソース修正・鮮度検査は NUC 未反映。 |
| [前日 JST の活動集計](docs/github-monitoring.md) | PR の作成・マージ・未マージ close、Issue の作成・close、最新 push が前日にあるリポジトリ数 | 収集コードに実装済み。検証範囲は詳細資料を参照。push イベント数・コミット数は未実装。API の取得範囲と検索索引の遅延に制約あり。 |
| [読み取り専用 MCP](docs/mcp-internal-api.md) | 認証・監査つきで保存済みレポートを参照 | n8n からの読み取り確認済み。公式クライアント／Inspector 互換性と実機での異常系試験は未確認。 |
| [監視・通知](docs/monitoring-notifications.md) | Uptime Kuma の死活監視、収集ジョブの Push 監視、任意の外部 heartbeat | 検知は確認済み。通知チャネル・Push トークンは未設定。外部 heartbeat は未有効化。 |
| [バックアップ・復元](docs/backup-restore.md) | ローカル暗号化バックアップと復元試験 | 手動のバックアップ・復元は確認済み。timer の初回自動実行は未観測。NUC 外コピーなし。 |
| [OSS プレイグラウンド](docs/playground.md) | Prometheus・Grafana・node_exporter、2 ノードの kind クラスタ | 起動、scrape、Grafana API クエリ、kind の Ready を実機確認済み。ブラウザでのダッシュボード表示・kind 上のワークロードは未確認。Kyverno は設計のみ。 |
| [家庭ネットワーク可視化](docs/network-visibility.md) | ホストの数値、許可した端末の手動台帳、ダッシュボード定義、限定 DNS 試験の雛形 | Phase 1・2 を実装中。実機への適用・表示は未検証。IDS・遮断は将来の検討。 |
| [専用セキュリティ解析 VM](docs/security-analysis-vm.md) | 仮想 NIC なしのゲスト、読み取り専用 ISO 搬入、独立した Workbench と REA/Ghidra | スコープ A（VM 基盤・基本操作）は条件付きオーナー受入れ。スコープ B（REA → Ghidra の解析能力）は未受入れ。元の `FAIL` / `REPORT=UNVERIFIED` を保持。 |
| [Open WebUI](docs/ops-runbook.md#1-open-webui-stop--start) | チャット UI のスタックを保存 | 意図的に停止中、データ保持。LLM API への実接続は未検証。 |

過去の構築結果と根拠は [構築進捗](docs/build-progress.md) にあります。古い構築記録よりも、上表からリンクした各テーマの新しい記録を優先してください。

最新の保守記録：[Brotli 脆弱性対応と n8n 更新（2026-10-25）](docs/brotli-n8n-update-2026-10-25.md)。確認済みの範囲と未検証事項を分けています。

## 構成

| 層 | 構成と境界 |
|---|---|
| アクセス | 手元の PC → SSH 鍵認証 → NUC。管理画面はループバック限定で SSH トンネルから利用。インターネットへの画面公開・ルーターのポート開放なし。 |
| 自動化 | n8n が内部の `python-jobs` を呼び、GitHub API を読み取り、レポートとスナップショットを保存。 |
| レポート参照 | n8n または互換性のあるクライアントから、内部の読み取り専用 MCP サーバーを利用。 |
| 可観測性 | Uptime Kuma がサービスを監視。Prometheus／node_exporter の数値を Grafana で参照。ネットワーク可視化の追加部分は実機適用未検証。 |
| 復旧 | `age` で暗号化したローカルバックアップ。NUC 外の保存先は未決定。observability のボリュームは既存の暗号化バックアップ対象外。 |
| 解析 | 仮想 NIC なしの独立 QEMU/KVM ゲスト。Workbench と REA は別個の MCP サーバーで、相互連携は未実施。 |

[システム・ネットワーク・バックアップの構成図](docs/architecture.md) · [VM の構成図と受入れ範囲](docs/security-analysis-vm.md)

## 使い方

手元の PC から、ご自身のアカウントと NUC のアドレスで SSH トンネルを張ります。実際の LAN アドレスは公開リポジトリに記載しません。

```bash
ssh -N -L 3001:127.0.0.1:3001 -L 5678:127.0.0.1:5678 -L 9090:127.0.0.1:9090 -L 3000:127.0.0.1:3000 <user>@<nuc-address>
```

| 画面 | PC から開く URL | 操作ガイド |
|---|---|---|
| Uptime Kuma | <http://localhost:3001> | [通知・外部 heartbeat](docs/monitoring-notifications.md) |
| n8n | <http://localhost:5678> | [GitHub レポートの運用](docs/github-monitoring.md) |
| Prometheus | <http://localhost:9090> | [Prometheus の記録](docs/playground/prometheus.md) |
| Grafana | <http://localhost:3000> | [Grafana の記録](docs/playground/grafana.md) |

- **レポート生成：** n8n → `GitHub daily report (read-only)` → Execute。無認証 API の予算により部分的な結果になる場合があります。同日のより充実したレポートを、不完全な結果で上書きしない保護があります。
- **レポート参照：** n8n → `MCP read-only test`、または MCP の `read_report` で `github-daily-latest.md` を読む。[合成データのサンプル](docs/samples/github-daily-sample.md)。
- **定期実行されない場合：** [GitHub monitoring §11](docs/github-monitoring.md#11-scheduled-run-investigation-task-122-2026-10-18) の読み取り専用の調査手順を使う。状態確認のために deploy スクリプトを実行しない。
- **停止・再開・更新・復旧：** [運用手順書](docs/ops-runbook.md) を参照。

## 構築・開発

1. **ホストを再構築する：** [物理セットアップ](docs/physical-setup-guide.md) → [実装計画とフェーズ別の結果](docs/implementation-plan.md)。再構築用の記録であり、一括インストーラーではありません。
2. **機能を変更する：** `stacks/` の定義、`scripts/` の処理、対応する [テーマ別ガイド](docs/README.md) を確認。
3. **ローカルで検証する：** リポジトリのルートで関連するオフライン試験と秘密情報検査を実行。実機への反映・受入れ確認とは区別します。

```bash
python3 -m unittest discover -s tests -p '*_test.py'
python3 tests/mcp_selftest.py
bash scripts/scan-secrets.sh
```

構築・運用スクリプトはホストを変更するものがあります。NUC で実行する前に対応する手順書を確認してください。初期スタックと後から追加したプレイグラウンドでは配置先が異なります。[運用手順書](docs/ops-runbook.md)・[プレイグラウンド構築](docs/playground.md) を参照。

| パス | 内容 |
|---|---|
| [`stacks/`](stacks/) | Compose、ワークフロー、Python 収集、MCP、監視基盤、kind の定義 |
| [`scripts/`](scripts/) | 構築・運用・バックアップ・heartbeat・ネットワーク集計・秘密情報検査 |
| [`tests/`](tests/) | 収集・鮮度検査・MCP・ネットワーク可視化のオフライン試験 |
| [`docs/`](docs/README.md) | 設計・テーマ別手順書・サンプル・進捗・過去の記録 |

## 運用上の優先事項と境界

- GitHub 定期実行の結果を確認し、調査手順に沿ってソース修正を実機に反映する。
- 通知配送・収集ジョブの Push・任意の外部 heartbeat を設定し、[NUC 外バックアップ先](docs/offsite-backup-options.md) を決める。
- ネットワーク可視化と VM の未検証・未受入れを明示する。コードや限定的な出力だけで、実機の機能完成とは扱わない。
- SSH 鍵認証、ループバック限定の管理画面、読み取り専用の収集を維持する。秘密情報・実際の LAN アドレス・MAC・シリアルをコミットしない。[セキュリティ運用](docs/security-operations.md) を参照。
- 外部への書き込み・資格情報・有料サービス・ネットワーク変更は、各資料に記載した承認範囲に従う。

ライセンス：未指定。
