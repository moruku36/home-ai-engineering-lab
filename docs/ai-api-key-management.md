# 外部AI APIの鍵管理と接続方式（Open WebUI）

最終更新: 2026-10-15 JST。**状態: 構成は導入・検証済み。APIキーは未登録（鍵なし起動）。キーを使った実接続・課金を伴う実行は未実施。**

## 接続方式
Open WebUI は外部LLMを **OpenAI互換エンドポイント**として接続する（`stacks/open-webui`）。NUC側に推論はない。

| プロバイダー | Base URL | 備考 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | 標準 |
| Anthropic | `https://api.anthropic.com/v1` | OpenAI互換レイヤー。機能差があり得る（未検証）。ネイティブ連携が必要ならOpenWebUIのPipe関数/ゲートウェイを後日検討 |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | OpenAI互換 |
| RunPod | `https://api.runpod.ai/v2/<endpoint-id>/openai/v1` | **Serverless vLLM等のOpenAI互換エンドポイント**。エンドポイントIDは `owui-admin.sh set-key runpod` で入力。**エンドポイント/Podの起動は課金が発生するため、このリポジトリの作業では起動していない** |

**検証済み（鍵なし）**: コンテナから各ホストへHTTPSで到達できる（OpenAI/Anthropic: 401、Gemini/RunPod: 404 ＝ 到達可・認証必要）。**未検証**: 鍵を使ったモデル一覧取得・チャット・Anthropic互換レイヤーの挙動。

## 鍵管理方式
原則: **鍵はGit・チャット・ログ・画面に出さない。NUC上の `chmod 600` ファイルにのみ保存。**

1. 入力: NUC上で `./owui-admin.sh set-key <provider>` を実行し、**非表示プロンプト**に貼り付ける（SSH端末に直接入力。チャットには貼らない）。長さ・空白/`;`/`$`/引用符を検証し、不正値は拒否。
2. 保存: `~/home-ai-lab/open-webui/secrets/<provider>.key`（ディレクトリ700、ファイル600）。
3. 反映: スクリプトが有効なプロバイダーだけを `OPENAI_API_BASE_URLS` / `OPENAI_API_KEYS`（`;`区切り）として `.env`（600）へ**生成**し、コンテナを再作成。`ENABLE_PERSISTENT_CONFIG=false` のため **`.env` が設定の唯一の正**（UIで鍵が別途DBに残らない）。
4. ローテーション: `set-key` を再実行（上書き）→ プロバイダー側で旧キーを失効。
5. 撤去: `./owui-admin.sh remove-key <provider>`（`shred`で削除し、プロバイダー無効化）。**プロバイダーのコンソールでも失効すること。**
6. 確認: `./owui-admin.sh status`（設定済みかどうかと権限のみ表示。値は出さない）。
7. バックアップ: `.env`・`secrets/` は `config.tar` に含まれ**暗号化バックアップ**に入る（平文では外へ出ない）。
8. 露出面: 鍵はコンテナ環境変数として存在し、`docker inspect` でroot権限者に見える（単一管理者の自宅サーバーとして許容）。UIからは参照できない。

## 費用・利用の上限（人間の承認）
アプリ内の上限機構は未実装。**プロバイダー側のハード上限が実質の費用統制**:
- OpenAI / Anthropic / Gemini: プロジェクト単位の**月額上限（ハードリミット）**と、用途専用のAPIキー（最小権限・専用プロジェクト）を作成してから登録する。
- RunPod: 自動停止（Idle Timeout）・最大ワーカー数・日次予算アラートを設定。常時起動しない。
- 将来、アプリ内で予算/レート制御が必要になった場合はLLMゲートウェイ（例: LiteLLM）の導入を検討（未実施、別途承認）。
- 外部へ送るデータ: 会話内容がプロバイダーへ送信される。機密情報・個人情報を入力しない運用とし、Open WebUIの会話履歴の保持はユーザーが管理する。

## アクセス制御
- UI: `127.0.0.1:8300` のみ。SSHトンネル `ssh -N -L 8300:127.0.0.1:8300 <user>@<host>` → `http://localhost:8300`。
- **初回のみ** `ENABLE_SIGNUP=true`。最初に登録したアカウントが管理者になる。作成後すぐ `./owui-admin.sh lock-signup`。以降の新規アカウントは `DEFAULT_USER_ROLE=pending`（管理者承認制）。
- テレメトリ/外部共有/バージョン確認/Ollamaを無効化。

## 手順（ユーザー実施）
```bash
# 1. トンネル → http://localhost:8300 で管理者アカウントを作成（パスワードはチャットに共有しない）
# 2. サインアップを閉じる
cd ~/home-ai-lab/open-webui && ./owui-admin.sh lock-signup
# 3. （キーを用意できたら）プロバイダーごとに
./owui-admin.sh set-key openai
./owui-admin.sh status
```

## ロールバック
`cd ~/home-ai-lab/open-webui && sudo docker compose down`（ボリューム保持）。鍵の撤去は `remove-key`。ボリューム削除は別途承認。
