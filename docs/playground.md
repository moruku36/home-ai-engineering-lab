# OSS Playground / OSS プレイグラウンド

**Status: definitions and scripts are in this repo; they have NOT yet been run on the NUC.** Nothing below is counted as "verified" until you (or a later session on the NUC) run it and record the result in [build-progress.md](build-progress.md).

## Purpose

Besides the always-on monitoring box, the lab is a **playground for open-source products**: run them, write down impressions, run vulnerability checks, and prepare bug fixes / contributions upstream.

| Product | Role | Where | Status |
|---|---|---|---|
| Uptime Kuma | monitoring / alerts (already in the lab) | `stacks/uptime-kuma` → `127.0.0.1:3001` | ✅ running (see README) |
| Prometheus | metrics | `stacks/observability` → `127.0.0.1:9090` | ⬜ not run yet |
| Grafana OSS | dashboards | `stacks/observability` → `127.0.0.1:3000` | ⬜ not run yet |
| Kubernetes (kind) | throw-away cluster (1 control-plane + 1 worker) | `stacks/kubernetes` → API `127.0.0.1:6443` | ⬜ not run yet |

Also in the stack: `node-exporter` (host metrics, no published port).

## Start / stop (on the NUC)

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

- Image tags use major versions (`prom/prometheus:v3`, `grafana/grafana-oss:12`, `prom/node-exporter:v1`); pin exact digests when a test must be reproducible.
- `node-exporter` mounts the host root read-only (needed for host metrics). Remove it if you don't need NUC metrics.
- kind runs Kubernetes nodes as privileged containers on the NUC's Docker; treat the cluster as disposable and don't run untrusted workloads that need host access.
- Memory: Prometheus 512 MB + Grafana 512 MB + kind (2 nodes, roughly 1.5–2 GB) — check headroom with `scripts/ops-status.sh` first. Not measured yet.
- Prometheus/Grafana volumes are not yet included in the encrypted backup scripts.

## 日本語

**状況：定義とスクリプトはリポジトリに追加済み。NUC 上ではまだ実行していません**（実行・記録するまで「検証済み」とは扱いません）。

### 目的

常設の監視ボックスに加えて、**OSS 製品のプレイグラウンド**として使います。動かす → 使ってみた感想を残す → 脆弱性診断 → バグ修正・上流への貢献、という流れです。

| 製品 | 役割 | 場所 | 状態 |
|---|---|---|---|
| Uptime Kuma | 監視・通知（既存） | `stacks/uptime-kuma` | ✅ 稼働中 |
| Prometheus | メトリクス | `stacks/observability`（`127.0.0.1:9090`） | ⬜ 未実行 |
| Grafana OSS | ダッシュボード | `stacks/observability`（`127.0.0.1:3000`） | ⬜ 未実行 |
| Kubernetes (kind) | 使い捨てクラスタ（control-plane 1＋worker 1） | `stacks/kubernetes`（API `127.0.0.1:6443`） | ⬜ 未実行 |

### 起動・停止（NUC 上）

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

- イメージは major タグ。再現性が要るテストでは digest で固定。
- node-exporter はホストのルートを読み取り専用でマウント（NUC のメトリクス用）。不要なら外す。
- kind はNUCのDocker上でノードを特権コンテナとして動かす。使い捨て前提で、信頼できないワークロードは載せない。
- メモリ目安は Prometheus 512MB＋Grafana 512MB＋kind（約1.5〜2GB）。未計測。先に `scripts/ops-status.sh` で余裕を確認。
- Prometheus/Grafana のボリュームは暗号化バックアップの対象にまだ入れていない。
