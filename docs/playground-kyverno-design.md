# Design: add Kyverno to the OSS playground / Kyverno 追加の設計

**Status: design only. Not implemented, not run.** Implementation is done locally by the owner (next step). Nothing here counts as verified.

## 1. Goal

Make the fifth playground product **Kyverno** (Kubernetes policy engine) and wire the playground so that the set is useful together:

| Product | Role in the set |
|---|---|
| Uptime Kuma | up/down alerts (running) |
| Prometheus | metrics (defined, not run) |
| Grafana | dashboards (defined, not run) |
| Kubernetes (kind) | throw-away cluster (defined, not run) |
| **Kyverno** | admission policies on the kind cluster; a good target for usage notes, vulnerability checks and upstream fixes |

Non-goals: production use, exposing anything beyond loopback, paid services, testing hosts outside this lab.

## 2. Design

### 2.1 Install
- Into the kind cluster `playground`, namespace `kyverno`, via the official Helm chart. **Pin the chart and app versions** (record them in `docs/playground/kyverno.md` when installed).
- Helm is installed by the script the same way as kind/kubectl: pinned version + checksum verification.
- Start with **1 replica** of each controller (lab, not HA). Resource limits set; memory budget to be measured (not yet).
- New script step: `scripts/playground-run.sh kyverno` (idempotent `helm upgrade --install`); `down` removes it with the cluster.

### 2.2 Policies (in Git)
- Directory `stacks/kubernetes/policies/`. Start with a small baseline, **Audit mode first**, then switch chosen ones to Enforce after observing reports:
  1. disallow `:latest` image tags
  2. require resource requests/limits
  3. disallow privileged containers / host namespaces
  4. require labels (e.g. `app.kubernetes.io/name`)
- Unit tests with the **Kyverno CLI** (`kyverno test`) against good/bad sample manifests in `stacks/kubernetes/policies/tests/`; also a live check with `kubectl apply --dry-run=server`. Both pass/fail results are recorded.
- System namespaces (`kube-system`, `kyverno`) are excluded so a bad policy cannot lock the cluster; document how to remove a policy / the webhooks if admission breaks (`kubectl delete clusterpolicy --all`, or delete the Kyverno webhook configurations).

### 2.3 Observability link
- Kyverno exposes Prometheus metrics. Prometheus runs in Docker **outside** kind, so the cluster needs a path to it. Options:
  - **A (recommended):** kind `extraPortMappings` publishing one NodePort for the Kyverno metrics service on `127.0.0.1` only; Prometheus scrapes `host.docker.internal:<port>` (add `extra_hosts`).
  - B: run Prometheus inside the cluster (heavier; duplicates the Docker stack).
  - C: skip metrics; use policy reports only.
- Grafana: one dashboard JSON (policy results, admission latency) provisioned from Git. Kuma: one HTTP monitor on Kyverno's health endpoint is optional (needs the same path).
- Decision needed from the owner on A/B/C when implementing; default is A.

### 2.4 Security rules
- All endpoints stay on loopback; cluster API `127.0.0.1:6443` only; kubeconfig `chmod 600`, never committed.
- Vulnerability checks target **only this lab's cluster**. Findings: reproduce → minimal report → disclose **privately** to upstream (Kyverno security contact) → only then write details in `docs/playground/kyverno.md` and open a fix PR.
- Policies must not weaken cluster isolation; Enforce only after Audit review.

## 3. Implementation order (each step = one PR)

1. Run the already-defined set locally (`playground-run.sh all`) and record real results in `docs/build-progress.md` (prerequisite; currently unverified).
2. Add Helm install + `kyverno` subcommand; install Kyverno; check pods Ready.
3. Add baseline policies (Audit) + CLI tests + sample manifests.
4. Metrics path (2.3) + Grafana dashboard.
5. Switch selected policies to Enforce; record behaviour.
6. `docs/playground/kyverno.md`: versions, impressions, findings.

## 4. Verification checklist (to fill in when done)

- [ ] Kyverno pods Ready; versions recorded
- [ ] `kyverno test` passes for all policies; a bad manifest is rejected in Enforce, only reported in Audit
- [ ] Policy reports appear (`kubectl get policyreport -A`)
- [ ] Prometheus target for Kyverno is UP; dashboard shows data
- [ ] Only loopback listeners (`ss -ltn`), nothing new on the LAN
- [ ] Recovery procedure (policy removal / webhook deletion) tried once
- [ ] Memory/CPU headroom measured (`scripts/ops-status.sh`)

## 5. Open questions

- Metrics path A/B/C (2.3).
- Whether to include Kyverno in the encrypted backup (policies live in Git, so probably not needed).
- Exact chart/app versions: choose at implementation time and pin.

---

## 日本語

**状況：設計のみ。未実装・未実行。** 実装は次のステップとして、オーナーがローカルで行います。検証済みの項目はありません。

### 目的
5つ目のプレイグラウンド製品として **Kyverno**（Kubernetes のポリシーエンジン）を追加し、Kuma / Prometheus / Grafana / kind と合わせて使えるようにします。用途は、使ってみた感想、脆弱性診断（このラボ内のみ）、上流への修正貢献。本番利用・LAN 公開・有料サービスは対象外です。

### 設計の要点
1. **導入**：kind クラスタ `playground` の `kyverno` 名前空間に公式 Helm チャートで導入。チャート／アプリのバージョンは固定して記録。Helm 自体もチェックサム検証つきでスクリプトが導入。1 レプリカ、リソース制限つき。`scripts/playground-run.sh kyverno`（冪等）。
2. **ポリシーは Git 管理**：`stacks/kubernetes/policies/`。まず **Audit モード**で `latest` タグ禁止／リソース要求・上限必須／特権コンテナ・ホスト名前空間禁止／ラベル必須。観察後に一部を Enforce へ。Kyverno CLI（`kyverno test`）と `kubectl apply --dry-run=server` で検証。`kube-system` と `kyverno` は除外し、壊れた場合の復旧手順（ポリシー削除／webhook 削除）を用意。
3. **監視連携**：Prometheus は kind の外（Docker）にいるため経路が必要。**案A（推奨）**：kind の `extraPortMappings` で Kyverno メトリクスの NodePort を `127.0.0.1` のみに公開し、Prometheus が `host.docker.internal` 経由で取得。案B：クラスタ内に Prometheus（重い）。案C：メトリクスなし。Grafana のダッシュボードは JSON を Git から自動読み込み。
4. **セキュリティ**：すべて loopback のみ。診断対象はこのラボのクラスタだけ。脆弱性は再現 → 最小限の報告 → **上流へ非公開で報告** → その後に詳細と修正 PR。Audit を確認してから Enforce。

### 実装順（1ステップ＝1PR）
1. 既存の定義をローカルで実行し、実結果を `docs/build-progress.md` に記録（前提）
2. Helm 導入＋`kyverno` サブコマンド、Pod が Ready になるまで
3. 基本ポリシー（Audit）＋CLI テスト＋サンプル
4. メトリクス経路＋Grafana ダッシュボード
5. 一部を Enforce にして挙動を記録
6. `docs/playground/kyverno.md` にバージョン・感想・発見を記録

### 未決事項
メトリクス経路 A/B/C、バックアップ対象にするか（ポリシーは Git にあるので不要の見込み）、バージョンの固定値。
