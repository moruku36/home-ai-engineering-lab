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
