# OSS Playground / OSS プレイグラウンド

**Status (2026-10-15): Prometheus + Grafana (+ node-exporter) and a kind cluster are running on the NUC.** Verified: health checks, loopback-only ports, all three scrape targets `up`, Grafana admin login and a query through the Prometheus data source, kind with 2 `Ready` nodes and the API on `127.0.0.1:6443` only. Not yet tried: the UIs in a browser, dashboards, workloads on kind. Results: [build-progress.md](build-progress.md) §0.5 and the per-product notes in [playground/](playground/).

## Purpose

Besides the always-on monitoring box, the lab is a **playground for open-source products**: run them, write down impressions, run vulnerability checks, and prepare bug fixes / contributions upstream.

| Product | Role | Where | Status |
|---|---|---|---|
| Uptime Kuma | monitoring / alerts (already in the lab) | `stacks/uptime-kuma` → `127.0.0.1:3001` | ✅ running (see README) |
| Prometheus | metrics | `stacks/observability` → `127.0.0.1:9090` | ✅ running (v3.15.0) · ✅ 3 targets `up` — [note](playground/prometheus.md) |
| Grafana OSS | dashboards | `stacks/observability` → `127.0.0.1:3000` | ✅ running (12.4.3) · ✅ login + data source query · ⬜ dashboards — [note](playground/grafana.md) |
| Kubernetes (kind) | throw-away cluster (1 control-plane + 1 worker) | `stacks/kubernetes` → API `127.0.0.1:6443` | ✅ running (kind v0.27.0, k8s v1.32.2, 2 nodes `Ready`) · kubectl skew fixed in repo (pinned v1.32.13), not re-run — [note](playground/kubernetes.md) |
| Kyverno | Kubernetes policy engine (5th product) | design only: [playground-kyverno-design.md](playground-kyverno-design.md) | 📝 designed, not implemented |

Also in the stack: `node-exporter` (host metrics, no published port).

## Start / stop (on the NUC)

The NUC's always-on stacks live in `~/home-ai-lab` (deployed file by file, not a Git clone). The playground runs from a clone of this repo at `~/home-ai-engineering-lab` (`git clone https://github.com/moruku36/home-ai-engineering-lab.git`, then `git pull --ff-only` to update).

```bash
bash scripts/playground-run.sh observability   # Prometheus + Grafana + node-exporter
bash scripts/playground-run.sh kubernetes      # kind cluster "playground"
bash scripts/playground-run.sh all | status | down   # down keeps volumes
```

SSH tunnel from your PC: `ssh -N -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 -L 6443:127.0.0.1:6443 <user>@<nuc-address>`

Grafana's admin password is generated into `stacks/observability/.env` (`chmod 600`, git-ignored, never printed). Kubeconfig: `~/.kube-playground`.

## Rules for playground work

1. **Isolation first.** UIs/APIs bind to loopback; nothing is opened on the LAN or router. Keep targets of vulnerability testing **inside this lab only** (never scan third-party hosts).
2. **No secrets in Git.** Use `.env` / kubeconfig files with `chmod 600`.
3. **One note per product** under `docs/playground/<product>.md`: version tested, what was tried, impressions, findings (bugs / vulnerabilities), upstream issue/PR links. Report vulnerabilities **privately** to the upstream project's security contact before writing details here.
4. **Pin and record versions** when you test (`docker image inspect`, `kind version`, `kubectl version`).
5. Add new products as `stacks/<name>/` + a row in the table above. Remove what you don't use.

## Caveats

- Images are pinned to exact tags (`prom/prometheus:v3.15.0`, `grafana/grafana-oss:12.4.3`, `prom/node-exporter:v1.12.1`); the digests tested are in the per-product notes. Major-only tags were used before, but `grafana/grafana-oss:12` does not exist on Docker Hub and the first start failed. Bump tags deliberately and record the new version.
- `node-exporter` mounts the host root read-only (needed for host metrics). Remove it if you don't need NUC metrics.
- The script used to install the latest stable kubectl (v1.37.1 on 2026-10-15) while kind v0.27.0 creates a v1.32.2 cluster: outside kubectl's ±1 minor support. Fixed in repo, not re-run on the NUC: kubectl is pinned to v1.32.13 and the node image to `kindest/node:v1.32.2` (by digest). Bump `KIND_VERSION`, `KIND_NODE_IMAGE` and `KUBECTL_VERSION` together.
- kind runs Kubernetes nodes as privileged containers on the NUC's Docker; treat the cluster as disposable and don't run untrusted workloads that need host access.
- Memory: limits are Prometheus 512 MB + Grafana 512 MB; measured right after start: about 31 MiB + 108 MiB + 4 MiB (node-exporter); host used memory 1.4 → 1.8 GiB of 30 GiB. After about 1 h: Prometheus 51 MiB, Grafana 98 MiB, node-exporter 9 MiB. kind (2 nodes, no container memory limit): control-plane 489 MiB + worker 113 MiB; host used memory 1.6 → 2.2 GiB.
- Prometheus/Grafana volumes are not yet included in the encrypted backup scripts.

## 日本語

**状況（2026-10-15）：Prometheus＋Grafana（＋node-exporter）と kind クラスタが NUC 上で稼働中**。確認済み：ヘルスチェック、loopback 限定、収集対象3つが `up`、Grafana の管理者ログインと Prometheus データソース経由のクエリ、kind の2ノード `Ready` と API の `127.0.0.1:6443` 限定。未確認：ブラウザでの画面操作、ダッシュボード、kind 上のワークロード。結果：[build-progress.md](build-progress.md) §0.5、製品ごとのメモ [playground/](playground/)。

### 目的

常設の監視ボックスに加えて、**OSS 製品のプレイグラウンド**として使います。動かす → 使ってみた感想を残す → 脆弱性診断 → バグ修正・上流への貢献、という流れです。

| 製品 | 役割 | 場所 | 状態 |
|---|---|---|---|
| Uptime Kuma | 監視・通知（既存） | `stacks/uptime-kuma` | ✅ 稼働中 |
| Prometheus | メトリクス | `stacks/observability`（`127.0.0.1:9090`） | ✅ 稼働中（v3.15.0）· ✅ 収集対象3つ `up` — [メモ](playground/prometheus.md) |
| Grafana OSS | ダッシュボード | `stacks/observability`（`127.0.0.1:3000`） | ✅ 稼働中（12.4.3）· ✅ ログイン・データソース経由のクエリ · ⬜ ダッシュボード — [メモ](playground/grafana.md) |
| Kubernetes (kind) | 使い捨てクラスタ（control-plane 1＋worker 1） | `stacks/kubernetes`（API `127.0.0.1:6443`） | ✅ 稼働中（kind v0.27.0、k8s v1.32.2、2ノード `Ready`）· kubectl のバージョン差はリポジトリで修正済み（v1.32.13 に固定）、実機では未再実行 — [メモ](playground/kubernetes.md) |
| Kyverno | Kubernetes ポリシーエンジン（5つ目） | [設計のみ](playground-kyverno-design.md) | 📝 設計済み・未実装 |

### 起動・停止（NUC 上）

常設スタックは `~/home-ai-lab`（ファイル単位で配置、Git clone ではない）。プレイグラウンドは、このリポジトリを `~/home-ai-engineering-lab` に clone して実行します（更新は `git pull --ff-only`）。

```bash
bash scripts/playground-run.sh observability   # Prometheus + Grafana + node-exporter
bash scripts/playground-run.sh kubernetes      # kind クラスタ "playground"
bash scripts/playground-run.sh all | status | down   # down でもボリュームは残る
```

### ルール

1. 画面・API は loopback のみ。**脆弱性診断の対象はこのラボ内だけ**（他人のホストは絶対に対象にしない）。
2. 秘密情報は Git に入れない（`.env` / kubeconfig は `chmod 600`）。
3. 製品ごとに `docs/playground/<product>.md` を作り、バージョン・試したこと・感想・発見（バグ／脆弱性）・上流の Issue/PR を残す。脆弱性は**先に上流の窓口へ非公開で報告**してから詳細を書く。
4. テスト時はバージョンを固定して記録する。
5. 製品を増やすときは `stacks/<name>/` と上の表に1行を追加。使わないものは止める。

### 注意

- イメージは正確なタグで固定（`prom/prometheus:v3.15.0`、`grafana/grafana-oss:12.4.3`、`prom/node-exporter:v1.12.1`）。digest は製品ごとのメモに記録。以前は major タグだったが、`grafana/grafana-oss:12` は Docker Hub に存在せず初回起動が失敗した。更新は意図して行い、バージョンを記録する。
- node-exporter はホストのルートを読み取り専用でマウント（NUC のメトリクス用）。不要なら外す。
- スクリプトは最新の stable の kubectl（2026-10-15 時点で v1.37.1）を入れていたが、kind v0.27.0 が作るクラスタは v1.32.2 で、kubectl のサポート範囲（±1 マイナー）外だった。リポジトリでは修正済み、実機では未再実行：kubectl を v1.32.13、ノードイメージを `kindest/node:v1.32.2`（digest 指定）に固定。上げるときは `KIND_VERSION`・`KIND_NODE_IMAGE`・`KUBECTL_VERSION` を一緒に変える。
- kind はNUCのDocker上でノードを特権コンテナとして動かす。使い捨て前提で、信頼できないワークロードは載せない。
- メモリ上限は Prometheus 512MB＋Grafana 512MB。起動直後の実測は約 31MiB＋108MiB＋4MiB（node-exporter）、ホスト全体の使用量は 30GiB 中 1.4 → 1.8GiB。約1時間後は Prometheus 51MiB、Grafana 98MiB、node-exporter 9MiB。kind（2ノード、コンテナのメモリ上限なし）は control-plane 489MiB＋worker 113MiB、ホスト全体の使用量は 1.6 → 2.2GiB。
- Prometheus/Grafana のボリュームは暗号化バックアップの対象にまだ入れていない。
