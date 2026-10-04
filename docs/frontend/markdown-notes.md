# メモ欄の Markdown 表示

メモ・本文などのテキストは、入力はそのまま（Markdown）で保存し、表示時にサーバー側で HTML に変換する。

## 実装

- `app/utils/markdown_render.py` の `render_markdown()` を Jinja フィルター `markdown` として登録（`app/__init__.py`）
- ライブラリは `markdown-it-py`（CommonMark + 表 + 取り消し線）。CDN の JS に頼らないので、オフラインのスマホでも同じ表示になる
- `html=False`: 入力中の生 HTML はエスケープされる。`javascript:` などの危険な URL もリンク化されない。**`|safe` を併用しないこと**（フィルターが `Markup` を返すので不要）
- `breaks=True`: 単独の改行も `<br />` にする。Markdown を意識せずに書かれた既存のメモも、従来の `pre-wrap` 表示と同じ改行で見える
- リンクは `target="_blank" rel="noopener noreferrer"` を付与
- 空・None は空文字を返す（呼び出し側の `{% if x.notes %}` はそのまま残す）

## 使い方

```html
<div class="detail-notes markdown-body">{{ crop.notes|markdown }}</div>
```

- `.markdown-body`（`custom.css` の「Markdown 表示」セクション）が見出し・リスト・表・引用・コードの余白と装飾を整え、`.detail-notes` / `.supplement-text` の `white-space: pre-wrap` を `normal` に打ち消す（両クラスより後に定義しているため。順序を入れ替えないこと）
- 見出しは本文サイズに合わせて小さめ（h1 1.15em、h2 1.08em + 下線）

## 対象箇所

| 箇所 | テンプレート |
|------|-------------|
| 詳細画面の基本情報カード | 作物・品種・場所・植え付け・栽培記録・収穫・日記（`content`）・タスク（`description`）・料理の各 `detail.html` / `plantings/record_detail.html` |
| 補足情報のテキスト | `_supplements_section.html` |
| サイドバーの情報カード | `_crop_info_card.html` / `_variety_info_card.html` / `_location_info_card.html` |

**対象外**: 1行に切り詰めるプレビュー（栽培記録カード、写真プールのメモ、スライドショーのキャプションなど）はプレーンテキストのまま。Markdown 記号が見えても行が崩れないことを優先している。新たにメモを表示する画面を作るときは、全文表示なら `|markdown` + `.markdown-body`、切り詰め表示ならプレーンテキストにする。
