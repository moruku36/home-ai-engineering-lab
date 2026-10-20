# Local GPU AI Security Log Analysis — Deployment Guide (Draft Proposal)
# ローカルGPU AI セキュリティログ解析 デプロイ手順案（未実施・提案段階）

**Status: Draft / Inactive Proposal / 未適用・提案段階**\
**Warning: 実機への適用、ポート開放、サービスの再起動・停止は本フェーズでは禁止されています。**

---

## 1. 前提条件と配備構成 (Prerequisites)

本ガイドは、将来 Phase 2（実機検証）へ進む承認が得られた場合に実施するデプロイ手順を定めたものです。現段階では実機への適用を行いません。

### 必要環境
1. **Windows 端末 (推論ホスト)**
   - Windows 11 Pro 26H2, RTX 3070 8GB
   - Ollama 0.40.5 導入済み、`huihui_ai/qwen3-abliterated:8b` モデル保持
   - `127.0.0.1:11434` (loopback限定) でリッスン中
2. **Intel NUC 端末 (収集・自動化ホスト)**
   - Ubuntu Server 24.04 LTS, Docker Compose 稼働中
   - 既存スタック: `stacks/n8n/compose.yaml` (稼働維持、変更しない)
   - 既存ボリューム: `jobs-reports` (日次レポート用、変更しない)
   - 独立新ボリューム: `security-reports`, `security-state`

---

## 2. ネットワーク接続と認証の安全化 (Secure Bridge Setup)

Ollama はデフォルトで認証機構を持たないため、**Ollamaのポート11434を家庭内LANへ直接リッスンさせる設定（`OLLAMA_HOST=0.0.0.0`）はセキュリティ上絶対に行ってはなりません**。

### 推奨構成: SSH リバーストンネル方式
NUC から Windows への暗号化トンネルを経由して通信します。

```
[NUC Docker Container] ──> [NUC Host (127.0.0.1:11434)]
                             │ (SSH Local Forward via 鍵認証)
                             ▼
                           [Windows Host (127.0.0.1:11434)] ──> [Ollama Daemon]
```

#### 設定手順（Phase 2 承認後の手順）
1. NUC ホスト上にトンネル用 systemd サービス（`ollama-tunnel.service`）を作成。
2. Windows ホストの OpenSSH Server への接続を定義（鍵認証限定）。
3. NUC ホストのループバック `127.0.0.1:11434` を Windows の `127.0.0.1:11434` にフォワード。
4. Docker Compose 内からはホストゲートウェイ（`host.docker.internal` または内部リバースプロキシ）経由でアクセス。

---

## 3. 環境変数とボリューム設定 (Configuration)

セキュリティ解析パイプライン用の独立設定を `.env` に定義します（`.env.example` 参照）。

| 変数名 | 推奨値 / 説明 |
|---|---|
| `LLM_ENDPOINT` | `http://host.docker.internal:11434` (トンネル経由ループバック) |
| `LLM_MODEL` | `huihui_ai/qwen3-abliterated:8b` |
| `LLM_TIMEOUT_SECONDS` | `120` (長時間の推論ハングを防止) |
| `LLM_MAX_CONCURRENCY` | `1` (GPUリソース保護のため単一推論固定) |
| `SECURITY_REPORT_DIR` | `/data/security-reports` (日次レポートボリュームとは物理分離) |
| `SECURITY_STATE_DIR` | `/data/security-state` |

---

## 4. ワークフロー適用手順 (Workflow Activation - Phase 2以降)

1. **オフライン検証の確認**:
   - `python -m unittest tests/security_log_pipeline_test.py` が PASS していることを確認。
2. **n8n ワークフローのインポート**:
   - [`stacks/n8n/workflows/security-log-analysis.proposed.json`](../stacks/n8n/workflows/security-log-analysis.proposed.json) を n8n UI（SSH トンネル `http://localhost:5678` 経由）にインポート。
   - インポート時は `active: false` のまま手動実行テストを行う。
3. **成果物の確認**:
   - レポートが `/data/security-reports/` に生成され、JSON Schema および証拠行が正常に検証されることを確認。

---

## 5. デプロイ判定ゲート (Deployment Gates)

以下の条件がすべて満たされるまで、実機デプロイは行いません：
- [ ] 運用責任者による本設計書およびオフラインテスト結果の承認。
- [ ] Windows ホスト側での GPU 推論時メモリ測定プロトコルの策定（VRAM枯渇防止の確認）。
- [ ] NUC 側での `/var/log` 読み取り権限（Read-Only）の最小特権バインドマウントの安全確認。
- [ ] 既存の GitHub 日次レポート（PR #20 適用済み）への干渉が皆無であることの再確認。
