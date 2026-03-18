# CLAUDE.md - 家庭菜園管理アプリ AI アシスタントガイド

このドキュメントは、このコードベースで作業するAIアシスタント（Claudeなど）のための包括的なガイドです。アーキテクチャ、規約、ワークフロー、ベストプラクティスについて説明します。

## プロジェクト概要

**名称:** 家庭菜園管理アプリ
**タイプ:** Flask ベースの Web アプリケーション
**言語:** Python 3.12、日本語UI
**データベース:** SQLite
**目的:** ビジュアルキャンバスレイアウト、日記エントリ、作物と場所の関係を使用した家庭菜園の栽培管理
**パッケージ管理:** uv

### 主な機能
- **作物管理:** 作物の種類、品種、特徴のCRUD操作
- **場所管理:** 畑やプランターの場所のCRUD、画像サポート付き
- **キャンバスエディター:** バニラJSベースのビジュアル菜園レイアウトデザイナー（作物アイコンのドラッグ&ドロップ配置、背景画像選択）。植え付け登録時に見取り図配置ページへ自動遷移（スキップ可能）
- **見取り図プレビュー:** 場所詳細・植え付け詳細に読み取り専用の見取り図を表示（植え付けのハイライト・ディム対応）、場所詳細では日付スライダーで過去の配置状態を再現可能
- **栽培記録:** 作物と場所をリンクし、ステータス追跡（栽培中/栽培終了/削除済み）、タブフィルター付き一覧（`/plantings/`）、栽培観察記録の登録・管理
- **収穫記録:** 複数回の収穫を記録、収穫量・単位・メモ・画像対応、植え付けからの日数自動計算
- **日記システム:** 複数エンティティ（作物、場所、植え付け、収穫）との関連付けと画像添付を持つ栽培日記
- **画像サポート:** 作物、場所、日記、収穫記録の画像アップロード・管理（最大16MB）、一覧画面はサムネイル（800×600px JPEG）を使用して高速化
- **スライドショー:** 栽培記録一覧（植え付け詳細内）・収穫記録一覧の画像をフルスクリーンで閲覧（`slideshow.js` + `slideshow.css`）、日付・日数・キャプション表示、キーボード操作対応
- **検索とフィルター:** エンティティ全体でのキーワード検索、日記・収穫記録の日付範囲フィルタリング
- **ダッシュボード:** 統計情報と最近のアクティビティ概要
- **カレンダービュー:** 月別カレンダーで作物・場所・日記・植え付け・収穫・タスクをアイコン表示、詳細ページへのリンク
- **タスク管理:** 栽培作業タスクのCRUD、ステータス管理（未着手/進行中/完了）、期限日設定、作物・場所・栽培記録との関連付け
- **詳細画面ナビゲーション:** 全詳細画面（作物・場所・植え付け・栽培記録・収穫・日記・タスク）で前後データへの移動ボタンを表示。共通部品 `_detail_nav.html` を使用し、各モデルの `get_adjacent()` メソッドで一覧の表示順に基づく前後を取得

---

## クイックリファレンス

### プロジェクト構造
```
garden-app/
├── app/                      # メインアプリケーションパッケージ
│   ├── __init__.py          # Flaskファクトリパターン
│   ├── config.py            # 環境ベース設定
│   ├── database.py          # SQLite接続管理
│   ├── schema.sql           # 初期データベーススキーマ
│   ├── models/              # データモデル（静的メソッドパターン）
│   │   ├── crop.py
│   │   ├── location.py
│   │   ├── planting.py      # 植え付けモデル（plantings テーブル）
│   │   ├── diary.py
│   │   ├── harvest.py       # 収穫記録モデル
│   │   ├── calendar.py      # カレンダーデータ取得モデル
│   │   ├── task.py          # タスクモデル
│   │   └── planting_record.py # 栽培記録モデル（planting_records テーブル）
│   ├── routes/              # Flask ブループリント
│   │   ├── crop_routes.py
│   │   ├── location_routes.py
│   │   ├── diary_routes.py
│   │   ├── harvest_routes.py
│   │   ├── calendar_routes.py
│   │   ├── task_routes.py
│   │   └── planting_routes.py       # Blueprint名: plantings
│   ├── utils/               # ユーティリティ
│   │   ├── upload.py        # 画像アップロードヘルパー（サムネイル自動生成含む）
│   │   ├── migration.py     # マイグレーションユーティリティ
│   │   ├── generate_thumbnails.py  # 既存画像の一括サムネイル生成スクリプト
│   │   ├── split_sprite.py  # 作物アイコンスプライトシート分割ユーティリティ
│   │   └── trim_icons.py    # アイコン余白トリムユーティリティ
│   ├── migrations/          # データベースマイグレーション（増分SQL）
│   ├── templates/           # Jinja2 テンプレート
│   │   ├── base.html        # ナビバー付きベースレイアウト
│   │   ├── _detail_nav.html # 詳細画面の前後ナビゲーション共通部品
│   │   ├── index.html       # ダッシュボード
│   │   ├── crops/           # 作物テンプレート
│   │   ├── locations/       # 場所テンプレート（canvas.html, _canvas_preview.html）
│   │   ├── diary/           # 日記テンプレート
│   │   ├── harvests/        # 収穫記録テンプレート
│   │   ├── plantings/       # 栽培記録テンプレート（list/detail/record_detail/form/place）
│   │   ├── calendar/        # カレンダーテンプレート
│   │   └── tasks/           # タスクテンプレート
│   └── static/              # 静的アセット
│       ├── css/             # Bootstrap カスタマイズ
│       ├── js/              # canvas-editor.js, canvas-placement.js, canvas-preview.js, canvas-history.js, slideshow.js, ユーティリティ
│       ├── images/          # UIアイコン・静的画像
│       │   ├── location_bg_images/  # 見取り図の背景画像（手動配置）
│       │   │   ├── bg_image_default.png  # デフォルト背景
│       │   │   └── bg_image_001.png〜    # 追加背景画像
│       │   └── crop_icons/  # 作物アイコン（icon_{row:02d}_{col:02d}.png）
│       └── uploads/         # ユーザーアップロード画像（crops/, locations/, diary/, harvests/）
│                            # 各フォルダに thumbs/ サブフォルダ（サムネイル置き場）
├── instance/                # Flask インスタンスフォルダ（garden.db）
├── run.py                   # アプリケーション起動スクリプト
├── test_data.py             # テストデータ投入スクリプト
└── pyproject.toml           # プロジェクトメタデータ（uvパッケージマネージャー）
```

### 開発サーバー起動

```bash
uv run python run.py
```

### テンプレート構造

**base.html のブロック:**
- `{% block title %}` - ページタイトル
- `{% block extra_css %}` - 追加CSS読み込み
- `{% block content %}` - メインコンテンツ
- `{% block extra_js %}` - 追加JS読み込み

**使用ライブラリ:**
- Bootstrap 5.3（CDN）
- Bootstrap Icons（CDN）
- Pillow（サムネイル生成、Python依存）
- ※ Fabric.js は削除済み（見取り図はバニラJSで実装）

### 画像サムネイル

一覧画面の表示高速化のため、アップロード時に自動でサムネイルを生成する。

- **保存先**: `uploads/{folder}/thumbs/{basename}.jpg`（拡張子は常に .jpg）
- **サイズ**: 最大800×600px、JPEG品質80、EXIF回転補正済み
- **Jinja2フィルター**: `{{ image_path | thumb_path }}` でサムネイルパスに変換
- **onerrorフォールバック**: サムネイルがない場合はオリジナルにフォールバック
- **GIF**: サムネイル非対応のためスキップ
- **既存画像の一括変換**: `uv run python app/utils/generate_thumbnails.py`

### スライドショー機能

画像付き一覧画面でフルスクリーンのスライドショー表示を提供する汎用コンポーネント。

#### 使用箇所

| 画面 | テンプレート | キャプション内容 |
|------|------------|----------------|
| 栽培記録一覧（植え付け詳細内） | `plantings/detail.html` | メモ（80文字で切り詰め） |
| 収穫記録一覧 | `harvests/list.html` | 作物名（品種名）+ 収穫量 |

#### テンプレートでの使い方

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

#### data属性

| 属性 | 必須 | 説明 |
|-----|------|------|
| `class="slideshow-target"` | ○ | JS収集対象 + クリックで起動 |
| `data-slideshow-date` | - | フッターに表示する日付 |
| `data-slideshow-days` | - | 「植え付けから N日目」として表示 |
| `data-slideshow-caption` | - | フッターに表示するキャプションテキスト |

### 詳細画面ナビゲーション

全詳細画面で前後データへの移動ボタンを表示する共通機能。一覧に戻らずにデータ間を移動できる。

#### 共通部品

`app/templates/_detail_nav.html` — 前後ナビボタンを描画する include 用テンプレート。

#### テンプレートでの使い方

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

#### 各画面の `get_adjacent()` 実装

| 画面 | モデルメソッド | 表示順 | ラベル |
|------|-------------|--------|-------|
| 作物詳細 | `Crop.get_adjacent(crop_id)` | `created_at DESC` | 作物名（品種） |
| 場所詳細 | `Location.get_adjacent(location_id)` | `created_at DESC` | 場所名 |
| 植え付け詳細 | `Planting.get_adjacent(id, status)` | `planted_date DESC`、同じステータス内 | 作物名（品種）- 場所名 |
| 栽培記録詳細 | `PlantingRecord.get_adjacent(record_id)` | `recorded_at DESC`、同一植え付け内 | 記録日 |
| 収穫詳細 | `Harvest.get_adjacent(harvest_id)` | `harvest_date DESC` | 収穫日 作物名 |
| 日記詳細 | `DiaryEntry.get_adjacent(diary_id)` | `entry_date DESC` | 日付 タイトル |
| タスク詳細 | `Task.get_adjacent(task_id)` | ステータス順→期限日（Python側でインデックス検索） | タイトル |

### 見取り図機能

#### アーキテクチャ

| コンポーネント | ファイル | 役割 |
|------------|--------|------|
| エディター画面 | `locations/canvas.html` + `canvas-editor.js` | 作物配置の編集（800×800px） |
| 植え付け配置ページ | `plantings/place.html` + `canvas-placement.js` | 植え付け登録後の見取り図配置（エディターを再利用） |
| プレビューコンポーネント | `locations/_canvas_preview.html` + `canvas-preview.js` | 読み取り専用の表示（400×400px） |
| 履歴スライダー | `canvas-history.js` | 場所詳細で日付スライダーによる過去配置の再現 |
| CSSスタイル | `static/css/canvas.css` | エディター・プレビュー共通スタイル |

#### 背景画像

- **保存場所**: `app/static/images/location_bg_images/`（静的ファイル、アップロード不可）
- **追加方法**: 画像ファイルを直接このフォルダに配置する（`bg_image_001.png` などの連番命名）
- **対応形式**: `.png`, `.jpg`, `.jpeg`, `.webp`
- **選択UI**: `Location.get_bg_images()` でファイル一覧を取得し、エディター画面でセレクト
- **デフォルト**: `bg_image_default.png`

#### 作物アイコン

- **保存場所**: `app/static/images/crop_icons/`
- **命名規則**: `icon_{row:02d}_{col:02d}.png`（例: `icon_01_03.png`）
- **生成元**: スプライトシートを `split_sprite.py` で分割（12列×7行 = 84アイコン）

#### データ形式（version 2.0 JSON）

```json
{
  "version": "2.0",
  "placements": [
    {
      "locationCropId": 1,
      "cropId": 5,
      "x": 350,
      "y": 420,
      "iconPath": "icon_01_03.png",
      "imageColor": "#4CAF50",
      "cropName": "トマト",
      "variety": "ミニトマト"
    }
  ]
}
```

- `canvas_data` カラム（`locations` テーブル、TEXT型）に JSON 文字列として保存
- 旧形式（Fabric.js の version 1.x）は無視してプレビューを非表示にする

#### APIエンドポイント

| エンドポイント | メソッド | 説明 |
|-------------|--------|------|
| `/locations/<id>/canvas` | GET | エディター画面 |
| `/locations/<id>/canvas/data` | GET | 配置データ取得（JSON） |
| `/locations/<id>/canvas/save` | POST | 配置データ保存 |
| `/locations/<id>/canvas/history/range` | GET | 見取り図に変化がある日付一覧（`{dates: [...]}` 形式） |
| `/locations/<id>/canvas/history?date=YYYY-MM-DD` | GET | 指定日付の配置データ（version 2.0 JSON） |

#### プレビューコンポーネントの使い方

```html
{% include 'locations/_canvas_preview.html' %}
```

テンプレートに渡す変数:
- `location` — 場所オブジェクト（`location['id']`, `location['bg_image']` を使用）
- `preview_highlight_id`（任意）— ハイライトする `location_crop_id`

`CanvasPreview` クラスのAPI:
- `updateData(data)` — 表示内容をクリアして新しいデータで再描画（履歴スライダー等で使用）
- `data-manual-init="true"` 属性 — 自動初期化をスキップ（JS側で手動制御する場合に指定）

#### 履歴スライダー

場所詳細ページの見取り図カードに統合。`canvas-history.js` が制御。
- 植え付け日・栽培終了日など、見取り図に変化がある日付のみスライド可能
- 左端: 最初の植え付け日の1日前（何もない状態）、右端: 今日（`locations.canvas_data` で表示）
- 位置情報の取得元: active作物は `locations.canvas_data`（複数配置対応）、harvested作物は `plantings.canvas_snapshot`
- 位置情報を持たない植え付けのみの日付はスライダーから除外

#### レスポンシブ対応（重要）

**座標系は常に800×800px固定。これを変更してはならない。**

作物の配置座標（`x`, `y`）はすべて800×800pxキャンバス上の絶対ピクセル値として保存される。モバイル等で表示領域が狭い場合は、キャンバス要素のサイズは800×800を維持したまま `transform: scale()` で縮小表示する。`width: 100%` 等でキャンバス自体を縮小すると、`overflow: hidden` により端の作物がクリップされて見えなくなる。

**エディター（`canvas-editor.js`）のスケーリング:**
- `ResizeObserver` でラッパー幅を監視し、800px未満なら `transform: scale(factor)` を適用
- `transform-origin: top left` で左上基点に縮小
- ラッパーの高さを縮小後のサイズに合わせて設定（空白防止）
- ドラッグ・ドロップの座標は `_toCanvasCoords()` でスケール補正が必要（`clientX / scale`）
- 保存時の座標は常に800×800基準のまま

**プレビュー（`canvas-preview.js`）のスケーリング:**
- 400×400pxのプレビュー領域を、コンテナ幅に合わせて同様に `transform: scale()` で縮小
- `ResizeObserver` で動的に追従

**CSS上の注意点:**
- `#canvas-area` には `flex-shrink: 0` が必須。flexboxコンテナ内でデフォルトの `flex-shrink: 1` だとキャンバスが縮小され、transform と二重に縮小されてしまう
- モバイルではラッパーに `overflow: hidden`（レイアウト上800×800のままの要素をクリップ）
- モバイルではラッパーに `flex: none`（不要な余白を防ぎ、サイドバーをキャンバス直下に配置）
- モバイルではサイドバーの `overflow-y: visible`（ブラウザスクロールに委ねる）、デスクトップでは `overflow-y: auto`

### 植え付け登録フロー

植え付け登録後、見取り図配置ページへ自動遷移し、作物の配置を促す2ステップ方式。

```
植え付けフォーム（/plantings/plant/new）
  ↓ POST → DBにレコード作成（ID取得）
見取り図配置ページ（/plantings/<id>/place）
  ├─ 新規作物をサイドバーでハイライト表示（.crop-item-new）
  ├─ ドラッグ&ドロップで配置 → 保存 → 植え付け詳細へ
  └─ スキップ → 植え付け詳細へ（配置なしでもOK）
```

- **場所詳細からの植え付け:** 操作カードの「作物を植え付ける」→ `/plantings/plant/new?location_id=<id>`（場所プリセレクト済み）
- **`canvas-placement.js`:** `canvas-editor.js` の上に載せる薄いラッパー。保存後に植え付け詳細へリダイレクトする動作を追加
- **`canvas-editor.js`:** `window._canvasEditor` でインスタンスを公開、`buildSaveData()` メソッドで保存データを取得可能

### URL設計

| 機能 | Blueprint | 一覧 | 詳細 | 新規 | 編集 |
|-----|-----------|------|------|------|------|
| 作物 | crops | /crops/ | /crops/{id} | /crops/new | /crops/{id}/edit |
| 場所 | locations | /locations/ | /locations/{id} | /locations/new | /locations/{id}/edit |
| 日記 | diary | /diary/ | /diary/{id} | /diary/new | /diary/{id}/edit |
| 収穫 | harvests | /harvests/ | /harvests/{id} | /harvests/new | /harvests/{id}/edit |
| 植え付け | plantings | /plantings/?status= | /plantings/{lc_id} | - | - |
| タスク | tasks | /tasks/ | /tasks/{id} | /tasks/new | /tasks/{id}/edit |
| カレンダー | calendar | /calendar/ | - | - | - |

植え付け（plantings）は `?status=active|harvested|all` でタブフィルター。

画面上の用語は URL パスで統一する:
- `/plantings/` 直下 → **「植え付け一覧」「植え付け詳細」**
- `/plantings/record` 直下 → **「栽培記録詳細」「栽培記録編集」**

| エンドポイント | URL | 画面名 |
|--------------|-----|-------|
| `plantings.index` | `/plantings/` | 植え付け一覧 |
| `plantings.detail` | `/plantings/<location_crop_id>` | 植え付け詳細（栽培記録一覧を含む） |
| `plantings.place` | `/plantings/<location_crop_id>/place` | 見取り図配置（植え付け登録後に遷移） |
| `plantings.new` | `/plantings/new/<location_crop_id>` | 栽培記録登録 |
| `plantings.record_detail` | `/plantings/record/<record_id>` | 栽培記録詳細 |
| `plantings.edit` | `/plantings/record/<record_id>/edit` | 栽培記録編集 |
| `plantings.delete` | POST `/plantings/record/<record_id>/delete` | 栽培記録削除 |

`url_for` 例:
- `url_for('plantings.index')` → `/plantings/`
- `url_for('plantings.detail', location_crop_id=1)` → `/plantings/1`
- `url_for('plantings.place', location_crop_id=1)` → `/plantings/1/place`
- `url_for('plantings.record_detail', record_id=1)` → `/plantings/record/1`
- `url_for('plantings.edit', record_id=1)` → `/plantings/record/1/edit`
- `url_for('diary.detail', diary_id=1)` → `/diary/1`

### 新機能追加チェックリスト

1. **モデル作成**: `app/models/{feature}.py` - 静的メソッドパターン、`get_db()`使用
2. **ルート作成**: `app/routes/{feature}_routes.py` - Blueprint名は `{feature}`
3. **Blueprint登録**: `app/__init__.py` の `create_app()` 内に追加
4. **テンプレート**: `app/templates/{feature}/` フォルダ作成（Blueprint名に合わせる）
5. **CSS（任意）**: `app/static/css/{feature}.css`
6. **JS（任意）**: `app/static/js/{feature}.js`
7. **ナビ追加**: `app/templates/base.html` のナビゲーションに追加

### ドキュメント更新チェックリスト

モデルやスキーマを変更した際は必ず以下も更新すること：

- **`app/models/CLAUDE.md`**: テーブル定義・カラム定義の追加・変更・削除を反映
- **`CLAUDE.md`（このファイル）**: プロジェクト構造・機能概要・見取り図など関連セクションを更新
- **`README.md`**: ユーザー向けの機能説明・プロジェクト構造を更新