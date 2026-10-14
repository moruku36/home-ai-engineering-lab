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
- **UFW**: 受信は<LAN サブネット>→22/tcp に加え、Kuma専用ネットワーク(172.30.0.0/24)→22/tcp のみ許可（ホストSSH死活監視用）。SSHは公開鍵認証のみのため、到達可能でも認証なしでは入れない。
- **dockerグループ**: 未使用。`sudo docker` 運用。sudoersの恒久拡大なし（パスワード必須のまま）。
- **バックアップ**: age公開鍵暗号。NUC上の暗号化はrecipient（公開鍵）のみで行い、秘密鍵（`/etc/home-ai-lab/backup-identity.key`）はroot 600＋NUC外にも保管。詳細は [backup-restore.md](backup-restore.md)。
- **未対応**: NUC外保存、通知設定、`cap_drop`/read-only rootfs、Kuma自身停止時の外部検知。

### Phase 3（n8n / Pythonジョブ）追加分
- n8n管理画面は `127.0.0.1:5678` のみ（SSHトンネル）。オーナー認証有効。公開API・環境変数参照・コマンド実行/ファイル読み書きノードは無効。
- python-jobs は公開ポートなし、read-only rootfs、`cap_drop: ALL`、非root。Bearer認証（`hmac.compare_digest`）、`ALLOWED_REPOS` 許可リスト、入力検証、ボディ上限、タイムアウト。GitHubは未認証の公開データ読み取りのみ。
- 秘密情報: `~/home-ai-lab/n8n/.env`（chmod 600、Git管理外）の `N8N_ENCRYPTION_KEY` / `JOBS_TOKEN`。`.env` は暗号化バックアップに含まれる（`N8N_ENCRYPTION_KEY` を失うとn8n資格情報は復号不能）。
- **トークンローテーション**: `ROTATE_JOBS_TOKEN=1 bash ~/phase3-run.sh`。n8nの実行履歴には、通信エラー時にAuthorizationヘッダーが残り得る点に注意（7日で自動削除）。
- ネットワーク: `monitor-net`（172.31.0.0/24）はKuma・n8n・Open WebUIのみ。python-jobsは `n8n_internal` のみで、Kumaからは到達不可。UFW追加なし。
- 未対応: n8nのread-only rootfs、`cap_drop` 後の長期動作確認、外部AI APIキーの保管方式（n8n資格情報＋予算上限を承認後に設計）。

### Phase 4（Open WebUI）追加分
- UIは `127.0.0.1:8300` のみ（SSHトンネル）。サインアップは管理者作成後に閉じる（`owui-admin.sh lock-signup`）。新規は承認制（`DEFAULT_USER_ROLE=pending`）。テレメトリ等は無効。
- 外部LLMのAPIキーは `secrets/<provider>.key`（600）→`.env`（600、生成物）。Git・チャット・ログに出さない。詳細・費用統制・失効手順は [ai-api-key-management.md](ai-api-key-management.md)。
- 外部へ送信されるのは会話内容のみ。機密・個人情報を入力しない運用。プロバイダー側で月額ハードリミット・専用キーを設定してから登録する。
- ネットワーク注意: コンテナに複数ネットワークを付けると既定経路・送信元IPが変わり、UFWの許可ルールに合わなくなる場合がある（Kumaで発生、`gw_priority`で解決）。

### Phase 5（MCP）追加分
- MCPサーバーは公開ポートなし・`internal` ネットワーク（外向き通信なし）。クライアントは n8n / Open WebUI / Kuma(`/healthz`のみ)。詳細・検証結果・未確認事項は [mcp-internal-api.md](mcp-internal-api.md)。
- 認証はクライアント別Bearer、ツールは許可リスト制、全ツール読み取り専用。**書き込み系ツールは追加しない（追加時は別途承認）**。
- 監査ログ: `mcp_mcp-audit` ボリューム（トークン・引数値は記録しない）。トークンは `~/home-ai-lab/mcp/.env`（600）で、バックアップ(暗号化)に含まれる。

## Credential handling and leak response / 認証情報の扱いと漏えい時の対応

**EN**
- **Where secrets live:** only in `chmod 600` files on the NUC (`.env`, `secrets/*.key`) and, encrypted, in backups. Never in Git, chat, tickets, screenshots or logs. The repo's `.gitignore` blocks `.env`, `*.key`, `*.pem`, `secrets/`, SQLite/DB files and `*.tar.age`.
- **Before every push:** run `bash scripts/scan-secrets.sh` (add `--history` for a full-history check). GitHub secret scanning is also enabled on the repository.
- **Placeholders are not secrets:** `.env.example` files and docs only show the *shape* of a value (e.g. `<64 hex chars>`). Real values are generated on the NUC by the setup scripts and never printed.
- **Last full check (2026-10-15):** current files, all 23 commits on all branches, and all PR/issue text were scanned; no API key, token, private key or `.env` file was found. The only environment detail in history is the home LAN subnet used in UFW notes (not a credential).
- **If a secret is ever committed or shown anywhere:**
  1. **Rotate/revoke it first** (provider console for API keys; `ROTATE_JOBS_TOKEN=1` / `ROTATE_MCP_TOKENS=1` for local tokens; `owui-admin.sh set-key` / `remove-key` for LLM keys). Deleting the text does not make a leaked secret safe.
  2. Remove it from the current files in a PR.
  3. Only if needed, rewrite history (`git filter-repo`) and force-push — **this is destructive; get explicit approval first**, and remember forks/caches may keep copies.
  4. Record the incident in `docs/build-progress.md` (without the secret).
- **Known residual risks:** n8n's execution history can keep the `Authorization` header if an HTTP request fails at the network level (kept 7 days); secrets are visible to root through `docker inspect`.

**JA**
- **秘密情報の置き場所：** NUC上の `chmod 600` ファイル（`.env`、`secrets/*.key`）と、*暗号化された*バックアップの中だけ。Git・チャット・スクリーンショット・ログには置かない。`.gitignore` で `.env`・`*.key`・`*.pem`・`secrets/`・DBファイル・`*.tar.age` を除外済み。
- **pushの前に：** `bash scripts/scan-secrets.sh` を実行（`--history` で全履歴）。GitHubのシークレットスキャンも有効。
- **プレースホルダーは秘密ではない：** `.env.example` やドキュメントは値の*形*だけ（例 `<64 hex chars>`）。実際の値はNUC上のセットアップスクリプトが生成し、表示しない。
- **直近の全件確認（2026-10-15）：** 現在のファイル、全ブランチ23コミット、PR/Issueの本文を走査。APIキー・トークン・秘密鍵・`.env` は**見つからず**。履歴にあった環境情報は、UFWの説明にある自宅LANのサブネットのみ（認証情報ではない）。
- **秘密がコミット／表示された場合：**
  1. **まず失効・再発行**（APIキーは各社コンソール、ローカルトークンは `ROTATE_JOBS_TOKEN=1` / `ROTATE_MCP_TOKENS=1`、LLMキーは `owui-admin.sh set-key` / `remove-key`）。文字列を消しても、漏れた秘密は安全にならない。
  2. 現在のファイルからPRで削除。
  3. 必要な場合のみ履歴を書き換え（`git filter-repo`＋強制push）。**破壊的操作なので事前に明示承認を得る。** フォークやキャッシュに残る可能性に注意。
  4. `docs/build-progress.md` に経緯を記録（秘密そのものは書かない）。
- **既知の残存リスク：** n8nの実行履歴は、HTTPリクエストが通信レベルで失敗した場合に `Authorization` ヘッダーを保持し得る（7日保持）。rootは `docker inspect` で環境変数の秘密を見られる。

### 運用基盤の改善フェーズ（GitHub 監視）追加分 / GitHub monitoring (2026-10-15)
- **EN:** The collector sends only `GET` requests to `api.github.com`, only for owners in `GITHUB_OWNERS` (`moruku36`). Any GitHub token must be a **fine-grained, read-only** token stored only in `~/home-ai-lab/n8n/.env` (600) via a hidden prompt (`jobs-admin.sh`); it is sent only to the GitHub API host and never written to reports, snapshots, logs or results (tested). Kuma push tokens are handled the same way.
- **EN:** `python-jobs` joined `monitor-net` so it can reach Kuma's push endpoint; it still publishes no port and every call needs its bearer token. UFW, SSH and port exposure are unchanged. Reports are Markdown from public data; the MCP server reads them through a **read-only** mount.
- **JA:** 収集は `api.github.com` への `GET` のみ、対象は `GITHUB_OWNERS`（`moruku36`）のみ。トークンは**読み取り専用の fine-grained** のみ、`.env`（600）に非表示入力で保存し、GitHub API 以外へは送らず、レポート・スナップショット・ログ・結果に書き出さない（テスト済み）。`python-jobs` は Kuma の push 先へ到達するため `monitor-net` に参加したが、公開ポートはなく、呼び出しにはトークンが必要。UFW・SSH・公開範囲は変更なし。
- **Accepted risks / 許容しているリスク:** the Kuma push token only allows sending heartbeats; a monitor `down` push can be spoofed by anything that knows it (internal networks only). / push トークンは heartbeat の送信のみ可能（内部ネットワーク内に限る）。
