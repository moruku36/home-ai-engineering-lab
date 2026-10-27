# OpenClaw trial idea / OpenClaw ラボ実験アイデア

Status: **idea only, not scheduled, nothing installed** (recorded 2026-10-27).
状態: **アイデア段階。時期未定、未導入**（2026-10-27 記録）。

## What it is / これは何か

- **EN:** OpenClaw (https://openclaw.ai/) is an open-source, self-hosted personal AI agent. It runs on your own machine, is driven from chat apps (WhatsApp, Telegram, Discord, iMessage), keeps persistent memory and a persona, runs scheduled "heartbeat" and cron-style work, and acts through skills/plugins on the host: shell, browser, mail, calendar and more. The model is bring-your-own (hosted APIs, subscriptions, or local models).
- **JA:** OpenClaw は自前ホスティング型のオープンソース・パーソナルエージェント基盤。自分のマシンに常駐し、チャットアプリ（WhatsApp / Telegram / Discord / iMessage）から操作する。記憶とペルソナを持ち、ハートビートや cron 的な定期動作をし、スキル／プラグイン経由でホスト上のシェル・ブラウザ・メール・カレンダー等を操作する。モデルは外付け（API、サブスクリプション、ローカルモデル）。

## Why not adopt it for daily operations / 日常運用に入れない理由

- **EN:** The personal-agent seat is already filled. Daily assistance, memory, briefings and watchers run on Muse (Fuwatchi); Windows-side execution runs through Dots via the Agent Lounge; coding execution is Claude Code, Codex and Antigravity (Gemini Flash 3.8 / Gemini 4 Argon). OpenClaw would duplicate most of that, add a third place where context and memory live, and add self-host maintenance and model-usage cost.
- **JA:** 常駐アシスタントの席は埋まっている。日常の支援・記憶・ブリーフィング・見張りは Muse（フワッチ）、Windows 側の実行はラウンジ経由でドッチー、コーディングの実行部隊は Claude Code / Codex / Antigravity（Gemini Flash 3.8 / Gemini 4 Argon）。OpenClaw を入れると役割の大半が重複し、文脈と記憶の置き場が3つ目に増え、自前運用の手間とモデル利用枠の消費も増える。

## Trial concept for the lab / ラボで実験するなら

- **EN:** Run it isolated on the lab side only, as a containment exercise as much as a product trial:
  - No Gmail, calendar or other personal credentials. Start with no accounts connected at all.
  - Model: the local Qwen3-30B-A3B (llama.cpp) first, so nothing leaves the house and no hosted quota is consumed.
  - One chat channel only, treated as an untrusted input source.
  - Evaluate it through the lethal-trifecta lens: private-data access × untrusted-content exposure × external communication. Note which of the three it holds by default, what its permission controls actually separate, and how message-borne prompt injection behaves.
  - Record install footprint, update behaviour, resource use, and how skills are added and reviewed (staged review, pinned versions, per the lab's OSS adoption rules).
- **JA:** ラボ側に隔離して入れ、製品評価であると同時に「封じ込めの演習」として扱う。
  - Gmail・カレンダー等の個人の資格情報は渡さない。最初はアカウント接続なしで始める。
  - モデルはまずローカルの Qwen3-30B-A3B（llama.cpp）とし、家の外に出さず、ホスト型の利用枠も消費しない。
  - チャットチャネルは1つだけに絞り、信頼できない入力源として扱う。
  - 評価軸は三要素（lethal trifecta）: 私的データへのアクセス × 信頼できないコンテンツへの接触 × 外部への通信。デフォルトでどれを保持するか、権限分離が実際にどこまで効くか、メッセージ経由のプロンプトインジェクションがどう振る舞うかを見る。
  - 導入の重さ、更新の挙動、リソース消費、スキルの追加と審査の流れ（段階的レビューとバージョン固定というラボの OSS 採用ルールに沿うか）を記録する。

## Exit criteria / 終了条件

- **EN:** The trial ends with a short report in this repo: what it did well, what the containment cost was, and whether any role remains that the current setup does not already cover. Absent such a role, it is removed again.
- **JA:** 終了時に短い報告をこのリポジトリに残す（良かった点、封じ込めのコスト、現構成で埋まっていない役割が残ったか）。役割が残らなければ削除する。
