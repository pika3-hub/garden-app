# 画像・写真プール・スライドショー

`app/templates/CLAUDE.md` から分割。画像アップロード全般（サムネイル生成、写真プール、フルスクリーンスライドショー）を扱う。

## 画像サムネイル

一覧画面・詳細画面の表示高速化のため、アップロード時に自動でサムネイルを生成する（`app/utils/upload.py` の `make_thumbnail()`）。

- **保存先**: `uploads/{folder}/thumbs/{basename}.jpg`（拡張子は常に .jpg）
- **サイズ**: 最大800×600px、JPEG品質80、EXIF回転補正済み
- **色プロファイル**: 元画像の ICC プロファイル（iPhone の写真は Display P3）を引き継ぐ。捨てるとブラウザが sRGB として表示し、元画像より緑がくすんで見える（2026-10-11 まではこの状態で作られていた）
- **拡大表示（lightbox）**: サムネイルを表示している `img.lightbox-target` には `data-full` で元画像を渡す（詳細画面・補足画像・写真プール）
- **Jinja2フィルター**: `{{ image_path | thumb_path }}` でサムネイルパスに変換
- **onerrorフォールバック**: サムネイルがない場合はオリジナルにフォールバック
- **GIF**: サムネイル非対応のためスキップ
- **遅延読み込み**: 件数が増える一覧のカード画像には `loading="lazy"` を付ける。付け忘れると全件の画像を最初に読み込み、スマホの初回表示が遅くなる（収穫一覧 344件で 20〜30 秒かかった。2回目以降はブラウザのキャッシュで速いので気づきにくい）。スライドショーは `img.src` を読むだけなので影響しない
- **既存画像の一括変換**: `uv run python -m app.utils.generate_thumbnails`（`uploads/` の各フォルダを走査し、無いサムネイルだけ作る）。`--force` で既存のサムネイルも作り直す。サーバーではファイルの所有者が変わらないよう、サービスを動かすユーザーで実行する

## アップロード時の変換（HEIC・撮影場所）

`app/utils/upload.py` の `save_image()` が、どの画面・API から上げた画像にも次の処理をする。

- **HEIC/HEIF**: 拡張子ではなく中身（`ftyp` の brand）で判定し、`pillow-heif` で JPEG（品質90）に変換して `.jpg` で保存する。向きは画素に反映し、色プロファイルと GPS 以外の EXIF（撮影日時など）は残す。`pillow-heif` を読み込めない環境では HEIC を受け付けない（`heif_supported()`）
- **撮影場所（GPS）は保存しない**: JPEG は EXIF のセグメントだけを差し替えて GPS を外す（`app/utils/strip_gps.py` の `strip_jpeg_gps()`。画像データに触れないので画質は変わらない）。EXIF が壊れていて読めないときは EXIF ごと外す。PNG / WebP / GIF は対象外（カメラの写真は JPEG か HEIC）。サムネイルにはもともと EXIF を入れていない
- **保存済み画像の GPS を外す**: `uv run python -m app.utils.strip_gps` で GPS を含む JPEG を数える（書き換えない）。`--apply` で外す。GPS を含む PNG / WebP はファイル名だけ表示する。実行前に `uploads/` をバックアップし、サーバーではサービスを動かすユーザーで実行する。写真プールの `file_size` は更新しない（数百バイトずれる）

## 写真プール（Photo Pool）ピッカー

モバイルで先行アップロードした写真を、各登録/編集フォームの画像フィールドから選んで送り込むための共通UI。

- **`_photo_pool_picker_modal.html`**: 共通モーダル本体。ローカルファイル選択（`<input type="file">`）と排他的に切り替えられ、使用状況（未使用/使用済み）バッジフィルター付きでプール画像を選択できる。
- **`_photo_pool_preselected.html`**: フォーム内で「写真プールから選択」した画像のプレビュー表示部品（選択解除ボタン付き）。`photo_pool_id`/`image` という固定のフィールド名を前提とするため、1画面に1箇所だけ配置する用途向け。
- **共通JS**: `app/static/js/photo-pool-picker.js`
- **利用画面**: `cooking/form.html`, `crops/form.html`, `diary/form.html`, `harvests/form.html`, `plantings/form.html`（栽培記録登録）, `locations/form.html`, `varieties/form.html`, `_supplements_section.html`（画像補足の追加時）
- **アップロード時のコピー**: `app/utils/upload.py` の `copy_image()` がプール画像を対象エンティティのフォルダへコピーする（元のプール画像は使い回し可能なまま残る）

### 1画面に複数の写真プール選択欄を置く場合（一括登録フォーム）

`harvests/bulk_form.html` / `plantings/bulk_form.html`（収穫記録・栽培記録の一括登録）は、共通の既定画像1箇所 + 行（植え付け）ごとの上書き画像を持つため、1画面に複数の `[data-photo-pool-container]` が同時に存在する。

- `photo-pool-picker.js` は `[data-photo-pool-container]` 単位でクラスベースにスキャンするため、複数個所在しても干渉しない。共有モーダル `#photoPoolPickerModal` は1つだけ include すればよい。
- 「どのトリガーボタンが押されたか」は `activeContainer`（直近クリックされたボタンの `closest('[data-photo-pool-container]')`）で判定し、モーダルでのカード選択結果をそのコンテナだけに反映する。
- `_photo_pool_preselected.html` は固定フィールド名（`photo_pool_id`, `image`）前提なので、行ごとの欄では使わずマークアップを直接複製し、`name` 属性だけ行のID付きに変える（例: `photo_pool_id_{{ lc.id }}`, `image_override_{{ lc.id }}`）。クラス名（`.photo-pool-id-input`, `.photo-pool-file-input` 等）は変えずに揃えること。
- サーバー側で「行が独自の画像を選ばなかった場合は共通の既定画像を使う」というフォールバック解決を行う（`harvest_routes.py`/`planting_routes.py` の `bulk_create()` を参照）。

## 写真の振り分け画面（`/photo_pool/sort/`）

写真プールの選択バーの「選んだ写真を振り分ける」から開く。選んだ写真を撮影日時の古い順（無いものは登録順で後ろ）に1枚ずつ表示し、種類を選んで登録する。

- **状態は URL だけ**: `ids`（並べ直し済みの写真ID）、`pos`（今の位置）、`done`（登録済み）、`kind`（種類）。サムネイル列から前後の写真へ戻れる。最後まで進むと写真プールへ戻り「n枚の写真を登録しました」
- **種類の切り替え**は GET で再描画（JS なし）。種類ごとの入力欄は `photo_sort/_fields_{kind}.html`、保存フォームは `_save_form.html`
- **既存の部品の使い回し**: 関連付け（料理・日記）は `_*_select_multi_modal.html` + `entity-select-modal.js`（初期化は `photo-sort.js`）。対象の植え付け（栽培記録・収穫）は `_planting_select_multi_modal.html` で、hidden 名は `location_crop_id`（`#planting-hidden-inputs` の `data-input-name`）。作物・品種のメモは `_ai_notes_button.html` / `ai-notes.js`（品種の親作物は `#crop_id_hidden` と `#selected-crop-display` を置く）
- **収穫量の欄**は植え付けごと。`MultiSelectModal` に変更通知が無いので、「選んだ植え付けで収穫量を入力」ボタン（`formaction` で GET）で同じ画面を再描画して作る。入力中の値は GET のパラメーターで引き継ぐ
- **AI 下書き**（`_ai_draft_button.html` + `photo-sort.js`）: 入力欄に `data-ai-field="notes"` などを付けると、返った項目がそこに入る。日付は `data-ai-date` の欄から読む。上書き前の値は「元に戻す」で戻せる。APIキーが無ければボタンを出さない。栽培記録だけ、include の前に `ai_compare` を set して「前回からの変化も書く」チェック（`data-ai-compare`、既定オン）を出す。オンなら植え付けごとに、記録日より前で写真のある最新の栽培記録（メモだけの記録は飛ばす）の写真とメモを一緒に送る（`PlantingRecord.get_previous_with_photo`）
- **写真のコピー**は保存1件ごとに `copy_image()` で別ファイルにし、`PhotoPool.record_usage()` で記録する（植え付けを複数選ぶと、その数だけコピーができる）

## スライドショー機能

画像付き一覧画面でフルスクリーンのスライドショー表示を提供する汎用コンポーネント。

### 使用箇所

| 画面 | テンプレート | キャプション内容 |
|------|------------|----------------|
| 栽培記録一覧（植え付け詳細内） | `plantings/detail.html` | メモ（80文字で切り詰め） |
| 収穫記録一覧 | `harvests/list.html` | 品種名（作物名）（`crop_display_name`）+ 収穫量 |

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
<img src="（サムネイル）" class="slideshow-target" loading="lazy"
     onerror="this.onerror=null; this.src=this.dataset.slideshowSrc"
     data-slideshow-src="（元画像）"
     data-slideshow-date="2025-07-01"
     data-slideshow-days="45"
     data-slideshow-caption="ミニトマト（トマト）">
```

### data属性

| 属性 | 必須 | 説明 |
|-----|------|------|
| `class="slideshow-target"` | ○ | JS収集対象 + クリックで起動 |
| `data-slideshow-src` | - | スライドショーで表示する元画像の URL。省略時は `img.src`（カードはサムネイルなので通常は指定する。サムネイルが無い GIF 等は `onerror` でこの URL に切り替える） |
| `data-slideshow-date` | - | フッターに表示する日付 |
| `data-slideshow-days` | - | 「植え付けから N日目」として表示 |
| `data-slideshow-caption` | - | フッターに表示するキャプションテキスト |
