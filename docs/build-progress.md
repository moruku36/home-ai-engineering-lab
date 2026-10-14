# Build progress / 構築進捗

最終更新: 2026-10-15 JST。SSH鍵限定の再接続成功、Docker未インストールを追加確認。状態はチャットに提示された画面・コマンド結果に基づく。未提示の操作は「未確認」。

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
- [ ] OS再起動後のSSH・UFW永続性を確認
- [ ] RAM/ディスク/LVM実測値をコマンドで記録
- [ ] Docker Engine / Compose Plugin 導入（**2026-10-15：`docker --version` / `docker compose version` とも `Command 'docker' not found`、サービス `inactive`。未インストール確認済み**）
- [ ] Uptime Kuma をLAN限定で起動
- [ ] バックアップとリストア試験
- [ ] n8n + Pythonジョブ
- [ ] Open WebUIと外部AI API
- [ ] MCP/APIとGitHub連携

## 現在判明している構成
- OS: Ubuntu Server 24.04 LTS (インストール後画面)
- Hardware: Intel NUC 11 Performance、Core i5-1135G7、RAM 32GB、Crucial P5 NVMe 1TB
- Storage: guided LVM; / root 約100GB + LVM未割当領域 約828GB（インストール時の表示、実測未完）
- Network: LAN内のDHCPでIP取得。IPは変更され得るためGitHubには記録しない
- SSH: rootログイン禁止・パスワード認証無効の実効設定確認済み
- Docker: **未インストール確認済み（2026-10-15）**

## 次の手順（優先度順）
1. Windowsの別PowerShellから専用鍵を明示して新規SSH接続 **成功済み**。既存セッションは維持。
2. Ubuntu上で `sudo sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication) '` と `sudo ufw status verbose` を再確認。
3. `hostnamectl; free -h; lsblk; df -h; sudo vgs; sudo lvs` で現状把握。LVMをむやみに拡張しない。
4. Docker導入状況は **未インストール確認済み**。競合パッケージ・APT設定を確認したうえで、公式APT手順で導入。
5. `sudo docker run --rm hello-world` を実行してDocker検証。
6. Uptime Kuma：ホストへのポート公開はLANアドレス限定またはSSHポートフォワードで試験（Docker公開ポートがUFWを迂回する点に注意）。
7. 運用設定と結果をGitHubドキュメントへ都度反映。

## 保安事項
- ローカルIPはこの公開リポジトリに書かない。SSHログインコマンドでは現在のIPを本人が確認して使用。
- SSH秘密鍵・APIキー・パスワードをコミット/チャットに貼らない。
- `docker` グループ追加はroot相当権限なので初期運用では `sudo docker` を利用。
- root領域が約100GBのため、Dockerのデータ配置・バックアップ前に容量計画を確定。
