# What can the lab do? / 何ができる？

English first, Japanese below. "Status" is what was actually verified on 2026-10-15. / 英語が先、日本語が後。「状態」は2026-10-15時点で実際に確認できたことです。

## In one sentence / ひとことで

**EN:** A quiet little box at home that watches your GitHub projects every morning, tells you only when something really needs attention, watches itself, and backs itself up — without any paid AI service.
**JA:** 自宅の静かな小箱が、毎朝あなたの GitHub プロジェクトの状況をまとめ、本当に対応が必要なときだけ知らせ、自分自身を監視し、自分でバックアップを取ります。有料の AI サービスは使いません。

## Use cases / ユースケース

| Use case | EN: how it helps | JA: どう役立つか | Status / 状態 |
|---|---|---|---|
| **Morning GitHub overview** | One Markdown report: what changed, open PRs/issues, stale items, failed Actions, Dependabot (with a token), diff vs. yesterday. | 1枚のレポートで、更新・未対応PR/Issue・停滞・失敗Actions・Dependabot（トークン時）・前日差分を把握。 | ✅ live run OK (108 repos) · ⬜ first 07:00 JST run not yet observed |
| **Spot a broken CI quickly** | A failing default-branch Actions run turns the Kuma push monitor red. | デフォルトブランチのActions失敗でKumaのPush監視が赤になる。 | ✅ logic (fake-API tests) · ⬜ real failure not yet seen · ⬜ delivery needs a channel |
| **Let an AI tool read the report safely** | Reports are served read-only through MCP (`list_reports`, `read_report`) with a token and audit log. | レポートをMCP経由で読み取り専用に提供（トークン＋監査ログ）。 | ✅ from n8n |
| **Know when something breaks** | Kuma watches SSH, n8n, MCP and the collector; an external heartbeat can watch the whole NUC. | KumaがSSH・n8n・MCP・収集ジョブを監視。外部heartbeatでNUC全体も監視可能。 | ✅ detection · ⬜ notifications · ⬜ heartbeat not enabled |
| **Recover after a failure** | Daily encrypted backup and a tested restore. | 毎日の暗号化バックアップと試験済みの復元。 | ✅ local · ⬜ off-device copy missing |
| **Try OSS / tools safely** | Run experiments in containers and throw them away; your PC stays clean. | コンテナで試して捨てる。開発PCを汚さない。 | ✅ pattern in place |
| *(Parked)* Chat with cloud LLMs | Open WebUI is stopped; no LLM API key, no cost. | Open WebUI は停止中。LLMのAPIキーなし・費用なし。 | ⏸ data kept; restart: [ops-runbook.md](ops-runbook.md) |

## Try it (after tunnelling in) / 試してみる（SSHトンネル接続後）

1. **n8n** → workflow **"GitHub daily report (read-only)"** → *Execute*. You get `repos … | open issues … | open PRs … | critical …`. The report is written on the NUC.
   **n8n** の「GitHub daily report (read-only)」を *Execute*。件数のサマリーが出て、レポートが NUC に保存されます。
2. **n8n** → **"MCP read-only test"** → *Execute*. You see the tool list, the report list and the first lines of `github-daily-latest.md`.
   **n8n** の「MCP read-only test」を実行。ツール一覧・レポート一覧・最新レポートの冒頭が見えます。
3. **Uptime Kuma** → the dashboard shows all monitors (Open WebUI is paused on purpose).
   **Uptime Kuma** で全監視を確認（Open WebUI は意図的に一時停止）。
4. Look at a sample report: [samples/github-daily-sample.md](samples/github-daily-sample.md) (synthetic data). / サンプル（合成データ）：[samples/github-daily-sample.md](samples/github-daily-sample.md)

> **EN:** Without a GitHub token the whole home IP shares 60 calls/hour, so a manual run soon after another can be *partial*; the report says so and the fuller report of the same day is kept.
> **JA:** トークンなしでは家庭のIP全体で 60回/時を共有するため、続けて手動実行すると*部分的*になることがあります（レポートに明記。同日のより充実したレポートは残ります）。

## What does it cost? / 費用

| Item | Extra monthly cost |
|---|---|
| GitHub API (public, read-only; optional free token) | 0 |
| LLM APIs | 0 (none used; Open WebUI stopped) |
| Notification channel (e-mail/SMTP with your existing account) | 0 |
| External heartbeat (free tier of a hosted check) | 0 (free tier; confirm current terms) |
| Off-device backup | 0 with hardware/accounts you already have — **not set up yet** |
| Electricity | not included (an idle NUC; measured load < 1 % CPU, 1.5 GiB RAM) |

## How to judge the value / 価値の測り方

**EN:** After a month: did the morning report save you manual checking? How many alerts were real? How much upkeep did it need? Stop what you do not use.
**JA:** 1か月後に、朝のレポートで手作業の確認が減ったか、通知のうち本物はいくつか、保守にどれだけかかったかを評価。使わないものは止める。

## What it deliberately does not do / 意図的にやらないこと

- **EN:** run LLMs or GPU workloads; use paid APIs; write to GitHub or other external services (the collector only reads); expose anything to the Internet; run untrusted code (no self-hosted CI runner).
- **JA:** LLM／GPU処理、有料APIの利用、GitHub等への書き込み（収集は読み取りのみ）、インターネット公開、未信頼コードの実行（self-hosted CI Runnerなし）。
