# テンプレート開発ガイド

Jinja2 テンプレートと関連フロントエンド部品（Bootstrap カスタマイズ、共通マクロ、再利用可能な include 部品）の規約。

## base.html のブロック

- `{% block title %}` — ページタイトル
- `{% block extra_css %}` — 追加CSS読み込み
- `{% block content %}` — メインコンテンツ
- `{% block extra_js %}` — 追加JS読み込み

## 使用ライブラリ

- Bootstrap 5.3（CDN）
- Bootstrap Icons（CDN）
- Pillow（サムネイル生成、Python依存）
- ※ Fabric.js は削除済み（見取り図はバニラJSで実装）

## 作物名の表記ルール

作物名・品種名の表示はアプリ全体で統一されたルールに従う。

### 表記フォーマット

| 条件 | 表示 | 例 |
|------|------|-----|
| 品種あり | `{品種名}（{作物名}）` | ミニトマト（トマト） |
| 品種なし | `{作物名}` | バジル |

### 実装方法: 2層構造

**1. `crop_display_name` — テキスト専用グローバル関数**

`app/__init__.py` で定義・登録。プレーンテキストを返す。`<option>` タグ、`data-*` 属性、`title` 属性など **HTMLが使えない箇所** で使用する。引数 `variety` は品種名の文字列（または None）。呼び出し側は VIEW 経由で `cv.crop_name` と `cv.variety` を取得して渡す。

```html
<!-- プルダウン内（HTMLタグ不可） -->
<option>{{ crop_display_name(planting.crop_name, planting.variety) }}</option>
```

**2. `crop_label` — アイコン付きHTML用マクロ**

`app/templates/_macros.html` で定義。作物アイコン（丸型、イメージカラーボーダー、白背景）＋ `crop_display_name` テキストを返す。**HTML表示箇所** で使用する。

```html
{% from '_macros.html' import crop_label %}

<!-- カードタイトル、ナビラベル等 -->
{{ crop_label(crop.crop_name, crop.variety, crop.icon_path, crop.image_color) }}
```

引数: `name`, `variety`, `icon_path`（任意）, `image_color`（任意）

**CSSクラス**: `.crop-icon-inline`（`custom.css` で定義、22px丸型、白背景、イメージカラーボーダー）

### 適用範囲

| 対象 | 方式 | 備考 |
|------|------|------|
| HTML表示（カードタイトル、ヘッダ、ナビラベル、一覧等） | `crop_label` マクロ | アイコン＋テキスト |
| `<select>` / `<option>` 内 | `crop_display_name` 関数 | テキストのみ（HTML不可） |
| `data-*` / `title` 属性 | `crop_display_name` 関数 | テキストのみ |
| カレンダーモーダル（JS動的生成） | JS側で `item.icon_path` を参照 | `calendar.js` で生成 |
| 見取り図サイドバー（エディター・配置ページ） | `crop_display_name` 関数 | テキストのみ |
| 作物一覧（カードタイトル） | `crop_label` マクロ | アイコン＋テキスト、`variety=None` を渡す |
| 品種一覧（カードタイトル） | `crop_label` マクロ | アイコン＋テキスト、`effective_icon_path` / `effective_image_color` で継承反映 |
| 作物エンティティ画面（登録・編集） | アイコン表示なし | `crop_display_name` のみ使用 |

### クエリ要件

`crop_label` マクロは `icon_path` / `image_color` を引数に取るので、モデルのクエリで該当カラムを SELECT する必要がある。ソースは画面によって異なる：

- **植え付け・収穫・カレンダー等**: `crop_variety_view cv` から `cv.crop_name, cv.variety, cv.icon_path, cv.image_color`（品種の外観が優先、未設定なら親作物に継承される）
- **作物一覧・作物詳細**: `crops` テーブルから `c.icon_path, c.image_color`。品種情報は持たないので `crop_label(c.name, None, ...)` の形で呼ぶ
- **品種一覧・品種詳細**: `Variety.apply_inheritance()` により付与される `effective_icon_path` / `effective_image_color`

新規クエリ追加時は、`cv.*` のワイルドカード展開ではなくカラムを明示すること（`app/models/CLAUDE.md` の Row 重複カラム名問題を参照）。

## 画像サムネイル

一覧画面の表示高速化のため、アップロード時に自動でサムネイルを生成する。

- **保存先**: `uploads/{folder}/thumbs/{basename}.jpg`（拡張子は常に .jpg）
- **サイズ**: 最大800×600px、JPEG品質80、EXIF回転補正済み
- **Jinja2フィルター**: `{{ image_path | thumb_path }}` でサムネイルパスに変換
- **onerrorフォールバック**: サムネイルがない場合はオリジナルにフォールバック
- **GIF**: サムネイル非対応のためスキップ
- **既存画像の一括変換**: `uv run python app/utils/generate_thumbnails.py`

## ダッシュボード画像カルーセル

HOME画面（`index.html`）の統計カード下部に、最近登録された画像をランダム順で自動再生するカルーセルを表示する。

### データ取得

`app/__init__.py` の `index()` ルート内で、6テーブル（`crops`, `varieties`, `locations`, `diary_entries`, `harvests`, `planting_records`）から `image_path` が存在するレコードをUNION ALLクエリで最大20件取得し、`random.shuffle()` でランダム化。各画像に `detail_url`（詳細ページURL）、`icon`（種別アイコン）、`type_label`（種別名）を付与してテンプレートに渡す。`harvests` / `planting_records` の作物名・品種名は `crop_variety_view` から取得する。

### 実装

- **コンポーネント**: Bootstrap 5 標準 Carousel（`data-bs-ride="carousel"`, 4秒間隔自動再生）
- **画像**: サムネイル（`thumb_path` フィルター）使用、`onerror` でオリジナル画像にフォールバック
- **キャプション**: 画像下部にグラデーションオーバーレイ + 種別アイコン付きバッジラベル
- **リンク**: 画像クリックで対応する詳細ページに遷移
- **画像なし**: カルーセル自体を非表示（`{% if carousel_images %}`）

### レスポンシブ対応

| 表示 | デスクトップ（md以上） | モバイル（md未満） |
|------|----------------------|-------------------|
| 画像高さ | 360px | 300px |
| 操作 | 左右ボタン | 左右ボタン + スワイプ操作（Bootstrap標準） |

### CSS（`custom.css` の `Dashboard Carousel` セクション）

| クラス / セレクター | 役割 |
|---------------------|------|
| `#dashboardCarousel` | コンテナ（角丸、overflow hidden） |
| `#dashboardCarousel:hover` | `.card:hover` の `translateY` を無効化 |
| `.carousel-dashboard-img` | 画像（固定高さ + `object-fit: cover`） |
| `.carousel-caption-badge` | キャプションバッジ（フォレストグリーン背景） |
| `.carousel-counter` | モバイル用枚数カウンター（中央下部、半透明背景） |

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

## 詳細画面 基本情報カード

全詳細画面の基本情報は `card-photo-detail` パターンで統一表示。画像上・テキスト下の縦積みレイアウト。

### CSS（`custom.css` の `DETAIL HERO CARD` セクション）

| クラス | 役割 |
|--------|------|
| `.card-photo-detail` | コンテナ（`display: flex; flex-direction: column`） |
| `.card-photo-detail-img-wrapper` | 画像ラッパー（`position: relative`、日付オーバーレイの基準） |
| `.card-photo-img` | 画像（`object-fit: contain` で切れずに中央表示、`max-height: 420px`） |
| `.card-photo-detail-overlay` | テキストパネル（通常フロー、`border-top` で画像と区切り） |
| `.card-photo-detail-title` | タイトル（`color: var(--forest)`） |
| `.detail-fields` / `.detail-field` | フィールド群（縦積み左揃え） |
| `.detail-field-label` / `.detail-field-value` | ラベルと値 |
| `.detail-notes` | メモ・本文（`white-space: pre-wrap`） |
| `.detail-timestamps` | タイムスタンプ（`登録日時: ... / 更新日時: ...` 統一書式） |

### 各画面のHTML構造

```html
<div class="card mb-3 card-photo-detail card-bg-{type} {画像なし: card-no-image}">
    <!-- 画像あり時 -->
    <div class="card-photo-detail-img-wrapper">
        <img src="..." class="card-photo-img lightbox-target" alt="...">
        <!-- 日付オーバーレイ（植え付け詳細のみ） -->
        <div class="card-img-date-overlay">2026-01-01</div>
    </div>
    <!-- テキストパネル -->
    <div class="card-photo-detail-overlay">
        <h4 class="card-photo-detail-title">タイトル</h4>
        <div class="detail-fields">...</div>
        <div class="detail-notes">メモ</div>
        <div class="detail-timestamps">登録日時: ... / 更新日時: ...</div>
    </div>
</div>
```

### 画像の扱い

| ページ | 画像ソース | 画像なし時 |
|--------|-----------|-----------|
| 作物 | `crop.image_path` | テキストのみ表示 |
| 場所 | `location.image_path` | テキストのみ表示 |
| 植え付け | `records`の最新画像付きレコード（`namespace`使用） | テキストのみ表示 |
| 栽培記録 | `record.image_path` | テキストのみ表示 |
| 収穫 | `harvest.image_path` | テキストのみ表示 |
| 日記(画像あり) | `entry.image_path` | - |
| 日記(天気あり) | なし（`card-weather-bg` + `::before` で天気背景） | - |
| 日記(その他) | なし | テキストのみ表示 |
| タスク | なし（常にテキストのみ） | テキストのみ表示 |

- 画像ありの場合のみ `lightbox-target` クラスを付与（既存 `lightbox.js` が動作）
- 画像なし時（`card-no-image`）はテキストパネルのみ表示（フォールバック画像なし）
- 植え付け詳細の画像取得は Jinja2 の `namespace` パターン（`{% set ns = namespace(hero_image=None) %}`）でループ内から変数を書き出す

## 詳細画面の操作ボタン配置

全詳細画面で編集・削除ボタンは基本情報カードの直下に `btn-group-action` で統一配置する。右カラムに「操作」カードは置かない。

### `btn-group-action` パターン

```html
<div class="btn-group-action">
    <a href="..." class="btn btn-primary"><i class="bi bi-pencil"></i> 編集</a>
    <form method="POST" action="..." class="d-inline" onsubmit="return confirm(...);">
        <button type="submit" class="btn btn-danger"><i class="bi bi-trash"></i> 削除</button>
    </form>
</div>
```

CSS: `display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;`（モバイルでは縦積み）

### 各画面のボタン構成

| 画面 | ボタン |
|------|--------|
| 作物詳細 | 編集、削除 |
| 場所詳細 | 編集、削除 |
| 植え付け詳細(active) | 編集、収穫を記録、栽培を終了（モーダル）、削除 |
| 植え付け詳細(harvested) | 編集、削除 |
| 収穫詳細 | 編集、削除 |
| 日記詳細 | 編集、削除 |
| タスク詳細 | 編集、削除 |

### 新規登録ボタンの配置ルール

新規登録系のボタンは関連する一覧の直上に配置する:
- 場所詳細の「作物を植え付ける」→ 栽培中の作物カード内、テーブルの上
- 植え付け詳細の「栽培記録を追加」→ 栽培記録一覧の見出し横

### 栽培終了モーダル

植え付け詳細（active）の「栽培を終了」ボタンはBootstrap 5モーダル（`#endCultivationModal`）で確認ダイアログを表示。栽培終了日の入力フィールドを含む。POST先は `plantings.end_cultivation`。

## 詳細画面サイドバーカード（関連情報）

全詳細画面の右カラム（サイドバー）に共通テンプレート部品で関連情報カードを表示する。各カードは `{% set %}` で変数を構築してから `{% include %}` するパターン。データが空の場合はカード自体が非表示になる。関連データは最大10件（`limit=10`）で取得する。

### カードヘッダーアイコン

各カードのヘッダーには `images/icon_*.webp` を使用する（Bootstrap Icons ではなく）。

| カード | アイコン | ヘッダー背景色 |
|--------|---------|--------------|
| 作物情報 | `icon_crop.webp` | `bg-success` |
| 品種情報 | `icon_variety.webp` | `bg-success` |
| 場所情報 | `icon_location.webp` | `bg-info` |
| タスク | `icon_tasklist.webp` | `bg-primary` |
| 関連する植え付け | `icon_location_crop.webp` | `bg-warning` |
| 関連する収穫 | `icon_harvest.webp` | `bg-success` |
| 関連する日記 | `icon_diary.webp` | `bg-primary` |
| 関連する作物 | `icon_crop.webp` | `bg-success` |
| 関連する場所 | `icon_location.webp` | `bg-info` |

### カード配置順序（統一ルール）

| 画面 | カード順序 |
|------|-----------|
| 作物詳細 | タスク → 栽培中の植え付け → 収穫 → 日記 |
| 品種詳細 | 親作物情報 → この品種の栽培中 → 関連する収穫 |
| 場所詳細 | タスク → 収穫 → 日記 |
| 植え付け詳細 | 作物情報 → 品種情報（variety_id があれば） → 場所情報 → タスク → 収穫 → 日記 |
| 収穫詳細 | 作物情報 → 品種情報（variety_id があれば） → 場所情報 → 植え付け → 日記 |
| 栽培記録詳細 | 作物情報 → 品種情報（variety_id があれば） → 場所情報 |
| 日記詳細 | 作物 → 場所 → 植え付け → 収穫 |
| タスク詳細 | 作物 → 場所 → 植え付け |

原則: 情報カード（静的参照）→ タスク（アクション）→ 関連データ（ナビゲーション）

### 作物情報カード (`_crop_info_card.html`)

植え付け詳細・収穫詳細・栽培記録詳細・品種詳細の右カラムに配置。作物の登録画像がある場合、カード本体内の右上に縮小表示（`float: right; width: 48%`）。`variety_id` を渡せば作物詳細リンクの下に「品種詳細へ」リンクが表示されるが、植え付け・収穫・栽培記録の各詳細では「品種情報カード」を別途表示する方針のため `variety_id: None` を渡す。

**テンプレート変数**: `crop_info` dict

```html
{% set crop_info = {
    'crop_id': parent_crop.id,
    'crop_name': parent_crop.name,
    'variety': None,
    'variety_id': None,
    'icon_path': parent_crop.icon_path,
    'image_color': parent_crop.image_color,
    'crop_type': parent_crop.crop_type,
    'crop_notes': parent_crop.notes,
    'crop_image_path': parent_crop.image_path
} %}
{% include '_crop_info_card.html' %}
```

**表示内容**: 作物名＋品種名（`crop_label` マクロ、`variety` が渡された場合のみ品種を表記）、品種詳細リンク（`variety_id` がある場合のみ）、登録画像（右上フロート）、種類（badge）、メモ（Markdown 統合テキスト）、作物詳細リンク。各フィールドは値がある場合のみ表示。

**データソース**: `Planting.get_by_id()` / `Harvest.get_by_id()` / `PlantingRecord.get_by_id()` 由来の `cv.*` は **品種オーバーライド込みの継承後値** のため作物の素の値を見せたいケースには使わない。各ルート（`planting_routes.detail/record_detail`、`harvest_routes.detail`、`variety_routes.detail`）で **`Crop.get_by_id(effective_crop_id)` を別途呼び出して `parent_crop` をテンプレートに渡す**。`variety_routes.detail()` も同様に `Variety.get_by_id()` で JOIN 取得した `crop_*` フィールドから親作物情報を組み立てる（VIEW を経由しない）。

### 品種情報カード (`_variety_info_card.html`)

植え付け詳細・収穫詳細・栽培記録詳細の右カラムに、品種が紐づく植え付け（`variety_id` あり）のときだけ作物情報カードの直後に表示する。品種独自のオーバーライドが何もない場合は「※ 外観・メモは親作物から継承」のヒントを表示する。

**テンプレート変数**: `variety_info` dict

```html
{% if variety %}
{% set variety_info = {
    'variety_id': variety.id,
    'variety_name': variety.name,
    'parent_crop_id': variety.crop_id,
    'parent_crop_name': variety.crop_name,
    'icon_path': variety.effective_icon_path,
    'image_color': variety.effective_image_color,
    'variety_notes': variety.notes,
    'variety_image_path': variety.effective_image_path,
    'has_overrides': variety.icon_path or variety.image_color or variety.image_path or variety.notes
} %}
{% include '_variety_info_card.html' %}
{% endif %}
```

**表示内容**: 品種名（作物名）の `crop_label`（品種詳細へリンク）、品種画像（オーバーライドがあれば品種独自、なければ親作物継承、右上フロート）、品種メモ（オーバーライド時のみ）、継承ヒント（オーバーライドが一つも無い場合のみ）。種類バッジは作物情報カードと重複するため省略。

**データソース**: 各ルート（`planting_routes.detail/record_detail`、`harvest_routes.detail`）で `location_crop['variety_id']` または `record['variety_id']` が NULL でないとき `Variety.get_by_id(variety_id)` で取得し、`Variety.apply_inheritance(variety)` で `effective_icon_path` / `effective_image_color` / `effective_image_path` を付与してテンプレートに渡す。

**`Variety.apply_inheritance(variety)` (`app/models/variety.py`)**: 品種に `effective_*` フィールドを付加する静的メソッド。元の `icon_path` / `image_color` / `image_path` は保持されるため、テンプレート側で「品種独自のオーバーライドがあるか」を判定できる（`has_overrides`）。同モデルの `get_effective_display()` は元フィールドを上書きする破壊的バージョンなので用途が異なる。

### 場所情報カード (`_location_info_card.html`)

植え付け詳細・収穫詳細の右カラムに配置。場所の登録画像がある場合、カード本体内の右上に縮小表示（`float: right; width: 48%`）。

**テンプレート変数**: `location_info` dict

```html
{% set location_info = {
    'location_id': location_crop.location_id,
    'location_name': location_crop.location_name,
    'location_type': location_crop.location_type,
    'area_size': location_crop.area_size,
    'sun_exposure': location_crop.sun_exposure,
    'location_notes': location_crop.location_notes,
    'location_image_path': location_crop.location_image_path
} %}
{% include '_location_info_card.html' %}
```

**表示内容**: 登録画像（右上フロート）、種類（badge）、面積、日当たり、メモ、場所詳細リンク。

**クエリ要件**: `Planting.get_by_id()` と `Harvest.get_by_id()` で `l.location_type, l.area_size, l.sun_exposure, l.notes as location_notes, l.image_path as location_image_path` をSELECTしている。

### 関連カード一覧

| テンプレート | 変数名 | 必須フィールド | マクロ |
|------------|--------|-------------|--------|
| `_related_plantings_card.html` | `related_plantings` | id, crop_name, variety, icon_path, image_color, location_name, location_id, planted_date, status | `crop_label` |
| `_related_harvests_card.html` | `related_harvests` | id, crop_name, variety, icon_path, image_color, location_name, harvest_date, quantity, unit | `crop_label` |
| `_related_diaries_card.html` | `related_diaries` | id, title, entry_date, weather | なし |
| `_related_crops_card.html` | `related_crops` | crop_id, crop_name, variety, icon_path, image_color, crop_type | `crop_label` |
| `_related_locations_card.html` | `related_locations` | location_id, location_name, location_type | なし |

`_related_plantings_card.html` はオプション変数 `related_plantings_title` でヘッダーテキストを変更可能（デフォルト: 「関連する植え付け」、作物詳細では「栽培中の植え付け」）。

## 一覧画面のバッジフィルター

作物・場所・植え付け・収穫の一覧画面では、種類バッジによるクライアントサイドフィルターを提供する。日記・タスクは従来のサーバーサイド検索を維持。

### 2つのモード

共通JS `app/static/js/badge-filter.js` が2つのモードを自動判定する:

**レガシーモード（作物一覧・場所一覧）:** `#badge-filter-container` + `data-filter-type` による単一グループフィルター。OR論理（複数選択でいずれかに一致）。

**マルチグループモード（植え付け一覧・収穫一覧）:** `.badge-filter-group[data-filter-key]` による複数グループフィルター。グループ間AND・グループ内OR。カードは `data-filter-card` + `data-filter-group-{key}` 属性を使用。

### 各画面のフィルター対象

| 画面 | モード | フィルター対象 | ルートで渡す変数 |
|------|--------|-------------|----------------|
| 作物一覧 | レガシー | `crop_type` | `filter_types` |
| 場所一覧 | レガシー | `location_type` | `filter_types` |
| 植え付け一覧 | マルチグループ | `crop_type` + `location_name` | `filter_types`, `filter_locations` |
| 収穫記録一覧 | マルチグループ | `crop_type` + `location_name` | `filter_types`, `filter_locations` |

### テンプレートでの使い方

**レガシーモード（作物・場所一覧）:**

```html
{% if filter_types %}
<div id="badge-filter-container" class="badge-filter-container">
    {% for t in filter_types %}
    <span class="badge badge-filter badge-filter-inactive" data-type="{{ t }}">{{ t }}</span>
    {% endfor %}
</div>
{% endif %}

<!-- カードラッパーに data-filter-type を付与 -->
<div class="col-md-6 col-lg-4 mb-3" data-filter-type="{{ item.crop_type }}">
```

**マルチグループモード（植え付け・収穫一覧）:**

```html
{% if filter_types or filter_locations %}
<div class="badge-filter-multi">
    {% if filter_types %}
    <div class="badge-filter-group" data-filter-key="cropType">
        <span class="badge-filter-group-label">種類:</span>
        {% for t in filter_types %}
        <span class="badge badge-filter badge-filter-inactive" data-type="{{ t }}">{{ t }}</span>
        {% endfor %}
    </div>
    {% endif %}
    {% if filter_locations %}
    <div class="badge-filter-group" data-filter-key="locationName">
        <span class="badge-filter-group-label">場所:</span>
        {% for loc in filter_locations %}
        <span class="badge badge-filter badge-filter-inactive" data-type="{{ loc }}">{{ loc }}</span>
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endif %}

<!-- カードラッパーに data-filter-card + data-filter-group-* を付与 -->
<div class="col-md-6 col-lg-4 mb-3" data-filter-card data-filter-group-crop-type="{{ item.crop_type }}" data-filter-group-location-name="{{ item.location_name }}">
```

**共通（件数・0件メッセージ）:**

```html
<p class="text-muted mb-3"><span id="filter-count" data-suffix="件の作物">{{ items|length }}件の作物</span></p>
<div id="filter-empty-msg" class="alert alert-info" style="display:none;">
    <i class="bi bi-info-circle"></i> 該当する項目がありません。
</div>
```

CSSクラス: `.badge-filter-container`, `.badge-filter-multi`, `.badge-filter-group`, `.badge-filter-group-label`, `.badge-filter`, `.badge-filter-active`, `.badge-filter-inactive`（`custom.css` で定義）

## 一覧画面のグルーピング表示

主要な一覧画面はサーバー側で `itertools.groupby` を使いセクションごとにグループ化して表示する。各グループは `<section class="date-group">` + `<h3 class="date-group-heading">` で描画し、グループ間の区切りを視覚化する。

### 各画面のグループ化ルール

| 画面 | ルート変数 | グループキー | グループ順 | 見出し |
|------|-----------|-------------|----------|--------|
| 日記一覧 | `grouped_entries` | `entry_date` の `YYYY-MM` | `entry_date DESC`（新しい月が上） | `YYYY年M月` |
| 植え付け一覧 | `grouped_crops` | `planted_date` の `YYYY-MM` | `planted_date DESC` | `YYYY年M月` |
| 収穫記録一覧 | `grouped_harvests` | `harvest_date` の `YYYY-MM` | `harvest_date DESC` | `YYYY年M月` |
| 作物一覧 | `grouped_crops` | `crop_type` | 件数多い順、1件のみは末尾「その他」にまとめる | 作物アイコン（`filter_type_icons`）+ 種類名 |
| 場所一覧 | `grouped_locations` | `location_type` | 件数多い順、1件のみは末尾「その他」にまとめる | 種類名 |
| タスク一覧 | `grouped_tasks` | `status` | `進行中 → 未着手 → 完了`（`Task.get_all()` の ORDER BY） | ステータスバッジ + ラベル + 件数 |

### ルートでの実装パターン

日付グループ（日記・植え付け・収穫）はモデルが既に `{date} DESC` でソート済みのため、そのまま `itertools.groupby` で連続ラン化できる:

```python
def _ym_key(e):
    d = e.get('entry_date')
    return str(d)[:7] if d else ''

grouped_entries = [(k, [item for item in g]) for k, g in groupby(entries, key=_ym_key)]
```

注意: Flask ルート関数名が `list` の場合、ビルトイン `list` がシャドウされるため `list(g)` は `TypeError` になる。内包表記 `[item for item in g]` を使うこと。

種類グループ（作物・場所）は種類キーでソート → グループ化 → 件数降順 → 1件グループを「その他」にマージする:

```python
sorted_crops = sorted(crops, key=_type_key)
grouped_crops = [(k, [item for item in g]) for k, g in groupby(sorted_crops, key=_type_key)]
grouped_crops.sort(key=lambda kv: len(kv[1]), reverse=True)
multi_groups = [kv for kv in grouped_crops if len(kv[1]) > 1]
single_items = [items[0] for _, items in grouped_crops if len(items) == 1]
if single_items:
    multi_groups.append(('その他', single_items))
grouped_crops = multi_groups
```

Pythonの `sorted` は stable のため、種類内の元順序（`created_at DESC`）は保たれる。

### テンプレートでの使い方

```html
{% for key, group_items in grouped_items %}
<section class="date-group" data-group-key="{{ key }}">
    <h3 class="date-group-heading">{{ key }}</h3>
    <div class="row">
        {% for item in group_items %}
        <div class="col-6 col-md-4 col-lg-3 mb-3" data-filter-...>...</div>
        {% endfor %}
    </div>
</section>
{% endfor %}
```

作物一覧の見出しはフィルタバッジと同じアイコンを表示するため `filter_type_icons.get(ct, [])` をループして `<img class="badge-filter-icon">` を先頭に並べる。

### 空グループの自動非表示

フィルターバッジ操作で該当カードが0件になったセクションは見出しごと非表示にする。`badge-filter.js`（マルチグループ・レガシー両モード）と `date-badge-filter.js` の各 `applyFilter()` 末尾に以下を追加している:

```js
var dateGroups = document.querySelectorAll('.date-group');
dateGroups.forEach(function (group) {
    var visible = false;
    group.querySelectorAll('[data-filter-...]').forEach(function (item) {
        if (item.style.display !== 'none') visible = true;
    });
    group.style.display = visible ? '' : 'none';
});
```

対象セレクタは JS ごとに異なる（`[data-filter-year]` / `[data-filter-card]` / `[data-filter-type]`）。

### CSSクラス

| クラス | 役割 |
|--------|------|
| `.date-group` | セクションラッパー（`custom.css` 末尾の `Date Group` セクションで定義） |
| `.date-group-heading` | 見出し（フォレストグリーン下線、`h3` スタイル） |

## エンティティ選択モーダル（複数選択）

日記・タスクの登録・編集フォームで、関連エンティティ（作物・場所・植え付け・収穫）をカード型モーダルで複数選択する共通機能。

### 共通JS

`app/static/js/entity-select-modal.js` — `MultiSelectModal` クラス。

### 使い方

```js
new MultiSelectModal({
    modalId: 'cropMultiSelectModal',        // モーダルのDOM id
    cardSelector: '.crop-ms-card',          // 選択可能カードのセレクタ
    idAttribute: 'cropId',                  // card.dataset からID取得するキー
    inputContainerId: 'crop-hidden-inputs', // hidden input 配置コンテナ
    inputName: 'crop_ids',                  // hidden input の name 属性
    displayContainerId: 'selected-crops-display', // バッジチップ表示コンテナ
    badgeRenderer: function(card) { ... },  // カード→バッジHTML生成コールバック
    filterMode: 'legacy',                   // 'legacy'（単一グループ）or 'multi'（マルチグループ）
    filterScope: 'crop-multi',              // legacy用: data-scope 値
    filterCardAttr: 'data-crop-ms-card',    // legacy用: カードのフィルタ属性
});
```

### 動作

- カードクリック → `.ms-card-selected` トグル（チェックマーク表示）
- モーダルフッターの「決定」ボタン → hidden inputs 同期 + バッジチップ描画 + モーダルclose
- バッジチップの「×」→ 選択解除（hidden input 削除、カードハイライト解除）
- 初期化時に既存 hidden inputs を読み取り pre-selected 状態を復元（編集モード対応）

### フィルターモード

| モード | 用途 | 仕組み |
|--------|------|--------|
| `legacy` | 作物・場所モーダル | `data-scope` + `data-filter-type` による単一グループフィルター |
| `multi` | 植え付け・収穫モーダル | `data-ms-filter-card` + `data-ms-filter-group-*` によるマルチグループフィルター（AND/OR） |

モーダル内のフィルターは `badge-filter.js` とは独立してスコープされる（同一ページに複数モーダルがあっても干渉しない）。

### モーダルテンプレート

| テンプレート | Modal ID | 対象画面 | テンプレート変数 |
|------------|----------|---------|----------------|
| `_crop_select_multi_modal.html` | `cropMultiSelectModal` | 日記・タスク | `crops`, `crop_filter_types`, `crop_filter_type_icons`, `selected_crop_ids` |
| `_variety_select_multi_modal.html` | `varietyMultiSelectModal` | 日記・タスク | `varieties`（`apply_inheritance` 適用済み）, `variety_filter_types`, `variety_filter_type_icons`, `selected_variety_ids` |
| `_location_select_multi_modal.html` | `locationMultiSelectModal` | 日記・タスク | `locations`, `location_filter_types`, `selected_location_ids` |
| `_planting_select_multi_modal.html` | `plantingMultiSelectModal` | 日記・タスク | `active_plantings`, `planting_filter_types`, `planting_filter_type_icons`, `planting_filter_locations`, `selected_location_crop_ids` |
| `_harvest_select_multi_modal.html` | `harvestMultiSelectModal` | 日記のみ | `harvests`, `harvest_filter_types`, `harvest_filter_type_icons`, `harvest_filter_locations`, `selected_harvest_ids` |

### ルートでの実装パターン

各ルートでフィルターデータを計算して `render_template` に渡す。`diary_routes.py` と `task_routes.py` にそれぞれ `_build_filter_data()` ヘルパーがある。

```python
active_plantings = Planting.get_all_with_stats(status='active')
filter_data = _build_filter_data(crops, locations, active_plantings, harvests)
render_template('diary/form.html', ..., **filter_data)
```

編集時は `selected_crop_ids`, `selected_location_ids`, `selected_location_crop_ids`, `selected_harvest_ids`（文字列IDのリスト）も追加で渡す。

### CSSクラス

| クラス | 役割 |
|--------|------|
| `.ms-card-selected` | 選択中カード（チェックマーク付きアウトライン） |
| `.selected-items-chips` | バッジチップコンテナ（空時は「未選択」表示） |
| `.selected-item-chip` | 個別バッジチップ（丸型、×ボタン付き） |
| `.ms-modal-footer` | モーダルフッター（件数 + 決定ボタン） |

## 詳細画面ナビゲーション

全詳細画面で前後データへの移動ボタンを表示する共通機能。一覧に戻らずにデータ間を移動できる。

### 共通部品

`app/templates/_detail_nav.html` — 前後ナビボタンを描画する include 用テンプレート。

### テンプレートでの使い方

`{% set %}` で変数を構築してから `{% include %}` する。配置場所は `<div class="row">` の直前（全幅）。

```html
{% set prev_item = {'url': url_for('crops.detail', crop_id=prev_crop.id),
                    'button_text': '前の作物',
                    'label': prev_crop.name} if prev_crop else None %}
{% set next_item = {'url': url_for('crops.detail', crop_id=next_crop.id),
                    'button_text': '次の作物',
                    'label': next_crop.name} if next_crop else None %}
{% set nav_label = '作物ナビゲーション' %}
{% include '_detail_nav.html' %}
```

### 各画面の `get_adjacent()` 実装

| 画面 | モデルメソッド | 表示順 | ラベル |
|------|-------------|--------|-------|
| 作物詳細 | `Crop.get_adjacent(crop_id)` | `created_at DESC` | 作物名 |
| 品種詳細 | `Variety.get_adjacent(variety_id)` | `crop_id ASC, created_at DESC` | 品種名（作物名） |
| 場所詳細 | `Location.get_adjacent(location_id)` | `created_at DESC` | 場所名 |
| 植え付け詳細 | `Planting.get_adjacent(id, status)` | `planted_date DESC`、同じステータス内 | 作物名（品種）- 場所名 |
| 栽培記録詳細 | `PlantingRecord.get_adjacent(record_id)` | `recorded_at DESC`、同一植え付け内 | 記録日 |
| 収穫詳細 | `Harvest.get_adjacent(harvest_id)` | `harvest_date DESC` | 収穫日 作物名 |
| 日記詳細 | `DiaryEntry.get_adjacent(diary_id)` | `entry_date DESC` | 日付 タイトル |
| タスク詳細 | `Task.get_adjacent(task_id)` | ステータス順→期限日（Python側でインデックス検索） | タイトル |

## 補足情報（Supplements）

作物・場所・日記・タスク・収穫の詳細画面に、基本情報を補う外部情報を複数添付できる機能。

### 補足タイプ

| supplement_type | contentの格納値 | 表示 |
|----------------|----------------|------|
| text | テキスト本文 | `pre-wrap`で表示 |
| image | 画像パス（`supplements/uuid.jpg`） | サムネイル + lightbox |
| url | 完全URL（http/https） | `target="_blank" rel="noopener noreferrer"` リンク |
| youtube | 動画ID または `動画ID:開始秒数` | サーバー制御のiframe埋め込み（`?start=秒数`） |

### データベース

`supplements` テーブル（`entity_type` + `entity_id` で親エンティティを参照）。詳細は `app/models/CLAUDE.md` 参照。

### YouTube処理（セキュリティ）

- ユーザー入力（URL/iframe貼り付け）から正規表現で動画ID（11文字）のみ抽出
- **生のHTML/iframeは保存しない**（XSS防止）
- 対応パターン: `watch?v=`, `youtu.be/`, `/embed/`, `/shorts/`
- タイムスタンプ（`t=`パラメータ）も抽出し `動画ID:秒数` 形式で保存
- テンプレートでサーバー制御のiframeを生成: `<iframe src="https://www.youtube.com/embed/ID?start=秒数">`
- 関連コード: `app/models/supplement.py` の `extract_youtube_info()`, `format_youtube_content()`, `parse_youtube_content()`

### 外部URL検証

- `http://` または `https://` スキームのみ許可（`javascript:` 等を排除）
- `urllib.parse.urlparse` で検証
- 関連コード: `app/models/supplement.py` の `validate_url()`

### テンプレートでの使い方

共通テンプレート `_supplements_section.html` を各詳細画面のメインカラム（操作ボタンの下）にincludeする。

```html
{% set supplement_entity_type = 'crop' %}
{% set supplement_entity_id = crop.id %}
{% include '_supplements_section.html' %}
```

テンプレート変数: `supplements`（ルートで `Supplement.get_by_entity()` から取得してテンプレートに渡す）

### ルートでの実装パターン

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

### 補足情報のルート（`supplement_routes.py`）

| エンドポイント | URL | メソッド | 説明 |
|--------------|-----|--------|------|
| `supplements.add` | `/supplements/<entity_type>/<entity_id>/add` | POST | 補足追加 |
| `supplements.update` | `/supplements/<supplement_id>/update` | POST | 補足更新 |
| `supplements.delete` | `/supplements/<supplement_id>/delete` | POST | 補足削除 |

操作後は親エンティティの詳細ページ（`#supplements` アンカー付き）にリダイレクトする。

### 画像補足

- `save_image(file, 'supplements')` で `uploads/supplements/` に保存
- サムネイルは `uploads/supplements/thumbs/` に自動生成
- 既存の `thumb_path` フィルターがそのまま動作

### 対象画面

| 画面 | entity_type | 配置位置 |
|------|------------|---------|
| 作物詳細 | crop | 操作ボタンの下 |
| 品種詳細 | variety | 操作ボタンの下 |
| 場所詳細 | location | 操作ボタンの下（見取り図カードの上） |
| 日記詳細 | diary | 操作ボタンの下 |
| タスク詳細 | task | 操作ボタンの下 |
| 収穫詳細 | harvest | 操作ボタンの下 |
