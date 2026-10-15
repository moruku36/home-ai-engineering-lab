# OSS Playground / OSS プレイグラウンド

**Status (2026-10-15): Prometheus + Grafana (+ node-exporter) are running on the NUC** (health checks and loopback-only ports verified; scrape targets and the Grafana UI not yet checked). **Kubernetes (kind) has not been run yet.** Results: [build-progress.md](build-progress.md) §0.5 and the per-product notes in [playground/](playground/).

## Purpose

Besides the always-on monitoring box, the lab is a **playground for open-source products**: run them, write down impressions, run vulnerability checks, and prepare bug fixes / contributions upstream.

| Product | Role | Where | Status |
|---|---|---|---|
| Uptime Kuma | monitoring / alerts (already in the lab) | `stacks/uptime-kuma` → `127.0.0.1:3001` | ✅ running (see README) |
| Prometheus | metrics | `stacks/observability` → `127.0.0.1:9090` | ✅ running (v3.15.0) · ⬜ targets not checked — [note](playground/prometheus.md) |
| Grafana OSS | dashboards | `stacks/observability` → `127.0.0.1:3000` | ✅ running (12.4.3) · ⬜ UI not tried — [note](playground/grafana.md) |
| Kubernetes (kind) | throw-away cluster (1 control-plane + 1 worker) | `stacks/kubernetes` → API `127.0.0.1:6443` | ⬜ not run yet |
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
- kind runs Kubernetes nodes as privileged containers on the NUC's Docker; treat the cluster as disposable and don't run untrusted workloads that need host access.
- Memory: limits are Prometheus 512 MB + Grafana 512 MB; measured right after start: about 31 MiB + 108 MiB + 4 MiB (node-exporter); host used memory 1.4 → 1.8 GiB of 30 GiB. kind (2 nodes, roughly 1.5–2 GB) not measured yet.
- Prometheus/Grafana volumes are not yet included in the encrypted backup scripts.

## 日本語

**状況（2026-10-15）：Prometheus＋Grafana（＋node-exporter）は NUC 上で稼働中**（ヘルスチェックと loopback 限定は確認済み。収集対象と Grafana 画面は未確認）。**Kubernetes (kind) は未実行**。結果：[build-progress.md](build-progress.md) §0.5、製品ごとのメモ [playground/](playground/)。

### 目的

常設の監視ボックスに加えて、**OSS 製品のプレイグラウンド**として使います。動かす → 使ってみた感想を残す → 脆弱性診断 → バグ修正・上流への貢献、という流れです。

| 製品 | 役割 | 場所 | 状態 |
|---|---|---|---|
| Uptime Kuma | 監視・通知（既存） | `stacks/uptime-kuma` | ✅ 稼働中 |
| Prometheus | メトリクス | `stacks/observability`（`127.0.0.1:9090`） | ✅ 稼働中（v3.15.0）· ⬜ 収集対象は未確認 — [メモ](playground/prometheus.md) |
| Grafana OSS | ダッシュボード | `stacks/observability`（`127.0.0.1:3000`） | ✅ 稼働中（12.4.3）· ⬜ 画面は未操作 — [メモ](playground/grafana.md) |
| Kubernetes (kind) | 使い捨てクラスタ（control-plane 1＋worker 1） | `stacks/kubernetes`（API `127.0.0.1:6443`） | ⬜ 未実行 |
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
- kind はNUCのDocker上でノードを特権コンテナとして動かす。使い捨て前提で、信頼できないワークロードは載せない。
- メモリ上限は Prometheus 512MB＋Grafana 512MB。起動直後の実測は約 31MiB＋108MiB＋4MiB（node-exporter）、ホスト全体の使用量は 30GiB 中 1.4 → 1.8GiB。kind（約1.5〜2GB）は未計測。
- Prometheus/Grafana のボリュームは暗号化バックアップの対象にまだ入れていない。
