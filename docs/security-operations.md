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
