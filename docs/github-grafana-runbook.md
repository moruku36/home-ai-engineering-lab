# GitHub snapshot → Prometheus / Grafana（ソース実装・実機未適用）

基準main: 68e617ac8671。ネットワーク監視の7パネルとは別の次段階です。
既存の日次snapshotから数値・取得時刻・固定コードの状態を抽出する変換CLIと、別UIDのGrafana JSONを用意しました。GitHub API追加取得・n8nワークフロー実行・資格情報読取りは行いません。

## 保存形式と出力する範囲

入力は n8n_jobs-state volume内の /data/state/snapshots/latest.json。schema 1、generated_at、partial、各取得フラグ・Coverage、集計用辞書、activityを参照します。最大8MiB、UTF-8のJSON object、配列・objectを合わせて最大32階層までを受け付けます。文字列内の括弧やエスケープを区別して、再帰的なJSON解析の前に深さを確認します。ルートが配列・スカラーの入力や深さ超過を、Pythonランタイムの再帰上限に依存せず拒否します。schema 1と必要フィールドの検証は変換時にも行います。名前・タイトル・URL・notes・本文は出力せず、metricラベルの値はコードの固定列挙だけです。非公開リポジトリが含まれる場合も件数だけを扱います。

日付別JSONは既定30件、Markdownは60件、別途latestあり。同日のsnapshotは置換されます。このGrafana案はアーカイブJSONを再生せず、Prometheusへ渡した時点からの観測履歴です。既存Prometheusの15日保持は変更しません。収集対象範囲や認証有無が変わった前後を同一条件として比較しません。

実機の最新snapshot・日次集計フィールド・Coverage・取得日時・定期実行・読取り権限は今回未確認です。過去の生成成功を現在の稼働証拠にしません。

## 集計と状態

lab_github_value はすべてgaugeで、固定ラベル metric を持ちます。

| 指標 | 意味・制限 |
|---|---|
| repos / open_issues / open_prs | snapshot時点の件数。Issue/PRの取得フラグがない旧形式を正常ゼロと推定しない |
| alerts_critical / alerts_warn | 保存された検出結果の件数。snapshot全体が部分取得ならこの件数も部分扱い |
| api_calls | snapshotを生成した収集のAPI回数。現在進行中のAPI使用量ではない |
| prs_opened / prs_merged / prs_closed_unmerged / issues_opened / issues_closed | 前日JSTの半開窓。取得時点の検索結果であり最終確定値ではない |
| latest_push_repositories | 最新push時刻が日次窓内の自所有・非forkリポジトリ数。常に下限。push回数でもコミット数でもない |

日次窓と取得時刻を検証し、同日再実行でもキーを重複排除して値を置換するだけです。rate / increase / sum_over_timeを使って日次件数を求めません。横軸は取得時点で、対象日へバックフィルしません。日次窓の終了時刻（JST）も表示します。

| lab_github_metric_state | 意味 | 数値系列 |
|---|---|---|
| 0 | 未取得／根拠不足 | 出さない |
| 1 | 取得済み | 正常な0件も0として出す |
| 2 | 部分取得／下限 | 取得済み範囲の値を出し、状態を併記 |
| 3 | 古いデータ（snapshotが26時間超） | 出さない |
| 4 | 記録された取得失敗、入力・検証失敗 | 出さない |

入力欠落・不正・読取り失敗時にも状態を出して以前の数値を残しません。保存失敗は非ゼロ終了し、以前のファイルを更新しません。Grafanaは変換時刻が120秒以上古いと表示を止めます。変換プロセス自体の成否監視は別途必要です。古いsnapshotに記録済みの取得失敗があれば、その指標の失敗状態を保持します。

**既存JSONの限界**：失敗した収集ジョブは新しいsnapshotを残さない場合があります。新鮮な以前のsnapshotがあっても、直近ジョブの成功は断定できません。lab_github_collector_attempt_known は0で、画面にも留保を表示します。JSONに記録された指標の失敗と、直近ジョブの未知の成否を分けます。実行履歴・生ペイロードを追加取得しません。

## 実機適用前の確認項目（未実施）

1. 利用可能な認可済み接続と読取り権限。Tailscale疎通をSSH認証の代用にしない。
2. 稼働checkout、実際のvolumeと保存先、sourceのサイズ/schema/取得日時/集計項目。識別子を表示・転載せず数値・状態だけで確認する。.envは読まない。
3. 既存node-exporterのtextfileディレクトリ・書込み権限、Prometheusのnode job、GrafanaのPrometheusデータソース。
4. 変換を毎60秒程度で呼ぶ既存の実行経路。変換はGitHub/n8nジョブを起動しない。新しいtimer/service、volume読取り経路、所有者変更が必要なら、具体的差分を別途承認対象にする。拒否済みSSHや権限操作は無根拠に再試行しない。

## 提案する実機差分（まだ実行しない）

- 既存snapshotを読めるoperatorのCLI → 既存textfile内の専用 github-daily.prom → 既存node-exporter → 既存Prometheus → 既存Grafana。
- source volumeをGrafana/Prometheusへ直接マウントしない。資格情報や保存payloadを公開しない。
- CLIは1回実行で常駐やスケジュールを作らない。読取りパスと定期呼出しは未確定であり、次の値を推測して実行しない。

    python3 scripts/github_snapshot_metrics.py \
      --input '<existing-readable-snapshot>/latest.json' \
      --output '<existing-textfile-directory>/github-daily.prom'

終了コード：0＝変換成功、2＝欠落／古いsnapshot、3＝入力不正・読取り／保存失敗。保存失敗メッセージは固定文で入力値・ファイル内容を出しません。出力の親ディレクトリをCLIが作成することもありません。

既存textfile mountを使えればnode-exporter／Prometheusの再作成は不要です。定期呼出しとsource読取り経路は未設定。追加service・mount・既存ワークフロー変更はこのソース改修に含めません。必要ならUID・path・停止影響を確認して具体的に報告します。

表示用JSONは stacks/observability/grafana/provisioning/dashboards/json/github-daily.json（UID home-github-daily）。既存のネットワーク監視JSONを置換しません。新JSON配備・GUI importとも未実施です。

受入れ時はsourceと出力の件数・対象窓・状態、正常ゼロ／未取得／部分／古い／失敗を照合します。変換の定期更新と保存後のGrafanaで数値・状態が一致して初めて実機適用済みとします。

復旧は追加した変換呼出しだけ停止し、専用 github-daily.prom と新dashboard UIDだけを対象確認して戻します。既存snapshot・レポート・他textfile・既存ネットワーク監視・volumeは保持します。

## ソース検証

Python標準ライブラリと合成snapshotだけで状態・入力上限・匿名化・同日再実行・atomic置換・dashboard固定ラベル／鮮度／gaugeクエリを検証します。ライブGrafanaやPrometheus評価エンジンの検証ではありません。

    python -m unittest discover -s tests -p github_snapshot_metrics_test.py -v
