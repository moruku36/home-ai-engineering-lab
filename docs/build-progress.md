# Build progress / 構築進捗

最終更新: 2026-10-15 JST。Phase 2（Docker / Uptime Kuma / ローカル暗号化バックアップ）を実施・検証。状態はチャットに提示された画面・コマンド結果に基づく。未提示の操作は「未確認」。

## チェックリスト
- [x] Intel NUC 11 NUC11PAHi5 確認（Core i5-1135G7、DDR4 16GB × 2 = 32GB、Crucial P5 1TB）
- [x] 既存 VMware ESXi 7.0.2 から Ubuntu Server へ移行（既存ディスク消去を伴う）
- [x] KIOXIA 16GB USB の Rufus 起動メディアを作成、FAT32 / EFIブートファイルを確認
- [x] NUC の Boot Menu にUSBが出ない問題を EFI Shell `map -r` → `fs0:\EFI\BOOT\BOOTX64.EFI` 直接実行で回避
- [x] Ubuntu Server 24.04 LTS インストール完了
- [x] ホスト名 `home-ai-lab`、ユーザー `moruku`、LAN経由SSHログイン成功
- [x] Ubuntu パッケージ更新（本人による完了報告）
- [x] SSH公開鍵を `~/.ssh/authorized_keys` に登録、権限600
- [x] OpenSSH 実効設定確認：`PermitRootLogin no`、`PubkeyAuthentication yes`、`PasswordAuthentication no`、`KbdInteractiveAuthentication no`
- [x] UFW有効、受信は原則拒否、192.168.3.0/24 からTCP/22のみ許可（提示スクリーンショットによる）
- [x] **SSH鍵のみでの新規接続再テスト**（Windowsから専用Ed25519秘密鍵を `-i` / `IdentitiesOnly=yes` で指定し、公開鍵のみでログイン成功。`whoami` = `moruku`、`hostname` = `home-ai-lab`）
- [x] OS再起動後のSSH・UFW永続性を確認（2026-10-15 再起動試験。SSHは約20秒で復帰、`sshd -T` 4設定・UFWルールは再起動前後で同一）
- [x] RAM/ディスク/LVM実測値を記録（RAM 30GiB、swap 8GiB、8スレッド、`/` = LV 100GiB（使用約11GiB）、PV 928.5GiB。**LVMは未変更**。※`vgs`/`lvs` の全文出力は未記録）
- [x] Docker Engine / Compose Plugin 導入（docker-ce 29.9.0 / compose-plugin 5.6.0 / containerd.io 2.4.2、公式APTリポジトリ）。docker・containerd enabled/active、TCPリスナなし。`moruku` はdockerグループ**未所属**（`sudo docker` 運用）。※`hello-world` 実行は導入スクリプトで実施したが出力全文は未記録
- [x] Uptime Kuma をLAN限定で起動（`127.0.0.1:3001` のみ公開、SSHトンネル経由。SQLite。管理者認証有効。監視2件: Kuma自身HTTP、NUC SSH TCP。通知先は**未設定**）
- [x] 再起動後の自動復帰・データ保持を確認（コンテナ healthy、`kuma.db` 同一、監視/履歴/ログイン保持）
- [x] ローカル暗号化バックアップとリストア試験（age公開鍵暗号、毎日03:30 systemd timer、7世代。チェックサム検証→復号→DB確認→隔離Kuma起動 PASS）。秘密鍵のNUC外保管はユーザー実施済み
- [ ] **NUC外バックアップ保存（保存先未決定のため保留）**
- [ ] バックアップtimerの自動実行を実機で確認（初回予定: 翌03:30頃）
- [ ] NUCの死活を外部から監視する仕組み（Kuma自身が止まる場合の検知）
- [ ] Kumaの通知先設定
- [x] n8n + Pythonジョブ（n8n 2.43.5、`127.0.0.1:5678` のみ公開、オーナー認証有効、python-jobs は内部ネットワークのみ・read-only rootfs・cap_drop ALL・Bearer認証。GitHub公開リポジトリのメタデータ取得ワークフロー成功、認証/入力検証の否定テスト 401/400/403/404 合格、Kuma監視 n8n Up、バックアップ/リストア試験にn8n含め合格）
- [ ] 外部AI API接続の基本構成（未着手。APIキー未提供のため、承認後に実施）
- [ ] n8nのエラー通知先（Kuma通知と併せて設定）
- [x] Open WebUI導入（v0.12.0-slim、`127.0.0.1:8300` のみ、API鍵なしで起動、テレメトリ無効、サインアップは管理者作成後に閉じる運用、Kuma監視 Up）
- [ ] Open WebUI管理者アカウント作成と `lock-signup`（ユーザー操作待ち）
- [ ] 外部LLM APIキー登録と実接続検証（OpenAI / Anthropic / Gemini / RunPod。キー未提供のため未検証。方式は docs/ai-api-key-management.md）
- [ ] MCP/APIとGitHub連携

## 現在判明している構成
- OS: Ubuntu Server 24.04 LTS (インストール後画面)
- Hardware: Intel NUC 11 Performance、Core i5-1135G7、RAM 32GB、Crucial P5 NVMe 1TB
- Storage: LVM。`/` = LV 100GiB（使用約11GiB、空き約82GiB）、PV 928.5GiB（残りはVG未割当。変更なし）。Dockerデータは `/var/lib/docker`（ルートLV上）
- Network: LAN内のDHCPでIP取得。IPは変更され得るためGitHubには記録しない
- SSH: rootログイン禁止・パスワード認証無効の実効設定確認済み
- Docker: **導入済み（docker-ce 29.9.0 / compose-plugin 5.6.0）**。稼働サービス: Uptime Kuma（`127.0.0.1:3001`、固定サブネット 172.30.0.0/24）

## 次の手順（優先度順）
1. バックアップ保存先（NUC外）を決定し、暗号化バックアップを転送・復元試験（認証情報は推測しない）。
2. バックアップtimerの初回自動実行（翌03:30頃）を確認。
3. Kumaの通知先設定、NUC外からの死活監視の検討。
4. Open WebUI管理者作成→`lock-signup`。APIキーは用途専用・月額上限設定後に `owui-admin.sh set-key` で登録し、実接続を検証。Phase 5（MCP）へ。

## 保安事項
- ローカルIPはこの公開リポジトリに書かない。SSHログインコマンドでは現在のIPを本人が確認して使用。
- SSH秘密鍵・APIキー・パスワードをコミット/チャットに貼らない。
- `docker` グループ追加はroot相当権限なので初期運用では `sudo docker` を利用。
- root領域が約100GBのため、Dockerのデータ配置・バックアップ前に容量計画を確定。
