# 補足情報（Supplements）

`app/templates/CLAUDE.md` から分割。作物・品種・場所・日記・タスク・収穫・料理の詳細画面に、基本情報を補う外部情報を複数添付できる機能。

## 補足タイプ

| supplement_type | contentの格納値 | 表示 |
|----------------|----------------|------|
| text | テキスト本文 | Markdown で表示（`|markdown` + `.markdown-body`、[`markdown-notes.md`](markdown-notes.md)） |
| image | 画像パス（`supplements/uuid.jpg`） | サムネイル + lightbox |
| url | 完全URL（http/https） | `target="_blank" rel="noopener noreferrer"` リンク（`app/utils/ogp_fetcher.py` で取得した `ogp_image`/`ogp_title`/`ogp_description` があればOGPカード表示） |
| youtube | 動画ID または `動画ID:開始秒数` | サーバー制御のiframe埋め込み（`?start=秒数`） |

## データベース

`supplements` テーブル（`entity_type` + `entity_id` で親エンティティを参照）。詳細は `app/models/CLAUDE.md` 参照。

## YouTube処理（セキュリティ）

- ユーザー入力（URL/iframe貼り付け）から正規表現で動画ID（11文字）のみ抽出
- **生のHTML/iframeは保存しない**（XSS防止）
- 対応パターン: `watch?v=`, `youtu.be/`, `/embed/`, `/shorts/`
- タイムスタンプ（`t=`パラメータ）も抽出し `動画ID:秒数` 形式で保存
- テンプレートでサーバー制御のiframeを生成: `<iframe src="https://www.youtube.com/embed/ID?start=秒数">`
- 関連コード: `app/models/supplement.py` の `extract_youtube_info()`, `format_youtube_content()`, `parse_youtube_content()`

## 外部URL検証

- `http://` または `https://` スキームのみ許可（`javascript:` 等を排除）
- `urllib.parse.urlparse` で検証
- 関連コード: `app/models/supplement.py` の `validate_url()`

## テンプレートでの使い方

共通テンプレート `_supplements_section.html` を各詳細画面のメインカラム（操作ボタンの下）にincludeする。

```html
{% set supplement_entity_type = 'crop' %}
{% set supplement_entity_id = crop.id %}
{% include '_supplements_section.html' %}
```

テンプレート変数: `supplements`（ルートで `Supplement.get_by_entity()` から取得してテンプレートに渡す）

## ルートでの実装パターン

各エンティティのdetailルートとdeleteルートに追加が必要:

```python
# detail: 補足データ取得
from app.models.supplement import Supplement
supplements = Supplement.get_by_entity('crop', crop_id)
# render_template に supplements=supplements を追加

# delete: 連動削除（画像クリーンアップ）
supplement_images = Supplement.delete_by_entity('crop', crop_id)
for img_path in supplement_images:
    delete_image(img_path)
```

## 補足情報のルート（`supplement_routes.py`）

| エンドポイント | URL | メソッド | 説明 |
|--------------|-----|--------|------|
| `supplements.add` | `/supplements/<entity_type>/<entity_id>/add` | POST | 補足追加 |
| `supplements.update` | `/supplements/<supplement_id>/update` | POST | 補足更新 |
| `supplements.delete` | `/supplements/<supplement_id>/delete` | POST | 補足削除 |

操作後は親エンティティの詳細ページ（`#supplements` アンカー付き）にリダイレクトする。

## 画像補足

- `save_image(file, 'supplements')` で `uploads/supplements/` に保存
- サムネイルは `uploads/supplements/thumbs/` に自動生成
- 既存の `thumb_path` フィルターがそのまま動作

## 対象画面

| 画面 | entity_type | 配置位置 |
|------|------------|---------|
| 作物詳細 | crop | 操作ボタンの下 |
| 品種詳細 | variety | 操作ボタンの下 |
| 場所詳細 | location | 操作ボタンの下（見取り図カードの上） |
| 日記詳細 | diary | 操作ボタンの下 |
| タスク詳細 | task | 操作ボタンの下 |
| 収穫詳細 | harvest | 操作ボタンの下 |
| 料理詳細 | cooking | 操作ボタンの下 |
