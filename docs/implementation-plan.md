# 導入計画 / Installation & Migration Runbook

> Phase 0〜1は実施済み。**Phase 2（Docker / Uptime Kuma / ローカルバックアップ）は実施・検証済み**（結果は末尾「Phase 2 実施結果」）。Phase 3以降は未着手の計画。

## Phase 0: 保全・調査
1. ESXi管理UIにはアクセスできるが資格情報は不明。VMやデータストアの保存要否を判断する。
2. モニターとUSBキーボードをつなぐ。起動時F2でBIOS、F10でBoot Menu（実機でも確認）。
3. CPU/RAM/SSD、BIOS、UEFI、Secure Bootを記録。
4. 必要なデータをNUC外の媒体にバックアップし、復元可能性を確認。
5. BIOS更新は必要性と公式手順を確認して別途実施。

## Phase 1: Ubuntu Server
> 詳細な配線・ブート・対話インストール手順は [物理セットアップ＆Ubuntu Server導入ランブック](physical-setup-guide.md) を参照。

1. Ubuntu公式のサポート中LTS ISOを取得、ハッシュ確認（Ubuntu 24.04.5 LTS 取得済）。
2. Rufus等でUSBインストーラーを作成（USB内容は消える）。
3. **既存ESXiのデータ消去を明示的に判断後**、対象SSDを選んでインストール。
4. OpenSSH Serverを有効化し、管理者ユーザー・SSH鍵認証を設定。
5. 更新・時刻同期・ファイアウォール・LAN限定SSHを設定。
6. ルーターのDHCP予約。必要に応じて停電復帰設定等。

### 実機インベントリ
```bash
lscpu
free -h
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
lspci
ip -br addr
df -h
```

## Phase 2: Docker・監視・バックアップ
- Docker Engine + Compose pluginを公式手順で導入。
- Composeファイルをコード管理。シークレットはGit管理外。
- 最初はUptime Kumaだけ起動し、再起動後の復帰を確認。
- Docker volumesと設定をNUC外へ暗号化バックアップし、リストアを試験。

## Phase 3: n8n + Python
- n8nの認証・アクセス制限を適用。
- 最初の処理は指定GitHubリポジトリの公開メタデータ取得 → Markdown保存。read-onlyで実施。
- AI APIを追加する場合は予算・回数制限・タイムアウト・リトライ・秘密情報マスキングを実装。

## Phase 4: Open WebUI
- 外部LLM APIの認証と互換性を確認し、少なくとも1モデルに接続。
- RunPodを使うなら認証/TLSと停止ルールを設計。Colabを常設エンドポイント前提にしない。

## Phase 5: MCP/GitHub/追加監視
- MCPサービスは隔離ネットワーク、許可ツールだけ、監査ログと権限制約付き。
- GitHub self-hosted runnerは信頼済みコードと隔離環境に限定。
- 詳細な分析が必要になればGrafana/Prometheusを追加。

## Done条件
- 別PCからSSH鍵で接続
- 再起動でサービス復帰
- 死活監視のアラート確認
- 読み取り専用ジョブ成功
- 外部AI APIへの接続確認
- NUC外バックアップの復元試験

## Phase 2 実施結果（2026-10-15）
| 項目 | 結果 | 備考 |
|---|---|---|
| Docker Engine / Compose | ✅ | 公式APT。`scripts/phase2a-docker.sh`。dockerグループ追加なし |
| Uptime Kuma | ✅ | `stacks/uptime-kuma/compose.yaml`。`127.0.0.1:3001` のみ公開（UFW迂回回避）、SQLite、認証有効 |
| ホストSSH監視 | ✅ | UFWが Docker→ホスト22 を遮断していたためDown。固定サブネット(172.30.0.0/24)からのTCP22のみ許可（`scripts/phase2b-ufw-docker-ssh.sh apply/rollback`）→Up |
| 再起動試験 | ✅ | `scripts/reboot-test.sh`。SSH/UFW/Docker/Kuma自動復帰、DB保持 |
| ローカル暗号化バックアップ＋リストア | ✅ | [backup-restore.md](backup-restore.md) |
| NUC外バックアップ | ⬜ 保留 | 保存先未決定 |
| Kuma通知 / 外部死活監視 | ⬜ 未実施 | |

ロールバック: Kuma `docker compose down`（ボリューム保持）、UFWは `phase2b-ufw-docker-ssh.sh rollback`、Docker撤去はデータ確認後に別途承認。

## Phase 3 実施結果（2026-10-15）
| 項目 | 結果 | 備考 |
|---|---|---|
| n8n（`stacks/n8n`） | ✅ | n8n 2.43.5。`127.0.0.1:5678` のみ。SSHトンネル経由。`.env`（chmod 600）に暗号化キー/トークン。実行履歴は7日で自動削除。Execute Command等のノードを無効化、公開APIと環境変数アクセスを無効化 |
| Pythonジョブ（`python-jobs`） | ✅ | 内部ネットワークのみ・公開ポートなし。read-only rootfs、cap_drop ALL、非root、メモリ256MB。Bearer認証、リポジトリ許可リスト、入力検証、タイムアウト/指数バックオフ再試行、JSONログ |
| 読み取り専用GitHubワークフロー | ✅ | 公開リポジトリのメタデータ取得（未認証、書き込みなし）→要約。失敗時は Error summary 分岐 |
| 否定テスト | ✅ | トークン無し401 / 形式不正400 / 許可リスト外403 / 不明ジョブ404 |
| Kuma監視 | ✅ | `monitor-net`（172.31.0.0/24）経由で `http://n8n:5678/healthz` |
| バックアップ | ✅ | n8nデータ・ジョブレポート・`.env` を暗号化バックアップに追加。リストア試験でn8nの起動とワークフロー読出しを確認 |
| 外部AI API接続基盤 | ⬜ 未着手 | APIキー・予算上限の承認待ち |

**発見した問題と対処**
- 初回実行で python-jobs が500: レポート用ボリュームが root 所有で非rootが書けなかった → Dockerfileと導入スクリプトで所有者を修正。
- **エラー出力にBearerトークンが含まれた**: HTTP Requestノードのエラーオブジェクトに送信ヘッダーが入り、n8n実行履歴に残った → `neverError` + `Job ok?` 分岐に変更し、エラー時は message のみ出力。該当実行を削除し、`ROTATE_JOBS_TOKEN=1 bash phase3-run.sh` でトークンをローテーション。**通信エラー（接続不可）時はエラーオブジェクトにヘッダーが残り得る**ため、実行履歴の保持期間短縮とトークン定期ローテーションで緩和する（残存リスク）。

ロールバック: `cd ~/home-ai-lab/n8n && sudo docker compose down`（ボリューム保持）。Kumaは `monitor-net` から外れても動作する。ボリューム/`monitor-net`の削除は別途承認。

## Phase 4 実施結果（2026-10-15）
| 項目 | 結果 | 備考 |
|---|---|---|
| Open WebUI（`stacks/open-webui`） | ✅ | `ghcr.io/open-webui/open-webui:v0.12.0-slim`、`127.0.0.1:8300` のみ、healthy。cap_drop ALL、no-new-privileges、2GB上限 |
| 鍵管理方式 | ✅（方式）/ ⬜（実鍵） | `owui-admin.sh`（非表示入力→`secrets/*.key`(600)→`.env`生成）。偽の鍵でスクリプトのロジックをローカル検証。実キーでの動作は**未検証** |
| プロバイダー到達性 | ✅（鍵なし） | OpenAI/Anthropic 401、Gemini/RunPod 404（到達可） |
| Kuma監視 | ✅ | `http://open-webui:8080/health` Up |
| バックアップ | ✅（スクリプト更新）/ ⬜（実行） | Open WebUIデータ・`.env`・`secrets/` を対象に追加。NUC上でバックアップ+復元試験PASS（ただし取得時点では管理者未作成で `users: 0`。管理者作成後の復元は未確認） |
| 管理者作成 | ✅ | `onboarding` 解消を確認、`lock-signup` 済み（サインアップ無効）。**初回は未作成のまま閉じてしまい再オープンが必要だった** |
| 実接続 | ⬜ | APIキー待ち |

**発見した問題と対処**: Phase 3でKumaを `monitor-net` に接続した際、ホストへの経路の送信元が `monitor-net`(172.31.0.0/24)になりUFW許可（172.30.0.0/24→22）に合わず、**「NUC SSH (host)」監視が Phase 3 完了時点からDownだった（当時の報告で見落とし）**。Kumaの `gw_priority`（既定経路を172.30.0.0/24側へ固定）で修正（UFWは緩めない）。`scripts/fix-kuma-gw.sh`。

## Phase 5 実施結果（2026-10-15）
詳細は [mcp-internal-api.md](mcp-internal-api.md)。
| 項目 | 結果 | 備考 |
|---|---|---|
| MCPサーバー（`stacks/mcp`） | ✅ | 自前の最小実装（標準ライブラリのみ）。ツール4種はすべて読み取り専用 |
| 認証・認可・タイムアウト・監査ログ | ✅ | クライアント別トークン＋ツール許可リスト、ツール5秒、レート制限、JSON監査ログ（トークン/引数値なし） |
| 外部公開されないこと | ✅ | 公開ポートなし、`internal` ネットワーク、外向き通信ブロック、LANからの1051ポートスキャンで開放は22のみ、UFW変更なし |
| n8nとの接続 | ✅ | ワークフロー「MCP read-only test」成功 |
| Open WebUI / 外部AIとの接続 | ⬜ 未検証 | 到達性と401のみ確認。APIキー・UI登録待ち |
| Kuma監視 | ✅ | `http://mcp-server:8080/healthz` Up |
| バックアップ | ⬜ | スクリプトに追加済み、NUC上での実行は未実施 |
