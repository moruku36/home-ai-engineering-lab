# Diagrams / 構成図

The SVG files in this directory are drawn with [Pele](https://pele.run/) 1.6.0 from the Mermaid sources in `src/`. Edit a `.mmd` file, then regenerate; do not edit the SVG by hand.
このディレクトリのSVGは、`src/` のMermaidソースから [Pele](https://pele.run/) 1.6.0 で生成しています。`.mmd` を編集して再生成してください（SVGは手で編集しません）。

## Regenerate / 再生成

```bash
cd docs/assets/diagrams
npm ci --ignore-scripts      # pele 1.6.0 (pinned); needs the network once
npm run render               # all diagrams;  node render.mjs status-map  → only files starting with that name
```

Rendering runs locally. `node_modules/` is not committed. / レンダリングはローカルで実行します。`node_modules/` はコミットしません。

## Diagrams / 図の一覧

| SVG | Used in | Language |
|---|---|---|
| `status-map.en.svg` / `status-map.ja.svg` | README (EN / JA) | EN / JA |
| `system-overview.svg` / `system-overview.ja.svg` | README (EN / JA), [architecture](../../architecture.md) | EN / JA |
| `networks.svg`, `report-sequence.svg`, `mcp-sequence.svg`, `backup-flow.svg` | [architecture](../../architecture.md) | EN |
| `github-report-flow.svg` | [github-monitoring](../../github-monitoring.md) | EN |
| `network-visibility.svg` | [network-visibility](../../network-visibility.md) | EN |
| `physical-setup.svg` | [physical-setup-guide](../../physical-setup-guide.md) | JA |
| `local-gpu-pipeline.svg`, `local-gpu-triage.svg` | [local GPU design](../../local-gpu-security-analysis-design.md), [ops runbook](../../local-gpu-ops-runbook.md) | JA |

The security-analysis VM diagram has its own folder: [../security-analysis-vm/](../security-analysis-vm/README.md). / 解析VMの構成図は別フォルダです。

## Color code / 色の意味

| Color | EN | JA |
|---|---|---|
| Green | Verified on the NUC | 実機で確認済み |
| Amber | Partly verified, or needs approval | 一部のみ確認／承認が必要 |
| Red | Not done / not configured | 未着手・未設定 |
| Grey | Design only, stopped or parked | 設計のみ・停止中 |
| Blue | External system or person | 外部のシステム・人 |

Notes / 注意:
- Pele options: sans-serif, 16 px, `responsive=false`. CSS variables are replaced by the light-theme literals and a white background is added so the SVG looks the same in any viewer (including dark mode). / CSS変数はライトテーマの値に置換し、白背景を付けています。
- Avoid `1. ` at the start of a label (Pele reads it as a list); use `①` or `1)`. Quote or avoid parentheses in `[...]` labels. / ラベル先頭の `1. ` は箇条書きと解釈されます。`[...]` 内の括弧に注意。
