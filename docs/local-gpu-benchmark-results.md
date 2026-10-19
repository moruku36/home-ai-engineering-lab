# Local GPU AI Security Log Analysis — Benchmark Results & Measurement Protocol
# ローカルGPU AI ベンチマーク結果（未測定）および測定プロトコル案

**Status: UNMEASURED / 未測定（推論負荷試験は本フェーズでは厳格に禁止）**  
**Date:** 2026-10-19

---

## 1. 現状と確認済みハードウェア/ランタイム仕様 (Confirmed Environment)

本フェーズ（Phase 0/1）では実機での推論負荷試験やモデルの新規ダウンロードを一切実施していません。以下は既知の静的スナップショットおよび確認済み事実のみを記録したものです。

| 項目 | 確認値 / 事実 | 確認方法・根拠 |
|---|---|---|
| **OS / CPU** | Windows 11 Pro 26H2 (Build 26300.9711), AMD Ryzen 7 5800X 8-Core / 16-Thread | 事前検証済みタスク証拠 |
| **GPU / VRAM** | NVIDIA GeForce RTX 3070 (8,192 MiB VRAM) | `nvidia-smi` |
| **GPU ドライバ** | NVIDIA Game Ready Driver 617.42 | `nvidia-smi` |
| **Ollama バージョン** | Ollama 0.40.5 (`127.0.0.1:11434` リッスン) | `ollama --version` |
| **配備済みモデル** | `huihui_ai/qwen3-abliterated:8b` (ID: `543f9deff86d`) | `ollama list` |
| **量子化 / ディスクサイズ** | Q4_K_M (8.2B パラメータ), 5.0 GB | `ollama show` |
| **モデル最大コンテキスト** | 40,960 トークン | `ollama show` |
| **プロセス常駐スナップショット** | メモリ常駐 6.1 GB, **CPU 100%**, ランタイムコンテキスト 10,240 | `ollama ps` |

---

## 2. 未測定・不明事項 (Unmeasured & Unknown Metrics)

以下の指標は**一切測定されておらず、推測による推定値も記載しません**。

- ❓ **実推論時の GPU VRAM オフロード率**: `ollama ps` のスナップショットで「CPU 100%」と表示された原因（VRAM不足によるCPUフォールバックか、単なるロード初期スレッド仕様か、UI表示特性か）は未特定。
- ❓ **初回推論レイテンシ (TTFT: Time To First Token)**: 1,000〜8,000 文字のログ投入時の初速。
- ❓ **生成スループット (tokens/sec)**: 構造化 JSON 出力時の実効処理速度。
- ❓ **GPU 温度・消費電力**: 推論中の GPU Hotspot 温度およびファンノイズ。
- ❓ **同時並行時の耐性**: 複数リクエスト投入時の挙動（設計上は Concurrency=1 で保護予定）。

> [!IMPORTANT]
> **ファイルサイズやモデルパラメータ数から推論性能や消費リソースを推測・断定することは禁止されています。**  
> 「8GB VRAM で完全に高速動作する」「メモリ削減効果がある」等の主張は行いません。

---

## 3. 将来のベンチマーク測定プロトコル案 (Future Protocol Proposal)

Phase 2 以降で負荷試験の承認が得られた場合に実施する標準化プロトコルです。

### 測定手順案
1. **ベースライン測定 (アイドル時)**:
   - `nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw --format=csv -l 1 > idle_gpu.csv` を 60 秒間記録。
2. **合成ログ投入による単一推論測定**:
   - 100行（約4,000文字）の合成セキュリティログ（SSH攻撃ログ・正常ログ・インジェクション混入ログ）を用意。
   - `curl -X POST http://127.0.0.1:11434/api/generate` にて計測用リクエストを1回投入。
   - 測定項目: TTFT、総所要時間、生成トークン数、ピーク VRAM 使用量、GPU 利用率ピーク。
3. **連続バッチ測定 (5回連続・Concurrency=1)**:
   - 連続実行時の温度上昇およびスロットリングの有無を検証。
4. **通常版 Qwen との比較 (提案のみ・未ダウンロード)**:
   - `qwen2.5:7b` または `qwen3:8b` 通常版との間で、同一合成ログセットに対する出力安定性および拒否率（Refusal）を比較。

### 測定実行に必要なゲート条件
- [ ] 運用者の明示的な負荷試験許可。
- [ ] Windows ホスト側での他重負荷プロセスの停止確認。
- [ ] GPU 温度異常時の自動中断スクリプトの準備。
