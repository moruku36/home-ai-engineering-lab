# Mac mini local AI experiment plan

**English** | [日本語](mac-mini-local-ai-plan.ja.md)

Status: **future plan before purchase. Nothing is bought, installed, downloaded or connected** (recorded 2026-10-30).

This is not a measurement. No model has run on this hardware, so no speed, memory or accuracy figure below is a result.

## 1. Purpose and non-goals

- Purposes: reduce contention for the Windows machine's resources, analyse logs locally, support OSS experiments, try RAG, and compare models reproducibly. The Mac mini would be an extra inference machine; it does not replace the existing Ubuntu/KVM host or Windows, and it is **not an isolation boundary** (isolated OSS verification stays where it is today).
- Local execution does not guarantee accuracy or safety. Claims about either must come from the measurements in section 5.

## 2. Planned hardware (confirmed from the vendor page)

Source: Apple, [Mac mini (2024) – technical specifications (ja-JP)](https://support.apple.com/ja-jp/121555), read 2026-10-30.

| Item | Value |
|---|---|
| Chip | Apple M4: 10-core CPU (4 performance + 6 efficiency), 10-core GPU, 16-core Neural Engine |
| Memory bandwidth | 120 GB/s |
| Unified memory | 16 GB (planned configuration; 24 GB and 32 GB are options) |
| Storage | 256 GB SSD (planned configuration) |

- The 16 GB is shared by macOS, the runtime, the model weights, the KV cache and other buffers. The SSD is storage; swapping to it must not be counted as inference memory. Swap use is measured and treated as a warning, not as capacity.

## 3. Model size policy

File sizes below are read from the publisher's repositories on 2026-10-30. They are download sizes only, not memory use.

| Model file | Size | Source |
|---|---|---|
| Qwen3-8B Q4_K_M (GGUF) | 5,027,783,488 bytes (about 5.03 GB) | [Qwen/Qwen3-8B-GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF/tree/main) |
| Qwen3-14B Q4_K_M (GGUF) | 9,001,752,960 bytes (about 9.0 GB) | [Qwen/Qwen3-14B-GGUF](https://huggingface.co/Qwen/Qwen3-14B-GGUF/tree/main) |

| Class | Plan |
|---|---|
| 7–8B, Q4 | **Initial baseline**: one request at a time, 4K context |
| 14B, Q4 | Short-context experiment near the upper limit; may not fit comfortably |
| 30–32B, Q4 | Not a practical target on 16 GB |

- These are starting points, not a guaranteed maximum model size or speed. Whether a model fits depends on the runtime, context length, KV cache and what else is running, and is decided only by measurement.
- An OpenAI-compatible API describes the request format only. It does not mean a closed model can run locally. Open-weight models need a separate suitability evaluation (licence, quality on the lab's tasks).

## 4. Runtime candidates and acquisition plan

Candidates: [ml-explore/mlx-lm](https://github.com/ml-explore/mlx-lm) (MIT) and [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT); both public and active when checked on 2026-10-30. Neither is adopted.

- Start with **one runtime**, **one primary model** and **one comparison model**. Fetch only the needed quantised file for each. Nothing is fetched now; any download or install happens later, after purchase and a separate approval, following the lab's OSS adoption rules (pinned versions, staged review).

## 5. Planned measurements

Time to first response, tokens/s, peak memory, swap use, false positives and misses on log analysis, and accuracy of the cited evidence. Measurement conditions (model file, runtime version, context length, input set) are recorded with every result so runs can be reproduced.

## 6. Planned data flow

1. Isolated OSS verification (existing side)
2. Ubuntu collects, normalises and strips secrets
3. Mac mini runs inference
4. Structured result with evidence IDs
5. Ubuntu validates and stores
6. Grafana displays

## 7. Safety rules

- Commands or instructions found inside logs, and commands the model suggests, are never executed automatically. Raw logs never fall back to a cloud service automatically. Secrets, personal data and operational paths are not published.
- Exposing a new API or adding authentication needs separate approval. Purchase, installation and network changes are outside this document.

Related: [local-gpu-security-analysis-design.md](local-gpu-security-analysis-design.md), [local-gpu-benchmark-results.md](local-gpu-benchmark-results.md), [architecture.md](architecture.md) (historical; this plan is not drawn there).
