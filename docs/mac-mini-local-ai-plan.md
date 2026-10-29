# Mac mini local AI experiment plan / Mac mini ローカルAI実験計画

Status: **future plan before purchase. Nothing is bought, installed, downloaded or connected** (recorded 2026-10-30).
状態: **購入前の将来計画。購入・導入・ダウンロード・接続は一切していません**（2026-10-30 記録）。

This is not a measurement. No model has run on this hardware, so no speed, memory or accuracy figure below is a result.
これは実測ではありません。この機器でモデルを動かしたことはなく、以下に速度・メモリ・精度の結果値はありません。

## 1. Purpose and non-goals / 目的と対象外

- **EN:** Purposes: reduce contention for the Windows machine's resources, analyse logs locally, support OSS experiments, try RAG, and compare models reproducibly. The Mac mini would be an extra inference machine; it does not replace the existing Ubuntu/KVM host or Windows, and it is **not an isolation boundary** (isolated OSS verification stays where it is today).
- **JA:** 目的は、Windows の資源競合の軽減、ローカルでのログ分析、OSS 実験の補助、RAG、再現可能なモデル比較。Mac mini は推論用の追加機であり、既存の Ubuntu/KVM や Windows を置き換えず、**隔離境界でもありません**（OSS の隔離検証は現状のまま既存側で行う）。
- **EN:** Local execution does not guarantee accuracy or safety. Claims about either must come from the measurements in section 5.
- **JA:** ローカル実行は正確性や安全性を保証しません。どちらも第5節の測定で確かめるまで主張しません。

## 2. Planned hardware (confirmed from the vendor page) / 想定機器（公式ページで確認）

Source / 出典: Apple, [Mac mini (2024) – technical specifications (ja-JP)](https://support.apple.com/ja-jp/121555), read 2026-10-30.

| Item / 項目 | Value / 値 |
|---|---|
| Chip / チップ | Apple M4: 10-core CPU (4 performance + 6 efficiency), 10-core GPU, 16-core Neural Engine |
| Memory bandwidth / メモリ帯域 | 120 GB/s |
| Unified memory / ユニファイドメモリ | 16 GB (planned configuration; 24 GB and 32 GB are options) |
| Storage / ストレージ | 256 GB SSD (planned configuration) |

- **EN:** The 16 GB is shared by macOS, the runtime, the model weights, the KV cache and other buffers. The SSD is storage; swapping to it must not be counted as inference memory. Swap use is measured and treated as a warning, not as capacity.
- **JA:** 16 GB は macOS、実行環境、モデルの重み、KV キャッシュ、各種バッファが共有します。SSD は保存先であり、swap を推論メモリの代わりとして数えません。swap の発生は測定し、容量ではなく警告として扱います。

## 3. Model size policy / モデルサイズの方針

File sizes below are read from the publisher's repositories on 2026-10-30. They are download sizes only, not memory use.
以下のファイルサイズは 2026-10-30 に配布元で確認した値です。ダウンロードサイズであり、メモリ使用量ではありません。

| Model file / モデル | Size / サイズ | Source / 出典 |
|---|---|---|
| Qwen3-8B Q4_K_M (GGUF) | 5,027,783,488 bytes (about 5.03 GB) | [Qwen/Qwen3-8B-GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF/tree/main) |
| Qwen3-14B Q4_K_M (GGUF) | 9,001,752,960 bytes (about 9.0 GB) | [Qwen/Qwen3-14B-GGUF](https://huggingface.co/Qwen/Qwen3-14B-GGUF/tree/main) |

| Class / 区分 | Plan / 方針 |
|---|---|
| 7–8B, Q4 | **Initial baseline**: one request at a time, 4K context / **初期基準**: 単一要求、4K 文脈 |
| 14B, Q4 | Short-context experiment near the upper limit; may not fit comfortably / 短文脈の上限寄りの実験。余裕があるとは限らない |
| 30–32B, Q4 | Not a practical target on 16 GB / 16 GB では実用対象外 |

- **EN:** These are starting points, not a guaranteed maximum model size or speed. Whether a model fits depends on the runtime, context length, KV cache and what else is running, and is decided only by measurement.
- **JA:** これらは出発点であり、最大モデルサイズや速度の保証ではありません。収まるかどうかは実行環境、文脈長、KV キャッシュ、同時に動く処理で変わり、測定でのみ判断します。
- **EN:** An OpenAI-compatible API describes the request format only. It does not mean a closed model can run locally. Open-weight models need a separate suitability evaluation (licence, quality on the lab's tasks).
- **JA:** OpenAI 互換 API は形式の話で、非公開モデルをローカルで動かせるという意味ではありません。open-weight モデルは、ライセンスとラボの用途での品質を、別途評価します。

## 4. Runtime candidates and acquisition plan / 実行環境の候補と取得計画

Candidates / 候補: [ml-explore/mlx-lm](https://github.com/ml-explore/mlx-lm) (MIT) and [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT); both public and active when checked on 2026-10-30. Neither is adopted.
両方とも 2026-10-30 の確認時点で公開・更新されています。いずれも採用はしていません。

- **EN:** Start with **one runtime**, **one primary model** and **one comparison model**. Fetch only the needed quantised file for each. Nothing is fetched now; any download or install happens later, after purchase and a separate approval, following the lab's OSS adoption rules (pinned versions, staged review).
- **JA:** 最初は**実行環境1つ**、**主力モデル1つ**、**比較モデル1つ**。取得は必要な量子化ファイルだけにします。現時点では何も取得しません。ダウンロードや導入は購入後に別途承認を得て、ラボの OSS 採用ルール（バージョン固定、段階的レビュー）に沿って行います。

## 5. Planned measurements / 測定計画

Time to first response, tokens/s, peak memory, swap use, false positives and misses on log analysis, and accuracy of the cited evidence. Measurement conditions (model file, runtime version, context length, input set) are recorded with every result so runs can be reproduced.
初回応答までの時間、tokens/s、ピークメモリ、swap 使用、ログ分析での誤検知と見逃し、根拠の精度を測ります。結果には、モデルファイル、実行環境のバージョン、文脈長、入力セットを併記し、再現できるようにします。

## 6. Planned data flow / 想定するデータの流れ

1. Isolated OSS verification (existing side) / 隔離した OSS 検証（既存側）
2. Ubuntu collects, normalises and strips secrets / Ubuntu で収集・正規化・秘密除去
3. Mac mini runs inference / Mac mini で推論
4. Structured result with evidence IDs / 構造化結果と根拠 ID
5. Ubuntu validates and stores / Ubuntu で検証・保存
6. Grafana displays / Grafana で表示

## 7. Safety rules / 安全上のルール

- **EN:** Commands or instructions found inside logs, and commands the model suggests, are never executed automatically. Raw logs never fall back to a cloud service automatically. Secrets, personal data and operational paths are not published.
- **JA:** ログ内の命令やモデルが提案したコマンドは自動実行しません。生ログをクラウドへ自動で fallback しません。秘密・個人情報・運用パスは公開しません。
- **EN:** Exposing a new API or adding authentication needs separate approval. Purchase, installation and network changes are outside this document.
- **JA:** 新しい API の公開や認証の追加は別途承認が必要です。購入・導入・ネットワーク変更はこの文書の対象外です。

Related / 関連: [local-gpu-security-analysis-design.md](local-gpu-security-analysis-design.md), [local-gpu-benchmark-results.md](local-gpu-benchmark-results.md), [architecture.md](architecture.md) (historical; this plan is not drawn there / 過去の構成図。この計画は反映していません).
