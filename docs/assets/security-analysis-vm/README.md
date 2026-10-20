# Security analysis VM diagram / 構成図

`architecture.svg` は [Pele](https://pele.run/) 1.6.0 で生成した公開用構成図です。編集用ソースは `source.mmd`、生成スクリプトは `render.mjs` です。構成・受入れ範囲の説明は [VM文書](../../security-analysis-vm.md) を参照してください。

## 再生成

このディレクトリで `npm ci --ignore-scripts`、続けて `npm run render` を実行します。依存は公式npmパッケージ `pele` の 1.6.0 に固定しています。初回のパッケージ取得にはネットワークが必要ですが、レンダリングはローカルで実行します。VM上での実行手順ではありません。

- 生成時の Node.js: 24.19.0（描画環境の値。ゲスト内のNode.jsとは別）
- 公式実装: https://github.com/obsidianmd/pele
- API: https://pele.run/api
- テーマ既定値: https://pele.run/theming
- オプション: sans-serif / 16px / responsive=false / autoDirection=false
- 入力・出力・辺数などの上限はパッケージの既定値を維持

図の形状・配置・ラベルはPeleが生成しています。SVG単体を表示するビューアとの互換性のため、公開用SVGでは既定のライトテーマのCSS変数をリテラル値に置換しています。幾何形状の変更はありません。

生成時にSVGをラスター化して文字・矢印・状態境界を目視確認しました。寸法は976 × 1320です。目視確認には `@resvg/resvg-js` 2.6.2 を用いましたが、構成図の再生成には不要なため依存に含めていません。`node_modules/`、キャッシュ、生ログ、確認用画像はコミット対象外です。
