# Network visibility Phase 1・2 — implementation / 検証手順

[概要と承認境界](network-visibility.md)。コードはmain反映済みですが、今回のPhase 1・2の実機適用は未確認です。[最新の照合結果と本人確認の範囲](build-progress.md#network-runtime-status)を参照。下記のホスト変更・DNS起動は実機の現状確認と対象操作の承認範囲を確認してから行います。
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

同じテストに、ダッシュボード定義の静的整合性検査（`DashboardStaticConsistencyTests`）を含みます。パネルのクエリが使うメトリクス名が`scripts/network_host_metrics.py`の出力と一致すること、`job`ラベルとデータソース名が`prometheus.yml`・provisioningと一致すること、NICパネルが「スナップショットが古い/無いときは表示しない」条件を持つこと、Composeのマウントと公開ポート（loopbackのみ）を、リポジトリのファイルだけで確認します。Grafanaやコンテナは起動しません。**実機のGrafana表示の証拠にはなりません**（名前の不一致による空パネルを事前に防ぐだけです）。

サンプルは文書用アドレスと`example.com`のみ。サンプル日時から24時間を超えればDNS表は空になります。試験の固定時計はunit testで指定しています。
生成HTMLをローカルで開きます。サーバーは起動せず、外部のJSやCSSも読み込みません。台帳は接続検知ではなく手動の確認記録です。
AdGuardの`GET /control/querylog`のJSON（`data[].time/client/question.name`）を入力できますが、自動収集やAPI認証は今回追加していません。
5 MiB超は拒否。APIのページング・長期間の完全取得は行わず、読み込んだ範囲だけを表示します。対象外の記録は表示から除外されるだけなので、取得元でも対象端末に限定してください。

## 2. 実機の読み取り確認

既存の認証済みSSH接続を利用。known_hostsや認証設定は変更しません。接続先や秘密鍵をGitに書きません。
現在のNUC cloneで`git status --short --branch`、`git log -1 --oneline`、`sudo docker compose ps`、`ip -br link`、`ss -ltn`を確認。
結果のIP/MAC/ホスト名は公開しません。cloneに未commit変更があればpull/checkoutで上書きせず停止し、別の作業ディレクトリを準備します。
ルータ/スイッチ機種、NIC用途、試験端末、DNS/DHCPの現状を本人に確認し、アドレス・NICを推測しません。

### 読み取り確認の結果（2026-10-15）

本人が既存の暗号化鍵をWindows OpenSSH agentへ登録後、登録済みhost keyを厳格確認し、agent forwardingなし・非対話SSHで接続に成功しました。秘密鍵本文・パスフレーズ・既存サービスの認証情報は読み取っていません。

- Ubuntu 24.04.5 LTS、Docker 29.9.0、Compose 5.6.0。Dockerサービスはactive。
- 物理有線NIC 1本がupでdefault routeもそのNIC、Wi-Fi NICはdown。実際のNIC名・IP/MACは公開せず、手順では`<approved-host-nic>`を使います。
- NUC cloneは`main`、commit `04d3683`、作業ツリーclean。PR #14反映前なので、承認後の適用時に現行状態を再確認してからfast-forwardします。既存`.env`は存在のみ確認し、読み取り・生成・置換はしていません。
- Prometheus ready、Grafana health正常（12.4.3）。既存収集先3件は全て`up`、errorなし。プロセス名の確認でもPrometheus/Grafana/node_exporter各1件を観測。Dockerの完全なcontainer一覧は権限不足のため未確認です。
- 現行`node_network_receive_bytes_total`のdeviceはコンテナ側の`eth0`と`lo`。物理NICの通信量として扱わず、Phase 1では既存exporterへホストsnapshotだけを追加します。
- 既存Kuma/n8n/Prometheus/Grafana/kind APIのTCP listenerはloopback。SSHは通常の22番。DNSの既存TCP53 listenerもloopback。試験用TCP/UDP1053とTCP13000の既存待受は観測されませんでした（適用直前に再確認）。Open WebUIの8300 listenerは確認されず、既存の停止記録と整合します。
- `sudo -n`と一般ユーザーのDocker API操作は利用不可。サービス操作には本人のsudo認証が必要です。sudo設定やdocker groupを変更していません。

**今回の操作は読み取りのみです。** リポジトリ更新、コンテナ再作成、定期snapshot、端末探索、DNS試験、管理者作成は行っていません。
Phase 1適用では既存Prometheusを維持し、対象NICのsnapshotとnode-exporter/Grafanaだけの再作成（短時間の表示・収集中断あり）を具体承認の対象にします。Phase 2の管理者作成・限定DNS試験は別の承認対象です。
作業終了後は本人がagentから対象公開鍵を指定して登録を除き、他の用途がなければagentを停止します。Manualの起動種別は維持し、鍵の暗号化は変更しません。

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
| コード・ダッシュボード・DNS Compose雛形 | mainに反映済み。PR #25の静的検証追加もマージ済み。自動deployしない |
| ホストcounter/対象限定/失敗時の振舞い、DNS集計・時刻・HTML escape | 合成データのunit testで検証（結果はPR） |
| ダッシュボードJSON・exporter出力・Prometheus/Grafana設定・Composeの名前/パス整合 | 静的テストで検証（ファイルのみ。実機表示は別） |
| NUC実接続・現在の作業ツリー/NIC確認 | 既存agentで読み取り確認済み。上記の結果参照。適用直前に再確認する |
| Docker Compose構成検証 / AdGuard image起動 | 両Composeのconfigは[Linux CIで成功](https://github.com/moruku36/home-ai-engineering-lab/actions/runs/38719281759)。実機でのimage起動は未実施 |
| NUC上のPhase 1収集・新規ダッシュボード表示 | 未確認。既存コンテナ稼働・Grafanaログインの本人確認と、GUIでのPrometheus既定登録／ダッシュボード未作成の確認は[構築進捗 §0.6](build-progress.md#network-runtime-status)参照。snapshot更新・設定適用・パネル表示の証拠とは分ける |
| 家庭端末一覧の自動取得、ルータflow、Phase 3・4 | 未実装。範囲・機器確認または将来作業 |

READMEの既存稼働実績は過去の記録であり、今回再検証したという意味ではありません。
