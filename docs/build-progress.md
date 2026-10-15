# Build progress & Final Report / 構築進捗・最終報告 (2026-10-15)

最終更新: 2026-10-15 JST（追加フェーズを §0 に追記、OSS プレイグラウンドの初回起動を §0.5 に追記）。Phase 0〜Phase 5 の導入および実機検証結果を統合した最終報告。実機での検証が済んでいない項目は合格扱いとせず、「未検証・未実施の項目」に分離して記録している。

## 0. 追加フェーズ：運用基盤の改善（2026-10-15）— **最新**

**EN summary:** Open WebUI was stopped (data kept); a read-only GitHub collector + daily Markdown report (07:00 JST, n8n) was added and is readable through MCP; alerts go through an Uptime Kuma push monitor; the backup script no longer restarts stacks that were stopped on purpose; an external heartbeat, off-device backup options and an ops runbook were prepared. **No paid service was added.** Not yet delivered: notifications (no channel), off-device backup, token-based features.
以下の「1〜9」は Phase 5 時点の最終報告で、**この節に反する記述（Open WebUI が稼働中など）は、この節が優先**です。

### 0.1 完了条件のチェック（実機検証済み／ローカル検証済み／未検証を区別）

| 完了条件 | 状態 | 根拠 |
|---|---|---|
| Open WebUI を停止し、復旧可能な状態で保存 | ✅ **実機** | `Exited (0)`、ボリューム `open-webui_open-webui-data`・`.env`・`secrets/` 保持、再起動方針 `unless-stopped`。復旧は `ops-open-webui.sh start`（**未実行**。再起動後も停止のままかも未確認） |
| n8n による GitHub 情報取得 | ✅ **実機** | n8n 画面から日次ワークフローを実行：収集 → Job ok? → Summary 成功（`repos 109 / open issues 3 / open PRs 29 / critical 0 / API 45回 / PARTIAL DATA`）。直前にジョブ単体でも成功（108リポジトリ） |
| 複数リポジトリの情報収集 | ✅ **実機** | 109リポジトリ、open issues 3、open PRs 29（fork含む。own は16件）。API 45回（無認証）。最新コミットは 8/33 件のみ（無認証の予算）→ `PARTIAL` と明記 |
| 日次 Markdown レポートの自動生成 | 🟨 | レポート生成は実機で成功。**07:00 JST の定期実行は有効化済みだが初回は未観測** |
| GitHub Actions 失敗の検出 | 🟨 **ローカルのみ** | 偽 API の自動テストで検証。実データでは確認した32リポジトリに失敗中のものがなく、実証できていない |
| 必要な異常通知の実装 | 🟨 | 検知（Kuma Push → down）は実装・テスト済み。**配送は未**（通知チャネル未設定、push トークン未登録） |
| MCP からレポートを読み取り | ✅ **実機** | n8n「MCP read-only test」で `list_reports`／`read_report(github-daily-latest.md)` 成功 |
| 既存セキュリティ設定を維持 | ✅ | UFW 変更なし、SSH 設定変更なし。新規ポート公開なし（python-jobs は `monitor-net` に参加するが公開ポートなし）。LAN ポートスキャンは前回確認（22のみ） |
| バックアップ・復旧手順の確認 | ✅ 実機（ローカル）／⬜ NUC外 | 修正版でバックアップ → 復元試験 全項目 PASS（Open WebUI の管理者 `users: 1` も確認）。timer の自動実行は未観測、NUC外コピーなし |
| 追加 LLM API 課金なし | ✅ | LLM API は未使用。追加サービス契約なし |
| GitHub ドキュメント更新 | ✅ | 本 PR |

### 0.2 実施した変更

| 変更 | 内容 |
|---|---|
| Phase 1 | Open WebUI を `docker compose stop`（削除なし）。Kuma の「Open WebUI (health)」は**一時停止**。停止前後の資源使用量を実測：[ops-runbook.md](ops-runbook.md) |
| Phase 2–3 | `python-jobs` に `github-dev-snapshot`（読み取り専用の複数リポジトリ収集）を追加。n8n ワークフロー「GitHub daily report (read-only)」（毎朝 07:00 JST ＋手動）。詳細：[github-monitoring.md](github-monitoring.md) |
| Phase 4 | Kuma に Push 監視「GitHub collector + alerts (push)」を作成。サービス監視 3 件にリトライ 2。外部 heartbeat スクリプトを作成（**未有効化**）。通知方針：[monitoring-notifications.md](monitoring-notifications.md) |
| Phase 5 | **バックアップスクリプトの修正**（下記インシデント）、対象に `jobs-state` を追加、実機で実行・復元試験。NUC外の選択肢を比較：[offsite-backup-options.md](offsite-backup-options.md)。運用手順書：[ops-runbook.md](ops-runbook.md) |

### 0.3 発見した問題と対処

1. **夜間バックアップが Open WebUI を勝手に再起動する不具合**（旧スクリプトは全スタックを停止→全スタックを起動）。停止中のスタックは動いていたものだけ止めて動いていたものだけ戻すよう修正し、**次の夜間実行（03:38 UTC）の前に実機へ導入**。スタブでの論理テストと実機での実行で、Open WebUI が停止のままであることを確認。
2. **同日再実行で、より不完全なレポートが充実したレポートを上書きした**（無認証 API 枠を使い切った状態で再実行）。保護ルールを実装したが、**旧形式のスナップショットには効かなかった**（保存済みフィールドに依存していたため）。内容から毎回計算する方式に修正し、旧形式のテストを追加。**修正版を実機へ反映済み**。上書きされた（より充実した）レポートは、直前のバックアップ `home-ai-lab-20261014T221757Z`（22:17 UTC）の `jobs-reports.tar` に残っている。いずれも翌朝の定期実行で置き換わる。
3. **MCP 自己テストの項目数を「36」と誤記していた**（正しくは 34）。文書を訂正。
4. **バックアップ timer の時刻表記が不正確だった**：NUC のタイムゾーンは UTC なので、03:30 は日本時間 **12:30**。文書を訂正。
5. Kuma の Push 監視作成画面のスクリーンショットに、トークンの先頭数文字が写った → 保存前にトークンを再生成して対処（Kuma はループバック限定で外部から到達不可）。以後その画面は撮影しない。
6. 共有の GitHub 無認証枠（60回/時・家庭の IP 全体）は PC とNUCで共有される → 設計に反映（Search API の一括取得、予算、部分レポート、トークンの案内）。

### 0.4 残課題（優先順）

| # | 項目 | 担当 |
|---|---|---|
| 1 | 通知チャネルを Kuma に追加（メール/SMTP 推奨） | あなた（認証情報） |
| 2 | Kuma の Push URL を `jobs-admin.sh set-kuma-push` で登録 | あなた（トークン） |
| 3 | 翌朝 07:00 JST の定期実行の結果を確認（n8n *Executions* とレポート） | あなた／次回 |
| 4 | NUC外バックアップの保存先を決める | あなた（[offsite-backup-options.md](offsite-backup-options.md)） |
| 5 | 外部 heartbeat を有効化（無料チェックを作成） | あなた |
| 6 | （任意）読み取り専用 GitHub トークン → 非公開リポジトリ・Dependabot・予算拡大 | あなた |
| 7 | 再起動後も Open WebUI が停止のままか確認（次回の計画再起動時） | 次回 |

### 0.5 OSS プレイグラウンド：Prometheus＋Grafana の初回起動（2026-10-15）

**EN summary:** Prometheus v3.15.0, Grafana OSS 12.4.3 and node-exporter v1.12.1 were started on the NUC with `scripts/playground-run.sh observability`. Health checks pass and both UIs listen on `127.0.0.1` only. The first start failed because `grafana/grafana-oss:12` does not exist on Docker Hub; all three images are now pinned to exact tags. Scrape targets, the Grafana UI and kind are **not yet verified**.

| 項目 | 状態 | 根拠 |
|---|---|---|
| Prometheus 起動 | ✅ **実機** | `GET /-/ready` → 200（ホストから）。`prom/prometheus:v3.15.0` |
| Grafana 起動 | ✅ **実機** | `GET /api/health` → `database: ok`、`version: 12.4.3` |
| loopback 限定 | ✅ **実機** | `docker port` と `ss -ltn` で `127.0.0.1:9090`・`127.0.0.1:3000` のみ。node-exporter は公開ポートなし |
| 資源使用量 | ✅ **実機**（起動直後） | prometheus 31MiB／grafana 108MiB／node-exporter 3.5MiB。ホスト使用量 1.4 → 1.8GiB（30GiB 中） |
| 収集対象（prometheus・node・grafana）の取得 | ⬜ **未確認** | 起動5秒後の照会ではすべて `health: unknown`（初回の収集前。間隔30秒）。`/targets` で要確認 |
| Grafana へのログイン・データソース・ダッシュボード | ⬜ 未確認 | 管理者パスワードは `stacks/observability/.env`（`chmod 600`、非表示） |
| Kubernetes (kind) | ⬜ 未実行 | 今回は対象外 |
| Prometheus/Grafana のボリュームの暗号化バックアップ | ⬜ 未対応 | 従来どおり対象外 |

発見した問題と対処：

1. **`grafana/grafana-oss:12` が Docker Hub に存在せず、初回の `docker compose up` が `not found` で失敗**（Grafana は `12.4.3` のような完全なバージョンしか公開していない）。3つのイメージを正確なタグに固定（`v3.15.0`／`12.4.3`／`v1.12.1`）。digest は [playground/prometheus.md](playground/prometheus.md)・[playground/grafana.md](playground/grafana.md) に記録。上流の不具合ではなく、このラボの定義の誤り。
2. **NUC 上にこのリポジトリの clone がなかった**（常設スタックは `~/home-ai-lab` にファイル単位で配置）。公開リポジトリを `~/home-ai-engineering-lab` に clone して実行。手順を [playground.md](playground.md) に追記。
3. SSH の LoginGraceTime が短いため、鍵のパスフレーズ入力が遅れると接続が切られる（`Connection closed`）。手順上の注意として記録（設定は変更していない）。

---

## 1. 稼働サービス

ホスト側の待ち受けは **TCP 22（LAN のみ）** と、下記3つの **`127.0.0.1` ポート** だけです。Uptime Kuma の監視は **5件（Kuma 自身、NUC SSH、n8n、Open WebUI、MCP）** です。

| サービス | 状態 | 待ち受け | 主な保護 |
| :--- | :--- | :--- | :--- |
| **Docker Engine 29.9.0 / Compose 5.6.0** | 稼働 | TCP 待ち受けなし | `docker` グループ未使用（`sudo docker` 運用） |
| **Uptime Kuma 2.x** | healthy | `127.0.0.1:3001` | 管理者認証、SQLite |
| **n8n 2.43.5** | 稼働 | `127.0.0.1:5678` | オーナー認証、公開 API・コマンド実行ノード無効 |
| **python-jobs（内部サービス）** | healthy | 公開ポートなし | Bearer 認証、許可リスト、`read-only` rootfs |
| **Open WebUI v0.12.0-slim** | healthy | `127.0.0.1:8300` | 管理者認証、サインアップ無効、テレメトリ無効 |
| **MCP サーバー（自前の最小実装）** | healthy | 公開ポートなし、内部専用ネットワーク | クライアント別トークン、ツール許可リスト、監査ログ |
| **暗号化バックアップ** | timer 有効 | 毎日 03:30 UTC（日本時間 12:30）頃 | age 公開鍵暗号、7世代 |

## 2. アクセス方法

管理画面はすべてループバック限定です。Windows から SSH トンネルで入ります（鍵は `ssh-agent` に登録済みであることが前提です。NUC の IP は公開リポジトリに載せていません）。

```bash
ssh -N -L 3001:127.0.0.1:3001 -L 5678:127.0.0.1:5678 -L 8300:127.0.0.1:8300 moruku@<NUC の IP>
```

- **Kuma**: `http://127.0.0.1:3001`
- **n8n**: `http://localhost:5678`
- **Open WebUI**: `http://localhost:8300`
- **MCP / python-jobs**: 内部専用で、画面はありません。n8n の中から呼びます。

## 3. テスト結果（検証済み）

| 項目 | 結果 |
| :--- | :--- |
| **NUC 再起動（SSH / UFW / Docker / Kuma の自動復帰、DB 保持）** | **合格**。SSH は約20秒で復帰。`sshd -T` の4設定（`PermitRootLogin no`, `PubkeyAuthentication yes`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`）と UFW ルールは再起動前後で同一。 |
| **Kuma、n8n、Open WebUI の認証と、ポートがループバックのみであること** | **合格** |
| **python-jobs の否定テスト** | **合格**。`401` / `400` / `403` / `404` がすべて期待どおり応答。 |
| **n8n の読み取り専用 GitHub ワークフロー** | **成功** |
| **n8n から MCP を呼ぶワークフロー** | **成功**（ツール一覧と時刻を取得）。 |
| **MCP のローカル自己テスト** | **34 項目すべて合格**（認証、パストラバーサル、タイムアウト、レート制限、ログにトークンが出ないこと）。 |
| **外部公開されないこと** | **合格**。公開ポートなし、MCP の外向き通信ブロック、LAN 上の別マシンから 1051 ポートをスキャンして開放は `22` のみ。 |
| **バックアップ → 復号 → 復元試験** | **合格**。Kuma、n8n、Open WebUI のデータ整合性を確認し、n8n は復元データで起動してワークフローを読み込み可能。 |
| **プロバイダーへの到達性（認証なし）** | **確認済み**。OpenAI と Anthropic は `401`、Gemini と RunPod は `404`（いずれもネットワーク到達を確認）。 |

## 4. フェーズ別PR構成

| PR | 内容 |
| :--- | :--- |
| **#1** | Phase 2: Docker、Kuma、暗号化バックアップ |
| **#2** | Phase 3: n8n と Python ジョブ（#1 の上にスタック） |
| **#3** | Phase 4: Open WebUI と API キー管理方式（#2 の上にスタック） |
| **#4** | Phase 5: MCP サーバー（#3 の上にスタック） |

## 5. 未検証・未実施の項目（合格扱いにしていません）

### 実機での検証が済んでいないもの
- [ ] **API キーを使った外部 LLM への実接続（OpenAI、Anthropic、Gemini、RunPod）**: キー未登録で、Open WebUI のモデル一覧は空です。RunPod は課金が発生するため何も起動していません。
- [ ] **Open WebUI から MCP ツールを使えるか**: 到達性と、認証なしの `401` までしか確認していません。管理画面での登録が必要です。
- [ ] **MCP のタイムアウト・レート制限・権限外の拒否の実機実行**: ローカル自己テストのみで実機では未実行です。実機の監査ログの成功呼び出しの行も未取得です。
- [ ] **公式 MCP クライアントとの互換性検証**: 自前の最小 MCP 実装のため、公式 MCP クライアントでの互換性は未検証です。
- [ ] **バックアップ timer の自動実行確認**: 次回 03:30 UTC（日本時間 12:30）頃の自動実行までは未確認です。
- [ ] **Open WebUI（管理者作成後）と MCP の分を含むバックアップの実機実行・復元試験**: スクリプト更新後のフル復元試験は未確認です。
- [ ] **`hello-world` の出力全文と `vgs`/`lvs` の全文記録**: 導入スクリプトは最後まで完了していますが全文ログは未記録です。

### 未実施の作業
- [ ] **NUC 外へのバックアップ保存**: 保存先が未決定のため保留です。現状は NUC のディスク故障や盗難に対して保護されません。
- [ ] **Kuma の通知先、n8n のエラー通知、Kuma 停止時の外部検知**: いずれも未設定です。
- [ ] **外部 AI API の基本構成（キー・予算上限の承認待ち）**: アプリ内の費用上限は未実装で、プロバイダー側の月額ハードリミットが前提です。
- [ ] **GitHub 連携（読み取り専用トークンの設計）**: GitHub 側の書き込みはしていません。
- [ ] **全フェーズ（PR #1〜#4）の `main` ブランチへの最終統合確認**

## 6. 作業中に起きた問題と、その対処

1. **Phase 3 完了時から約29分間、「NUC SSH (host)」監視が Down になった問題**:
   - **原因**: 当時は見落としていましたが、Kuma を共有ネットワークに接続したことでホストへの通信の送信元が変わり、UFW の許可ルールに合わなくなったためです。
   - **対処**: Kuma の既定経路を元のネットワーク（`172.30.0.0/24`）に固定して修正しました（`scripts/fix-kuma-gw.sh`）。UFW は緩めていません。
2. **n8n のエラー出力に認証トークンが含まれ、実行履歴と出力に露出した問題**:
   - **対処**: ワークフローを修正し、該当の実行履歴を削除した上で、トークンをローテーションしました。なお、通信自体が失敗した場合はヘッダーが履歴に残る可能性があります（実行履歴は7日で自動削除されます）。
3. **Open WebUI の管理者アカウント未作成のままサインアップを閉じてしまった問題**:
   - **対処**: `/api/config` で管理者未作成と判明したため、一時的にサインアップを開け直して管理者アカウントを作成したあと、再度ロック（`lock-signup`）しました。

## 7. 変更・承認したこと（設計書との関係）

- **UFW ルール追加**: Kuma 専用サブネット（`172.30.0.0/24`）からホストの **TCP 22 だけを許可するルールを1件追加** しました（ロールバック手順つきで承認済み）。
- **設計書との整合性**: 設計書（`docs/architecture.md` の ADR）と矛盾する変更はありません。

## 8. 次の手順（優先順）

1. **バックアップの NUC 外保存先を決める**: 保存先が決まったら暗号化したまま転送し、復元試験まで進める。
2. **プロバイダー側で用途専用 API キーと月額上限を設定する**: API キーを渡す前にプロバイダー側でハードリミットを設定し、その後 `owui-admin.sh set-key` で登録して実接続を検証する。
3. **スタック PR（#1〜#4）の変更を `main` に完全統合する**: レビュー反映および `main` ブランチへのマージを完了させる。
4. **不要なターミナルタブの整理**: ターミナルパネルに残っている作業用タブのうち、SSH トンネル用の `c11` 以外（`c14`、`c15`、`c16`）を閉じる。

## 9. 構築済み環境サマリー・保安事項

- **OS / Hardware**: Ubuntu Server 24.04 LTS / Intel NUC 11 Performance (`NUC11PAHi5`, Core i5-1135G7, RAM 32GB [実効30GiB, swap 8GiB], Crucial P5 NVMe 1TB)
- **Storage**: LVM `/` = LV 100GiB（使用約11GiB、空き約82GiB）、PV 928.5GiB（残りはVG未割当）。Dockerデータは `/var/lib/docker` 上
- **Network / Security**:
  - ローカルIPはこの公開リポジトリに書かない。
  - SSH秘密鍵・APIキー・パスワードをコミット/チャットに貼らない。
  - `docker` グループ追加は root 相当権限のため `sudo docker` 運用を維持する。
