# MCP / 内部API（Phase 5）

最終更新: 2026-10-15 JST。**状態: 読み取り専用MCPサーバーを導入し、n8nからの呼び出し・分離・非公開を実機で検証済み。Open WebUIからのMCPツール利用は未検証。**

## 構成
`stacks/mcp`（サーバー実装 `mcp-server/server.py`、標準ライブラリのみ、約300行）。

```
n8n ─┐                      ┌─ tools: echo / server_time / list_reports / read_report（全て readOnlyHint）
Open WebUI ─ mcp-net (internal) ─ mcp-server:8080 ─ audit.jsonl（ボリューム mcp_mcp-audit）
Uptime Kuma ┘ (/healthz のみ)         └─ /data/reports（n8n_jobs-reports を :ro でマウント）
```
- プロトコル: MCP Streamable HTTP の**最小実装**（JSON応答のみ。`initialize` / `ping` / `tools/list` / `tools/call`、通知は202。SSE・バッチ・リソース・プロンプトは非対応）。対応バージョン 2025-06-18 / 2025-03-26 / 2024-11-05。
- 呼び出し: `POST http://mcp-server:8080/mcp`（`Authorization: Bearer <token>`）。`GET /healthz` のみ無認証。

## セキュリティ制御
| 項目 | 実装 |
|---|---|
| 外部公開の防止 | **公開ポートなし**。`mcp-net` は `internal: true`（ゲートウェイなし＝インターネット・ホストへ出られない）。UFW変更なし |
| 認証 | クライアント別Bearerトークン（`.env`、32文字以上、`hmac.compare_digest` で全トークンと比較） |
| 認可（最小権限） | `policy.json` でクライアントごとのツール許可リスト。`tools/list` は許可分のみ、許可外の `tools/call` は `-32003`。例: Open WebUIは `read_report` 不可 |
| タイムアウト | HTTP読み取り10秒、ツール実行5秒（超過は `-32002`）、本文上限64KiB（413） |
| レート制限 | クライアント別（n8n 60/分、Open WebUI 30/分）。超過は429 |
| Origin検査 | `Origin` ヘッダー付きは403（DNSリバインディング対策。サーバー間通信は不要） |
| ファイルアクセス | `read_report` は `*.md`・名前形式検査・`realpath` で報告ディレクトリ直下のみ・64KiB上限。マウント自体が `:ro` |
| コンテナ | 非root(10002)、read-only rootfs、`cap_drop: ALL`、no-new-privileges、メモリ128MB、pids 64 |
| 監査ログ | 1リクエスト1行のJSON（ts, ip, client, method, tool, status, http, ms, `args_sha256`, `args_bytes`）。**トークンも引数の値も記録しない**。`/var/log/mcp/audit.jsonl`（5MB×5世代ローテーション）＋stdout。バックアップ対象 |

## 検証結果
**ローカル自己テスト（`python tests/mcp_selftest.py`、34項目、全PASS）**: 認証(401)、Origin(403)、バージョン交渉、ツール一覧のクライアント別フィルタ、権限外ツール拒否、パストラバーサル各種（`../`、`%2f`、`/`、先頭ドット、NUL、拡張子）、不正JSON(-32700)、バッチ拒否、413、**ツールタイムアウト(-32002)**、**レート制限(429)**、監査ログにトークン/引数値が含まれないこと。

**実機（`scripts/phase5-run.sh` の出力、2026-10-15）**
- 公開ポート: `docker port` 空。ホストの docker-proxy 待ち受けは 127.0.0.1:3001/5678/8300 のみ（MCPなし）
- `mcp-net`: `internal=true`、メンバーは mcp-server / n8n / open-webui / uptime-kuma のみ。python-jobs からは名前解決不可
- mcp-server の外向き通信（1.1.1.1:443、api.github.com、ホスト172.17.0.1:22）はすべてブロック
- クライアントコンテナからの未認証アクセス: `/healthz` 200、`/mcp` 401（n8n, Open WebUI）
- **LAN上の別ホスト（Windows）から NUC の1051 TCPポートをスキャン: 開いていたのは22のみ**。コンテナ網(172.30/31/32.x)へは到達不可
- UFW規則は変更なし。Kuma→ホスト22は到達可（Phase 3/4の再発防止確認）
- **n8nワークフロー「MCP read-only test」**（n8nのHeader Auth資格情報で認証）: `tools/list` が4ツールを返し、`server_time` が時刻を返した
- Kuma監視「MCP server (healthz)」Up

## 未確認・制約
- **Open WebUI → MCP のツール利用は未検証**（ネットワーク到達と401のみ確認）。Open WebUIの管理画面でMCPサーバー（URL `http://mcp-server:8080/mcp`、Bearer `MCP_TOKEN_OPENWEBUI`）を登録する手順は未実施。トークンはNUC上の `~/home-ai-lab/mcp/.env` から本人が取得し、チャットに貼らない。
- 実機上でのタイムアウト/レート制限/権限外拒否は、ローカルテストのみ（実機では未実行）。実機の監査ログの内容（成功呼び出し行）は導入直後の確認時点では未取得。
- 実装は**自前の最小MCP**。公式MCPクライアント/Inspectorとの相互運用は未検証。仕様準拠を厳密に求める用途では公式SDKへの置換を検討。
- 外部AI（LLM）側からMCPを呼ぶ経路は、APIキー未登録のため未検証。
- n8nの実行履歴には、**通信エラー時にAuthorizationヘッダーが残り得る**（Phase 3と同様の残存リスク。7日で削除）。
- 内部ネットワーク上のクライアント（n8n, Open WebUI, Kuma）は同一ネットワークのため、**他クライアントのトークンなしで `/healthz` に到達できる**（無認証は `/healthz` のみ）。クライアント間の通信遮断（個別ネットワーク）は未実装。

## 運用
- ツール追加: `server.py` の `TOOLS` に追加し、`policy.json` で許可クライアントを明示（**未許可なら誰も呼べない**）。**書き込み系ツールは追加しない**（追加する場合は別途承認・人間の承認フローを設計）。
- クライアント追加: `policy.json` に `token_env` を追加し `.env` へトークンを生成。
- トークンローテーション: `ROTATE_MCP_TOKENS=1 bash ~/phase5-run.sh`（n8n資格情報は自動で再取込み。Open WebUI側は管理画面で再入力が必要）。
- 監査ログ確認: `sudo docker exec mcp-server tail -n 50 /var/log/mcp/audit.jsonl`
- ロールバック: `cd ~/home-ai-lab/mcp && sudo docker compose down`（ボリューム保持）。n8n/Open WebUI/Kumaの `compose.yaml` から `mcp` ネットワークを外して `up -d`。`docker network rm mcp-net` は別途承認。

## 追記（2026-10-15）：GitHub 日次レポートの読み取り
- MCP が読み取り専用でマウントしているレポート用ボリューム（`n8n_jobs-reports`）に、GitHub 収集ジョブが `github-daily-YYYY-MM-DD.md` と `github-daily-latest.md` を書き込む（詳細：[github-monitoring.md](github-monitoring.md)）。
- **実機で確認済み：** n8n「MCP read-only test」が `list_reports`（3ファイルを列挙）と `read_report`（`github-daily-latest.md` の本文）に成功。MCP 側のコード変更はなし（既存の名前検証・64KiB 上限・読み取り専用マウントのまま）。
- 状態の JSON スナップショット（`jobs-state`）は MCP に**マウントしていない**（読めない）。Open WebUI は停止中のため、AI チャットクライアントからの読み取りは未検証。
