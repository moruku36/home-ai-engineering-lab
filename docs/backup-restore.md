# バックアップ・リストア手順

最終更新: 2026-10-15 JST。**状態: ローカル暗号化バックアップ＋リストア試験は合格。NUC外保存は未実施（保存先未決定）。**

## 方式
| 項目 | 内容 |
|---|---|
| 対象 | `~/home-ai-lab`（Compose定義）、Uptime Kumaデータボリューム（`uptime-kuma_uptime-kuma-data`） |
| 一貫性 | 取得中だけKumaを停止（数秒）→ tar → 再開 |
| 暗号化 | [age](https://github.com/FiloSottile/age) 公開鍵暗号。NUC上には**公開鍵（recipient）**でバックアップを暗号化。復号用の秘密鍵はNUC外（パスワードマネージャー等）にも保管 |
| 保存先 | `/var/backups/home-ai-lab`（root:root, 700 / ファイル600）＋ `.sha256` |
| スケジュール | systemd timer `home-ai-lab-backup.timer`、毎日 03:30（+最大10分のランダム遅延、`Persistent=true`） |
| 保持 | 最新7世代（`KEEP` 環境変数で変更）。古い世代は自動削除 |
| 導入 | `scripts/phase2c-run.sh`（age/sqlite3導入、鍵生成、スクリプト・timer設置、初回バックアップ、リストア試験） |

秘密鍵は `/etc/home-ai-lab/backup-identity.key`（root, 600）。**リポジトリ・チャット・ログに出さない。** 鍵を失うと過去のバックアップは復号できない。

## 手動バックアップ
```bash
sudo /usr/local/sbin/home-ai-lab-backup
sudo ls -l /var/backups/home-ai-lab
```

## リストア試験（本番に触れない）
```bash
sudo /usr/local/sbin/home-ai-lab-restore-test            # NUC上の鍵を使用
sudo /usr/local/sbin/home-ai-lab-restore-test /path/to/identity.key   # 別の鍵ファイル
```
最新バックアップのチェックサム検証 → 復号 → 展開 → `kuma.db` の監視一覧表示 → ネットワーク無しの使い捨てKumaを復元データで起動し `healthy` を確認 → 試験用コンテナ/ボリューム（`kuma-restore-test`）を削除。`RESTORE TEST: PASS` で合格。

## 実復旧（NUC再構築・データ破損時）
> 本番データを上書きする操作。実行前に現状データの退避と対象バックアップを確認すること。
1. Ubuntu・Docker・`age` を導入し、バックアップファイル（`*.tar.age`, `.sha256`）をNUCへ配置。
2. `sha256sum -c <file>.sha256`
3. 復号・展開（秘密鍵は一時的に配置、終了後に削除）:
   ```bash
   mkdir /tmp/restore && cd /tmp/restore
   age -d -i identity.key home-ai-lab-<ts>.tar.age | tar -xf -
   mkdir cfg && tar -C cfg -xf config.tar && tar -tf kuma-data.tar | head
   ```
4. Compose定義を `~/home-ai-lab` へ戻し、Kumaを停止（`docker compose stop`）。
5. ボリュームへ書き戻し（**既存データを置換**）:
   ```bash
   docker volume create uptime-kuma_uptime-kuma-data
   docker run --rm -v uptime-kuma_uptime-kuma-data:/d -v /tmp/restore:/src:ro --entrypoint sh louislam/uptime-kuma:2 -c 'cd /d && tar -xf /src/kuma-data.tar'
   ```
6. `docker compose up -d`、`healthy` と監視一覧をSSHトンネル経由で確認。
7. UFWルール（`scripts/phase2b-ufw-docker-ssh.sh apply`）と、バックアップ timer（`scripts/phase2c-run.sh`）を再設定。

## ロールバック（バックアップ機構の撤去）
```bash
sudo systemctl disable --now home-ai-lab-backup.timer
sudo rm /etc/systemd/system/home-ai-lab-backup.{service,timer} /usr/local/sbin/home-ai-lab-{backup,restore-test}
sudo systemctl daemon-reload
```
既存のバックアップファイルと鍵は自動では削除しない（削除は別途判断）。

## 未実施・制約
- **NUC外保存**: 保存先・認証情報が未確定のため保留。現状はNUCのディスク故障・盗難に対して保護されない。
- timerの**自動実行**は未確認（手動実行で動作確認済み）。
- リストア試験は「DB内容と起動可否」まで。履歴データの完全性は未検証。
- バックアップ中はKumaが数秒停止し、その間の監視は欠測する。

## Phase 3 での拡張（2026-10-15）
- 対象に **n8nデータ（`n8n_n8n-data`）**、**ジョブレポート（`n8n_jobs-reports`）**、**`~/home-ai-lab/n8n/.env`**（秘密情報。アーカイブごと暗号化）を追加。バックアップ中はn8n/python-jobs/Kumaを数秒停止。
- リストア試験は、n8nのDB整合性（`integrity_check`）、ワークフロー/資格情報件数、復元データでの使い捨てn8n起動（ネットワークなし）とCLIでのワークフロー読出しまで確認。
- 実復旧時は、`n8n-data.tar` を `n8n_n8n-data` に戻し、`.env`（同じ `N8N_ENCRYPTION_KEY`）を `~/home-ai-lab/n8n/` に配置してから `docker compose up -d`。ボリューム内の所有者は uid 1000（node）。
- 適用: `scripts/phase3-backup-update.sh`（スクリプト更新、バックアップ1回、リストア試験）。

## Phase 4 での拡張（2026-10-15）
- 対象に **Open WebUIデータ（`open-webui_open-webui-data`）** と、`~/home-ai-lab/open-webui/{.env,secrets/}`（APIキー。アーカイブごと暗号化）を追加（スクリプト更新済み、NUC上での実行は未実施）。
- リストア試験は `webui.db` の整合性とユーザー数を確認。
- 実復旧時は `owui-data.tar` を `open-webui_open-webui-data` に戻し、`.env` と `secrets/` を配置して `docker compose up -d`。

## Phase 5 での拡張（2026-10-15）
- 対象に **MCP監査ログ（`mcp_mcp-audit`）** と `~/home-ai-lab/mcp/.env`（MCPトークン。暗号化）を追加（スクリプト更新済み、NUC上での実行・復元試験は未実施）。
