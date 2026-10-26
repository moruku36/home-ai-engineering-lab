# REA usage and resources / REA の用途・参照リンク

[English overview](../README.md) · [日本語の概要](../README.ja.md) · [Documentation index / 索引](README.md)

**Source check: 2026-10-26 UTC / 情報確認日: 2026-10-26 UTC**  
Reference material only: upstream examples are not proof of capability in this lab.  
参照用の資料です。公式の事例紹介と、このラボで動作確認・受入れ済みの機能を区別します。

## Resource map / 参照先一覧

| Resource / 参照先 | Read it for / 何を見るか | Classification / 区分 |
|---|---|---|
| [GitHub: morluto/rea](https://github.com/morluto/rea) | Source, setup and technical documentation / ソース・導入・技術資料 | Official upstream / 公式 |
| [Website](https://rea.tools/) | Product overview and illustrated entry points / 全体像と図解付きの入口 | Official / 公式 |
| [Guides](https://rea.tools/guides/) | Concrete targets, prompts and analysis walkthroughs / 対象・質問例・解析の流れ | Official tutorials / 公式手順 |
| [Blog](https://rea.tools/blog/) | Reconstruction methods, model choice and verification lessons / 再構成の考え方・モデル選択・検証の知見 | Official-site essays, not local acceptance evidence / 公式サイトの記事。ラボの受入れ証跡ではない |
| [GitHub topic: rea](https://github.com/topics/rea) | Discover projects and community resources / 関連プロジェクト・コミュニティ資料を探す | Open topic listing, not an official certification / タグによる一覧。公式認定ではない |
| [Showcase](https://rea.tools/showcase/) | Published investigations and demonstrations / 公開された調査事例・デモ | Official-site case studies / 公式サイトの事例 |

REA connects a coding agent to analysis tools through MCP; CLI workflows are also available. Its upstream scope includes binaries, JavaScript/Electron applications and runtime behavior. Tool/provider requirements differ by target; being listed upstream does not establish availability in the installed lab version. [Source: upstream README](https://github.com/morluto/rea).

REA は MCP 経由でコーディングエージェントに解析ツールを提供し、CLI からも利用できます。対象ごとに必要な解析エンジンや依存関係が異なります。上流に記載された機能を、そのままラボの導入済みバージョンで使えるとは扱いません。

## What can it help investigate? / こういう使い方を調べられる

All rows below describe upstream documentation/examples, **not tests performed in this lab**.  
以下はすべて公式資料・事例の要約であり、**このラボで実施した試験ではありません**。

| Use / 用途 | Concrete example and evidence / 具体例と根拠 | Limit / 注意点 |
|---|---|---|
| Native calculation recovery / ネイティブ関数の計算復元 | [DX-Ball guide](https://rea.tools/guides/native/): combine instructions, caller references and constants to reconstruct a sound-pan calculation in C. / 命令・呼出し元・定数から左右音量の計算を読み解く。 | Decompiled pseudocode alone can omit arithmetic; compare against other evidence. / 逆コンパイル結果だけで断定しない。 |
| JavaScript / Electron feature tracing / 機能の経路追跡 | [Electron guide](https://rea.tools/guides/javascript/): follow a Notes CSV export from renderer through preload/IPC to the file writer. / CSV出力ボタンからファイル書込みまで追う。 | Code-derived paths are not runtime observations; computed channel names can remain unresolved. / 静的な経路推定と実行観測を分ける。 |
| Browser behavior / ブラウザの動作観測 | [Browser guide](https://rea.tools/guides/browser/): relate an Export click to its JSON request and the script creating a download. / クリック・通信・CSV生成コードを対応づける。 | A capture covers its observation window, not earlier requests. / 観測開始前の通信は含まない。 |
| Android APK feature understanding / APK内の機能理解 | [Aegis case study](https://rea.tools/showcase/aegis/): trace time-based code generation and compare a reconstruction with public test cases. / 公開APKの生成ロジックと公開テストデータによる再現を学ぶ。 | Static APK inspection is separate from running an Android app. Use public test data, not real account secrets. / 実アカウントの秘密は使わない。 |
| Packaged Electron behavior / パッケージ済みアプリの動作理解 | [Notion case study](https://rea.tools/showcase/notion/): follow text/HTML copying through wrappers and IPC to the clipboard. / コピー操作のAPIからシステムクリップボードまで追う。 | A case study of a particular package, not a guarantee for all versions. / 対象バージョンの事例。 |
| Agent training/evaluation environments / エージェントの学習・評価環境 | [RL environment guide](https://rea.tools/guides/rl-environments/): turn recorded web-app behavior into tools/local state for AgentEnv, then add tasks and reward checks. / 操作記録からツールとローカル状態を作り、課題・採点を加える。 | Only recorded, evidenced operations are supported. Startup, task success and original-app equivalence are separate checks. / 起動成功・課題達成・元アプリとの一致は別の検証。 |

The [showcase index](https://rea.tools/showcase/) also includes a CTF checker and a PC-98 game calculation; these are learning references, not a request to execute targets or develop exploits. The [blog](https://rea.tools/blog/) provides background reading on reconstruction and model specialization.

[Showcase一覧](https://rea.tools/showcase/)には CTF の判定ロジックや PC-98 ゲームの計算の事例もあります。学習用の参照先として扱い、実対象の実行や攻撃コード開発を指示するものではありません。[Blog](https://rea.tools/blog/)は再構成手法やモデルの専門化について読む入口です。

## Community discovery is not validation / コミュニティ一覧の読み方

The [rea topic](https://github.com/topics/rea) mixes the upstream project, prompt collections, curated lists and other tagged projects. A topic tag alone does not prove that a project was built with REA, is endorsed by its maintainers, is safe, or works here. Check each project's README, provenance, license and reproducible evidence before considering use.

[reaタグ一覧](https://github.com/topics/rea)は公式本体、プロンプト集、リンク集、その他のタグ付きプロジェクトが混在します。「REAで作られた」「公式推奨」「安全」「ラボで動作済み」の証明にはなりません。利用を検討する際は個別のREADME・出所・ライセンス・再現可能な証跡を確認します。

## Lab status stays separate / このラボの現在地とは分ける

The authoritative repository record is [Security analysis VM](security-analysis-vm.md), dated **2026-10-20 JST**; this page does not re-check the live machine.

- Recorded offline resources: **REA 6.7.0**, **Ghidra 12.1.4**, Java in a NIC-less QEMU/KVM guest.
- Scope A (VM foundation/basic operations): conditionally owner-accepted.
- Scope B (REA → Ghidra analysis capability): **not accepted**. Keep the original A4 `FAIL` and `REPORT=UNVERIFIED`, despite observed JSON output.
- Workbench and REA are independent MCP servers; their integration remains unimplemented.
- The examples above have **not been locally validated by this documentation update**. It performs no update/install, execution, network change or credential handling.

根拠は **2026-10-20 JST** の [専用セキュリティ解析VM記録](security-analysis-vm.md)です。今回、実機の状態を再確認したものではありません。

- 仮想NICなしの QEMU/KVM ゲストへ REA 6.7.0・Ghidra 12.1.4・Java をオフライン配置した記録があります。
- スコープA（VM基盤・基本操作）は条件付きオーナー受入れ、スコープB（REA → Ghidraの解析能力）は**未受入れ**です。元の A4 `FAIL` / `REPORT=UNVERIFIED` は保持します。
- Workbench ↔ REA の統合は未実施です。
- 上表の用途をラボで使えることは今回検証していません。バージョン更新も実施していません。

## How to use this reference / 参照の使い方

1. Choose one question and read the matching guide or case study; keep evidence separate from an agent's interpretation.
2. For future lab work, record the authorized target, fixed tool versions, dependencies, expected output and acceptance criteria before execution. Respect the VM's existing offline boundary.
3. Browser/RL examples may need a separate test app, browser, recording and additional runtime dependencies. They are not drop-in instructions for the offline VM. Captures/exported environments can retain tokens or personal data; do not publish or send them externally without review and authorization.

1. 「何を知りたいか」を一つ決め、対応する公式資料へ進みます。取得した証拠とエージェントの解釈を区別します。
2. 将来ラボで試す場合は、許可された対象・固定バージョン・依存関係・期待結果・受入れ基準を先に整理します。現在のオフライン境界は維持します。
3. ブラウザ観測・RL環境は別のテストアプリや追加依存関係が必要になり得ます。オフラインVMへそのまま適用する手順ではありません。通信記録や出力環境に秘密・個人情報が残り得るため、確認と許可なしに公開・外部送信しません。

This is a source-linked reading map, not an installation, upgrade or execution runbook.  
この文書は用途別の読書・参照マップであり、導入・更新・実行の手順書ではありません。
