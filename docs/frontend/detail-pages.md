# 詳細画面（基本カード・操作ボタン・サイドバー・前後ナビゲーション）

`app/templates/CLAUDE.md` から分割。全詳細画面（作物・品種・場所・植え付け・栽培記録・収穫・日記・タスク・料理）に共通するレイアウト規約をまとめる。

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
| 関連する品種 | `icon_variety.webp` | `bg-success` |
| 関連する料理 | `icon_cooking.webp` | `bg-warning` |

### カード配置順序（統一ルール）

| 画面 | カード順序 |
|------|-----------|
| 作物詳細 | タスク → 栽培中の植え付け → 収穫 → 栽培終了した植え付け → 日記 → 関連する料理 |
| 品種詳細 | 親作物情報 → この品種の栽培中 → 関連する収穫 → 栽培終了した植え付け → 日記 → 関連する料理 → タスク |
| 場所詳細 | タスク → 収穫 → 栽培終了した植え付け → 日記 |
| 植え付け詳細 | 作物情報 → 品種情報（variety_id があれば） → 場所情報 → タスク → 収穫 → 日記 → 関連する料理 |
| 収穫詳細 | 作物情報 → 品種情報（variety_id があれば） → 場所情報 → 植え付け → 日記 → 関連する料理 |
| 栽培記録詳細 | 作物情報 → 品種情報（variety_id があれば） → 場所情報 |
| 日記詳細 | 作物 → 品種 → 場所 → 植え付け → 収穫 |
| タスク詳細 | 作物 → 品種 → 場所 → 植え付け |
| 料理詳細 | 関連する作物 → 関連する品種 → 関連する植え付け → 関連する収穫（`relations` dict経由） |

原則: 情報カード（静的参照）→ タスク（アクション）→ 関連データ（ナビゲーション）

### 作物情報カード (`_crop_info_card.html`)

植え付け詳細・収穫詳細・栽培記録詳細・品種詳細の右カラムに配置。作物の登録画像がある場合、カード本体内の右上に縮小表示（`.sidebar-card-float-img` クラス、`float: right; width: 48%; aspect-ratio: 1/1` で常に正方形を維持）。`variety_id` を渡せば作物詳細リンクの下に「品種詳細へ」リンクが表示されるが、植え付け・収穫・栽培記録の各詳細では「品種情報カード」を別途表示する方針のため `variety_id: None` を渡す。

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

植え付け詳細・収穫詳細の右カラムに配置。場所の登録画像がある場合、カード本体内の右上に縮小表示（`.sidebar-card-float-img` クラス、常に正方形を維持）。

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
| `_related_varieties_card.html` | `related_varieties` | variety_id, crop_id, crop_name, variety, icon_path, image_color | `crop_label` |
| `_related_cookings_card.html` | `related_cookings` | id, title, category, cooked_date, image_path | なし |

`_related_plantings_card.html` はオプション変数 `related_plantings_title` でヘッダーテキストを変更可能（デフォルト: 「関連する植え付け」、作物詳細では「栽培中の植え付け」）。

作物詳細・品種詳細・場所詳細では、収穫カードの後に「栽培終了した植え付け」カードを同テンプレートで再表示する（`related_plantings` 変数を `ended_plantings` に再 `{% set %}` してから再 `include`）。データは `Planting.get_ended_by_crop/get_ended_by_variety/get_ended_by_location`（`status='harvested'`、`end_date DESC` で最大5件、終了日なしは最後）。

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
| 品種詳細 | `Variety.get_adjacent(variety_id)` | 作物名順 → `created_at DESC`（Python側でインデックス検索） | 品種名（作物名） |
| 場所詳細 | `Location.get_adjacent(location_id)` | `created_at DESC` | 場所名 |
| 植え付け詳細 | `Planting.get_adjacent(id, status)` | `planted_date DESC`、同じステータス内 | 作物名（品種）- 場所名 |
| 栽培記録詳細 | `PlantingRecord.get_adjacent(record_id)` | `recorded_at DESC`、同一植え付け内 | 記録日 |
| 収穫詳細 | `Harvest.get_adjacent(harvest_id)` | `harvest_date DESC` | 収穫日 作物名 |
| 日記詳細 | `DiaryEntry.get_adjacent(diary_id)` | `entry_date DESC` | 日付 タイトル |
| タスク詳細 | `Task.get_adjacent(task_id)` | ステータス順→期限日（Python側でインデックス検索） | タイトル |
| 料理詳細 | `Cooking.get_adjacent(cooking_id)` | `cooked_date DESC` | 料理名 |
