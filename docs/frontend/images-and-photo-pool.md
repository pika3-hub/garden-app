# 画像・写真プール・スライドショー

`app/templates/CLAUDE.md` から分割。画像アップロード全般（サムネイル生成、写真プール、フルスクリーンスライドショー）を扱う。

## 画像サムネイル

一覧画面の表示高速化のため、アップロード時に自動でサムネイルを生成する。

- **保存先**: `uploads/{folder}/thumbs/{basename}.jpg`（拡張子は常に .jpg）
- **サイズ**: 最大800×600px、JPEG品質80、EXIF回転補正済み
- **Jinja2フィルター**: `{{ image_path | thumb_path }}` でサムネイルパスに変換
- **onerrorフォールバック**: サムネイルがない場合はオリジナルにフォールバック
- **GIF**: サムネイル非対応のためスキップ
- **既存画像の一括変換**: `uv run python app/utils/generate_thumbnails.py`

## 写真プール（Photo Pool）ピッカー

モバイルで先行アップロードした写真を、各登録/編集フォームの画像フィールドから選んで送り込むための共通UI。

- **`_photo_pool_picker_modal.html`**: 共通モーダル本体。ローカルファイル選択（`<input type="file">`）と排他的に切り替えられ、使用状況（未使用/使用済み）バッジフィルター付きでプール画像を選択できる。
- **`_photo_pool_preselected.html`**: フォーム内で「写真プールから選択」した画像のプレビュー表示部品（選択解除ボタン付き）。
- **共通JS**: `app/static/js/photo-pool-picker.js`
- **利用画面**: `cooking/form.html`, `crops/form.html`, `diary/form.html`, `harvests/form.html`, `locations/form.html`, `plantings/form.html`, `varieties/form.html`, `_supplements_section.html`（画像補足の追加時）
- **アップロード時のコピー**: `app/utils/upload.py` の `copy_image()` がプール画像を対象エンティティのフォルダへコピーする（元のプール画像は使い回し可能なまま残る）

## スライドショー機能

画像付き一覧画面でフルスクリーンのスライドショー表示を提供する汎用コンポーネント。

### 使用箇所

| 画面 | テンプレート | キャプション内容 |
|------|------------|----------------|
| 栽培記録一覧（植え付け詳細内） | `plantings/detail.html` | メモ（80文字で切り詰め） |
| 収穫記録一覧 | `harvests/list.html` | 作物名（品種名）+ 収穫量 |

### テンプレートでの使い方

1. CSS/JSを読み込む:
```html
{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/slideshow.css') }}">
{% endblock %}
{% block extra_js %}
<script src="{{ url_for('static', filename='js/slideshow.js') }}"></script>
{% endblock %}
```

2. 起動ボタンを配置（`id="slideshow-btn"`）

3. 画像に属性を付与:
```html
<img src="..." class="slideshow-target"
     data-slideshow-date="2025-07-01"
     data-slideshow-days="45"
     data-slideshow-caption="トマト（ミニトマト）">
```

### data属性

| 属性 | 必須 | 説明 |
|-----|------|------|
| `class="slideshow-target"` | ○ | JS収集対象 + クリックで起動 |
| `data-slideshow-date` | - | フッターに表示する日付 |
| `data-slideshow-days` | - | 「植え付けから N日目」として表示 |
| `data-slideshow-caption` | - | フッターに表示するキャプションテキスト |
