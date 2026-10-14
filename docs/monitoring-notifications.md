# Monitoring and notifications / 監視と通知

English first, Japanese below each section. Status as of 2026-10-15. / 各節は英語が先、日本語が後。

**Bottom line / 結論:** **No notification channel is configured yet, so no alert can reach you today.** Detection works (Kuma shows red), delivery needs one credential that only you can provide. / **通知チャネルは未設定のため、現時点で通知はあなたに届きません。** 検知は動作（Kuma が赤になる）。配送には、あなた自身が用意する認証情報が1つ必要です。

## 1. Policy / 方針

| Event | Detected by | Notify? | Duplicate control |
|---|---|---|---|
| NUC SSH port unreachable | Kuma TCP monitor (retries 2) | yes | one notification per state change |
| n8n / MCP down | Kuma HTTP monitors (retries 2) | yes | same |
| Kuma itself or the whole NUC down | **external heartbeat** (section 4) | yes | the external service alerts once |
| GitHub Actions failing on a default branch | collector → Kuma push `down` | yes | one per state change; details in the daily report |
| Critical Dependabot alert (token needed) | collector → Kuma push `down` | yes | same |
| Collector fails / does not run for 26 h | Kuma push monitor (no heartbeat → `down`) | yes | same |
| New issues/PRs, pushes, stale items, partial data | daily report | **no** | collected in the 07:00 JST report |
| Open WebUI (stopped on purpose) | monitor **paused** | no | resume together with the service |

**JA:** 通常の更新は日次レポートへ集約し、対応が必要なものだけ通知します。Kuma は状態変化ごとに1回だけ通知します（瞬断対策としてリトライ2回）。停止中の Open WebUI の監視は一時停止してあります（再開時にあわせて再開）。

## 2. Uptime Kuma monitors now / 現在の監視

| ID | Monitor | Type | State |
|---|---|---|---|
| 1 | Uptime Kuma (self) | HTTP | active |
| 2 | NUC SSH (host) | TCP :22 via host gateway | active, retries 2 |
| 3 | n8n (healthz) | HTTP | active, retries 2 |
| 4 | Open WebUI (health) | HTTP | **paused** (service stopped on purpose) |
| 5 | MCP server (healthz) | HTTP | active, retries 2 |
| 6 | GitHub collector + alerts (push) | Push, 26 h | created; **waiting for the push token** ([github-monitoring.md](github-monitoring.md) §6) |

## 3. Notification channel (you choose, zero cost) / 通知チャネル（あなたが選択・無料）

Add one in Kuma: *Settings → Notifications → Setup Notification*, then enable "Default enabled / apply to all monitors". The credentials are stored **inside Kuma's database on the NUC** (included only in the encrypted backups) — never in Git and never typed to the assistant.

| Option | Cost | You must provide | Notes |
|---|---|---|---|
| **E-mail (SMTP)** — recommended | 0 | An SMTP login: e.g. a Gmail/Google *app password* for your own account, or your provider's SMTP | Works with what you already have. Use an app password, not your main password. |
| Telegram bot | 0 | Bot token + chat ID | Instant push to phone; token is a credential. |
| Discord / Slack webhook | 0 | Webhook URL | URL is a credential; messages leave your network. |
| Others (ntfy, Pushover, …) | varies | – | Not evaluated here. A public ntfy topic has no authentication — avoid for anything sensitive. |

**JA:** Kuma の「設定 → 通知 → 通知の設定」で1つ追加し、全監視に適用します。認証情報は **NUC 上の Kuma のデータベース内**（暗号化バックアップにのみ含まれる）に保存され、Git にもチャットにも入れません。おすすめは **メール(SMTP)**：自分のアカウントの*アプリパスワード*を使い、メインのパスワードは使わない。

## 4. External monitoring of the NUC itself (free) / NUC自体の外部監視（無料）

**EN:** If the NUC, the router or the power dies, Kuma dies with it and cannot warn you. The cure is a *dead-man's switch*: the NUC sends a small outbound HTTPS ping every 5 minutes to a free external service; if the pings stop, the service alerts you. **No inbound port is opened.**

| Option | Cost | Notes |
|---|---|---|
| **Healthchecks.io** (hosted) — suggested | free "Hobbyist" plan: 20 checks, 100 log entries per check (checked on their site, 2026-10-15; confirm current terms before relying on it) | Gives each check a ping URL; alerts by e-mail (and other channels). |
| UptimeRobot / Better Stack heartbeat | free tiers exist | **Not verified in this work.** |
| A second always-on machine running Kuma | 0 | needs hardware you may not have |

Set it up (you create the free check; the script never stores the URL in Git):

1. Create a check at the provider: *period 5 minutes, grace 15 minutes*, alert channel = your e-mail.
2. On the NUC: `bash ~/heartbeat/heartbeat-admin.sh enable` → paste the ping URL at the hidden prompt.
3. `bash ~/heartbeat/heartbeat-admin.sh status` to see the timer; `disable` removes everything.

The heartbeat reports `/fail` immediately if Docker, SSH or the Kuma container is unhealthy, so **Kuma itself is watched from the outside** too.

**JA:** NUC・ルーター・電源が落ちると Kuma も落ち、警告できません。対策は *dead-man's switch*：NUC が5分ごとに外部の無料サービスへ小さな HTTPS ping を**送信**し、止まったらサービスが通知します（**受信ポートは不要**）。候補は Healthchecks.io（無料枠 20 チェック・履歴 100 件/チェック。公式サイトで確認、利用前に最新条件を要確認）。UptimeRobot 等は**未検証**。手順は上記のとおり（チェックの作成はあなたが行い、スクリプトは URL を Git に保存しません）。Docker・SSH・Kuma が不健全なら即 `/fail` を送るので、**Kuma 自身も外部から監視**されます。

**Status / 状態:** scripts written and logic-tested with stubs (healthy / unhealthy / not configured). **Not enabled** — needs your ping URL. / スクリプトは作成済み・スタブで動作確認済み。**未有効化**（ping URL が必要）。

## 5. Known limitations / 既知の制限

- **EN:** While a Kuma monitor is already `down`, a second distinct incident on the same monitor does not notify again (state-change based). Retries delay detection by about 2–3 minutes. The "resend every N checks" option can be enabled per monitor if you want reminders.
- **JA:** すでに `down` の監視で別の障害が起きても、同じ監視では再通知されません（状態変化ベース）。リトライにより検知が2〜3分遅れます。リマインドが必要なら、監視ごとに「N回ごとに再送」を有効にできます。
