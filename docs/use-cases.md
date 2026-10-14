# What can the lab do? / 何ができる？

English first, Japanese below. "Status" is what was actually verified on 2026-10-15.
英語が先、日本語が後。「状態」は2026-10-15時点で実際に確認できたことです。

## In one sentence / ひとことで

**EN:** A quiet little box at home that runs your AI automations, gives AI a safe toolbox, watches itself, and backs itself up — while the big AI models stay in the cloud.
**JA:** 自宅に置いた静かな小箱が、AIの自動化を動かし、AIに安全な道具箱を渡し、自分を監視し、自分でバックアップを取ります。大きなAIモデルはクラウド側に任せます。

## Use cases / ユースケース

| Use case | EN: how it helps | JA: どう役立つか | Status / 状態 |
|---|---|---|---|
| **Watch a GitHub repo** | Fetch public repo metadata on demand or on a schedule and save a Markdown report; no write access needed. | 公開リポジトリの情報を手動／定期で取得し、Markdownで保存。書き込み権限は不要。 | ✅ Works (manual run). Scheduling not set up. / 手動実行で動作。定期実行は未設定 |
| **Compare several LLMs** | One browser UI for OpenAI, Anthropic, Gemini and RunPod-hosted models. | 1つのブラウザUIで複数社のLLMを比較。 | 🟡 UI ready; **needs your API keys**. / UIは準備済み。**APIキーが必要** |
| **Safe tools for AI (MCP)** | AI clients can call read-only tools through one authenticated, audited door instead of getting broad access. | AIには広い権限を渡さず、認証・監査つきの1つの入口から読み取り専用ツールだけ呼ばせる。 | ✅ From n8n · 🟡 Open WebUI not verified / n8nからは動作・Open WebUIは未検証 |
| **Try OSS / MCP tools safely** | Run experiments in containers; delete them when done; your PC stays clean. | コンテナで試して捨てる。開発PCを汚さない。 | ✅ The pattern is in place (Compose stacks). / 仕組みは整備済み |
| **Know when something breaks** | Uptime checks for SSH, n8n, Open WebUI, MCP and Kuma itself. | SSH・n8n・Open WebUI・MCP・Kuma自身の死活を監視。 | ✅ 5 monitors · ⬜ no notifications yet / 監視5件・通知は未設定 |
| **Use an external GPU when needed** | Point Open WebUI at an authenticated RunPod OpenAI-compatible endpoint; start it only when you need it. | 必要な時だけ、認証つきRunPodのOpenAI互換エンドポイントを使う。 | ⬜ Not set up (costs money). / 未設定（課金あり） |
| **Recover after a failure** | Daily encrypted backup and a tested restore. | 毎日の暗号化バックアップと、試験済みの復元手順。 | ✅ Local · ⬜ off-device copy missing / NUC内のみ・NUC外は未 |

## Try it (after tunnelling in) / 試してみる（SSHトンネル接続後）

1. **n8n** → open workflow **"GitHub repo metadata (read-only)"** → *Execute*. You should see `repo | stars | open issues | pushed`.
   **n8n** で「GitHub repo metadata (read-only)」を開き *Execute*。リポジトリ名・スター数・Issue数・最終pushが表示されます。
2. **n8n** → workflow **"MCP read-only test"** → *Execute*. You should see the tool list (`echo, server_time, list_reports, read_report`) and the server time.
   **n8n** で「MCP read-only test」を実行。ツール一覧とサーバー時刻が表示されます。
3. **Uptime Kuma** → the dashboard shows the monitors; stop a container and watch it turn red (intentional-failure test is *not* done yet).
   **Uptime Kuma** のダッシュボードで監視状況を確認。（意図的な停止試験は未実施）
4. **Open WebUI** → add an API key first with `owui-admin.sh set-key <provider>` (see [ai-api-key-management.md](ai-api-key-management.md)).
   **Open WebUI** は、先に `owui-admin.sh set-key <provider>` でAPIキーを登録（[ai-api-key-management.md](ai-api-key-management.md) 参照）。

## How to judge the value / 価値の測り方

**EN:** After a month: hours of manual work saved, job success rate, outages, API cost, upkeep time. Stop services that are not used. If CPU inference is too slow, hand the work to an external GPU/API.
**JA:** 1か月運用後に、手作業の削減時間・ジョブ成功率・障害・API費用・保守工数を評価。使わないサービスは止める。CPU推論が遅ければ外部GPU/APIに任せる。

## What it deliberately does not do / 意図的にやらないこと

- **EN:** run large local LLMs or GPU training; expose anything to the Internet without authentication; write to GitHub or other external services without explicit approval; run untrusted code (no self-hosted CI runner).
- **JA:** 大規模ローカルLLM／GPU学習、認証なしのインターネット公開、明示承認なしの外部サービスへの書き込み、未信頼コードの実行（self-hosted CI Runnerなし）。
