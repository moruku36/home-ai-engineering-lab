# Network visibility Phase 1・2 — implementation / 検証手順

[概要と承認境界](network-visibility.md)。今回のコードは未deploy。下記のホスト変更・DNS起動は実機の現状確認と承認後に行います。
既存サービスを止めず、Phase 1のホストメトリクスとPhase 2のDNS試験を分けます。

## 1. 手元でできる模擬試験

Python 3.11以降、標準ライブラリのみ。スキャンもDNS要求も実行しません。

```bash
python -m unittest discover -s tests -p network_visibility_test.py -v
mkdir -p data/network-demo
python scripts/network_report.py \
  --inventory docs/samples/network-inventory.example.json \
  --querylog docs/samples/network-querylog.example.json \
  --allow-client 192.0.2.10 --output data/network-demo/report.html
```

サンプルは文書用アドレスと`example.com`のみ。サンプル日時から24時間を超えればDNS表は空になります。試験の固定時計はunit testで指定しています。
生成HTMLをローカルで開きます。サーバーは起動せず、外部のJSやCSSも読み込みません。台帳は接続検知ではなく手動の確認記録です。
AdGuardの`GET /control/querylog`のJSON（`data[].time/client/question.name`）を入力できますが、自動収集やAPI認証は今回追加していません。
5 MiB超は拒否。APIのページング・長期間の完全取得は行わず、読み込んだ範囲だけを表示します。対象外の記録は表示から除外されるだけなので、取得元でも対象端末に限定してください。

## 2. 実機の読み取り確認（未実行）

既存の認証済みSSH接続を利用。known_hostsや認証設定は変更しません。接続先や秘密鍵をGitに書きません。
現在のNUC cloneで`git status --short --branch`、`git log -1 --oneline`、`sudo docker compose ps`、`ip -br link`、`ss -ltn`を確認。
結果のIP/MAC/ホスト名は公開しません。cloneに未commit変更があればpull/checkoutで上書きせず停止し、別の作業ディレクトリを準備します。
ルータ/スイッチ機種、NIC用途、試験端末、DNS/DHCPの現状を本人に確認し、アドレス・NICを推測しません。

## 3. Phase 1: ホストのNIC数値を正しく渡す（承認後）

既存node_exporterはbridge内です。今回はhost network/PID namespaceを追加しません。
`network_host_metrics.py`を**Ubuntuホストで**実行し、明示したNICだけの`/proc/net/dev`カウンタをtextfile collectorへ渡します。
コンテナ内の`node_network_*`を代用しません。`lab_host_network_*`はNUCの選択NICの値で、家庭全体のフローではありません。

適用前に現行コミットとComposeをローカルに記録。既存`.env`は維持し、`playground-run.sh`による新規資格情報生成は行いません。
`stacks/observability/data/textfile`をoperator所有・0755で準備。そこへ書くのはNIC名と数値だけです。exporterが読む`.prom`は0644。
既存のroot bind mount以外に、host namespace権限・Docker socket・新規LAN listenerは追加しません。

```bash
# On the NUC, after the selected commit and actual NIC have been reviewed:
mkdir -p stacks/observability/data/textfile
chmod 755 stacks/observability/data/textfile
# Replace <approved-host-nic> with the NIC confirmed on this host. Never use the sample as a guess.
python3 scripts/network_host_metrics.py --interface '<approved-host-nic>' \
  --output stacks/observability/data/textfile/host-network.prom
cd stacks/observability
sudo docker compose config -q
sudo docker compose up -d --no-deps node-exporter grafana
```

ホストスクリプトを30秒ごとに呼ぶ必要があります。自動timerは未設置です。初回は承認した短時間だけ別のホスト端末で次のloopを実行し、Ctrl+Cで終了します。

```bash
# From repository root on the Ubuntu host only:
while python3 scripts/network_host_metrics.py --interface '<approved-host-nic>' \
  --output stacks/observability/data/textfile/host-network.prom; do sleep 30; done
```

最初のscrape後、`lab_host_network_snapshot_timestamp_seconds`と各counterを確認。最低5分動かし、Grafanaの`Home network / NUC host metrics (not whole-home traffic)`をSSH tunnelで開きます。
ホストの`/proc/net/dev`との数値比較、対象NICのみ、bytes/s、エラー/ドロップ、CPU/メモリ、snapshot ageを確認。
NICグラフはsnapshotが120秒以上古ければ非表示。停止・未導入は0ではなく欠測で表示し、snapshot ageパネルで見分けます。
CPU/メモリは既存node_exporterの系列であり、NICのtextfile方式とは別です。

## 4. Phase 2: DNS試験（構成雛形、未起動）

`stacks/network-dns/compose.yaml`は専用profile `dns-trial`を指定しない限り起動しません。
公式release APIで`v0.107.79`を確認しタグを固定。imageのpull・digest・起動・この版でのwizard/権限の動作は未検証。適用前にdigestを記録します。
UIは`127.0.0.1:13000`、DNSは`127.0.0.1:1053`（TCP/UDP）。53番の既存systemd-resolvedと競合しません。
LANには開かず、家庭のDNS/DHCP/ルータは変更しません。このままではLAN上の他端末から通常のDNSとして利用できません。

本人へ承認を求める具体案: **NUC自身からの明示した`dig`だけ、1時間、query log最長24時間、試験後削除**。
初期wizardでローカル管理者を作成する行為も今回未承認なので実行しません。承認後に本人がパスワードを入力し、チャットやGitへ残しません。
設定はUI bind `0.0.0.0:3000`（コンテナ内のみ）、DNS bind `0.0.0.0:53`、フィルタ/保護/ブロックリスト/DNS書換/DHCPを無効、upstreamを本人が選択。
`querylog.file_enabled: false`で生ログのディスク保存を無効、`querylog.interval: 1h`、`statistics.enabled: false`にします。`interval`はローテーション間隔なので、それだけで24時間以内の削除を保証したとは扱いません。試験を1時間で終了し、メモリを含め停止・削除を確認します。runtime client sources（ARP、rDNS、WHOIS等）も無効にします。`data/`をoperator限定で保護し、保存設定が確認できるまで実際の問い合わせは送信しません。

承認後の起動・試験案（この文書に従い自動実行していません）:

```bash
cd stacks/network-dns
sudo docker compose --profile dns-trial config -q
sudo docker compose --profile dns-trial up -d
# First complete and review wizard settings through the authenticated SSH tunnel.
# Only then, on the NUC:
dig @127.0.0.1 -p 1053 example.com A
dig +tcp @127.0.0.1 -p 1053 example.com A
```

これで試験用DNS問い合わせの可視化は確認できます。本人PCの通常通信を対象にするには、個別のDNS設定変更・転送方法・記録範囲を別途レビューします。
query logをローカルのGit管理外ファイルに保存し、`network_report.py`で対象clientを明示して表示。実際のclientはDocker転送で変化する場合があるため確認して指定。
ルータflowは機種・ライセンス/無償機能・export条件・保存対象を確認してから実装判断。NetAlertX探索もまだ開始しません。

## 5. Rollback / 削除

- Phase 1: loopを終了。承認した変更の前のCompose/provisioningを復元し、`node-exporter grafana`だけ再作成。Prometheus/Grafana volumeと既存`.env`を維持。既存datasourceや他stackは変更しない。
- Grafanaのprovisioned dashboardは`disableDeletion: true`のため、ファイルを戻しても画面に残る場合はUIからこのUID `home-network-overview`だけ削除。既存dashboardは削除しない。
- Phase 2: 端末側のDNSを変更した場合は先に元に戻す。trialのみ`sudo docker compose --profile dns-trial down`で停止。`down -v`は使わない。
- 試験後、承認対象の`stacks/network-dns/data/`、私的query log、生成HTMLのみを対象確認して削除。Prometheus volume等を巻き込まない。バックアップにDNS生ログを追加しない。

## 6. 今回の証拠と残作業

| 項目 | 状態 |
|---|---|
| 概要文書を先にGitHub公開 | PR #14の最初のcommit `23c2f73` |
| コード・ダッシュボード・DNS Compose雛形 | PR上の実装。自動deployしない |
| ホストcounter/対象限定/失敗時の振舞い、DNS集計・時刻・HTML escape | 合成データのunit testで検証（結果はPR） |
| NUC実接続・現在の作業ツリー/NIC確認 | 未実施。手元SSH configにNUC aliasなし、agent接続不可。鍵を新規作成・解除していない |
| Docker Composeの実行検証 / AdGuard image起動 | 未実施。この実行環境にDocker CLIなし |
| NUC上の収集・稼働、Grafanaブラウザ表示 | 未実施。実機確認後に記録する |
| 家庭端末一覧の自動取得、ルータflow、Phase 3・4 | 未実装。範囲・機器確認または将来作業 |

READMEの既存稼働実績は過去の記録であり、今回再検証したという意味ではありません。
