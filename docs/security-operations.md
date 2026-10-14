# セキュリティと運用設計

## アクセス制御
- SSHは鍵認証・LAN限定・rootログイン禁止。ルーターのポート転送禁止。
- Web UIはLAN/SSHトンネル限定。無認証公開禁止。
- Dockerソケットを不用意にコンテナへマウントしない（dockerグループは実質root相当）。
- MCPツールは許可操作、対象、タイムアウト、監査ログを定義。ローカルネット全体への無制限アクセスは不可。
- GitHubはFine-grained token/GitHub Appによる最小権限。公開PRをself-hosted runnerで実行しない。
- n8n/Open WebUIのキー・トークンをGitに載せない。

## データ
- 外部AIへ送信する情報を選別し、機密・個人情報を無承認送信しない。
- 会話、n8n実行履歴、ログの保存期間を制限。
- 設定はGit管理、秘密値はGit対象外の.env等へ。
- この公開リポジトリにMAC、シリアル、実IP、認証情報を保存しない。

## 運用
- バックアップ・復旧確認後に更新。
- Docker volume・n8nワークフロー・Open WebUI設定を外部バックアップ。
- RAM、CPU、SSD残量、SMART、温度、死活を監視。
- 障害時の無限リトライ防止と通知。
- 外部LLM API、RunPodの費用制限・停止を設計。

## 未決事項
- Ubuntuの導入バージョン
- 実搭載RAM/SSD
- TLS・バックアップ先と保持期間
- 将来の外部Webhook要否

## 実装済みの設定（2026-10-15 時点）
- **Docker公開ポート**: Dockerは公開ポートでUFWを迂回し得るため、管理UIは `127.0.0.1` バインドのみ（Kuma: `127.0.0.1:3001`）。アクセスはSSHトンネル（`ssh -N -L 3001:127.0.0.1:3001 <user>@<host>`）。Docker APIのTCP待ち受けなし。Dockerソケットはどのコンテナにもマウントしていない。
- **コンテナ制限**: Kumaは `no-new-privileges`、メモリ512MB、pids 256、ログローテーション。`cap_drop` は未適用（今後の課題）。
- **UFW**: 受信は192.168.3.0/24→22/tcp に加え、Kuma専用ネットワーク(172.30.0.0/24)→22/tcp のみ許可（ホストSSH死活監視用）。SSHは公開鍵認証のみのため、到達可能でも認証なしでは入れない。
- **dockerグループ**: 未使用。`sudo docker` 運用。sudoersの恒久拡大なし（パスワード必須のまま）。
- **バックアップ**: age公開鍵暗号。NUC上の暗号化はrecipient（公開鍵）のみで行い、秘密鍵（`/etc/home-ai-lab/backup-identity.key`）はroot 600＋NUC外にも保管。詳細は [backup-restore.md](backup-restore.md)。
- **未対応**: NUC外保存、通知設定、`cap_drop`/read-only rootfs、Kuma自身停止時の外部検知。

### Phase 3（n8n / Pythonジョブ）追加分
- n8n管理画面は `127.0.0.1:5678` のみ（SSHトンネル）。オーナー認証有効。公開API・環境変数参照・コマンド実行/ファイル読み書きノードは無効。
- python-jobs は公開ポートなし、read-only rootfs、`cap_drop: ALL`、非root。Bearer認証（`hmac.compare_digest`）、`ALLOWED_REPOS` 許可リスト、入力検証、ボディ上限、タイムアウト。GitHubは未認証の公開データ読み取りのみ。
- 秘密情報: `~/home-ai-lab/n8n/.env`（chmod 600、Git管理外）の `N8N_ENCRYPTION_KEY` / `JOBS_TOKEN`。`.env` は暗号化バックアップに含まれる（`N8N_ENCRYPTION_KEY` を失うとn8n資格情報は復号不能）。
- **トークンローテーション**: `ROTATE_JOBS_TOKEN=1 bash ~/phase3-run.sh`。n8nの実行履歴には、通信エラー時にAuthorizationヘッダーが残り得る点に注意（7日で自動削除）。
- ネットワーク: `monitor-net`（172.31.0.0/24）はKumaとn8nのみ。python-jobsは `n8n_internal` のみで、Kumaからは到達不可。UFW追加なし。
- 未対応: n8nのread-only rootfs、`cap_drop` 後の長期動作確認、外部AI APIキーの保管方式（n8n資格情報＋予算上限を承認後に設計）。

### Phase 4（Open WebUI）追加分
- UIは `127.0.0.1:8300` のみ（SSHトンネル）。サインアップは管理者作成後に閉じる（`owui-admin.sh lock-signup`）。新規は承認制（`DEFAULT_USER_ROLE=pending`）。テレメトリ等は無効。
- 外部LLMのAPIキーは `secrets/<provider>.key`（600）→`.env`（600、生成物）。Git・チャット・ログに出さない。詳細・費用統制・失効手順は [ai-api-key-management.md](ai-api-key-management.md)。
- 外部へ送信されるのは会話内容のみ。機密・個人情報を入力しない運用。プロバイダー側で月額ハードリミット・専用キーを設定してから登録する。
- ネットワーク注意: コンテナに複数ネットワークを付けると既定経路・送信元IPが変わり、UFWの許可ルールに合わなくなる場合がある（Kumaで発生、`gw_priority`で解決）。
