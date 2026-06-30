# 製造工程フロー / WIP 可視化

**ライブ版**: https://tsuhasqni-pixel.github.io/cost-process-flow/

[internal-accounting](https://github.com/tsuhasqni-pixel/internal-accounting) で登録した製品マスタの**労務工程（labors）**を読んで、製造プロセスを**ボックス図（SVG）**で自動描画するツール。各工程ノードに**労務差異（賃率・時間）と OH 差異**をオーバーレイし、**差異の出所**を直感的に把握できる。仕掛品（WIP）残高はこのツール内で別途入力すると、ボックス間に「WIP: N 単位」として表示される。

## 機能

- **工程フロー自動描画** — 製品の `labors[]` から「材料投入 → 工程A → 工程B → 完成 / 製造間接費」を SVG で生成
- **差異オーバーレイ** — 各工程ノードに賃率差異・時間差異・合計差異、色（赤=不利・緑=有利）で視覚化
- **WIP ジャーナル** — 製品 × 工程 × 期間で「期首仕掛 / 当期投入 / 当期完成」を入力、期末仕掛は自動計算
- **差異の出所マップ** — 同名工程を全製品で横断集計し、慢性的に不利な工程をランキング表示

## 使い方

### ライブ（GitHub Pages）
1. internal-accounting で詳細モード製品（2 工程以上の labors を含む）を作成・実績入力
2. internal-accounting で「JSONエクスポート」
3. https://tsuhasqni-pixel.github.io/cost-process-flow/ で「JSONインポート」 → フロー図・WIP・出所マップへ
4. WIP ジャーナルは localStorage 保存

### ローカル Flask
```bash
./start.command          # macOS — :7864 起動、ブラウザ自動起動
```
依存: `flask`, `jinja2`（描画は自前 SVG で完結）

### CLI
```bash
python render.py /path/to/export.json --out /tmp/flow.html
open /tmp/flow.html
```

## 差異公式の真実

差異公式は **[internal-accounting/core/variance.py](https://github.com/tsuhasqni-pixel/internal-accounting/blob/main/core/variance.py)** をベンダリング。式を直すときは internal-accounting 側を先に修正し、本リポジトリ `core/variance_overlay.py` にコピーする運用とする。

## テスト

```bash
.venv/bin/python -m pytest tests/ -v
```
