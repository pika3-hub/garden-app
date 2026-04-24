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
- **作物管理:** 作物（トマト、なすなど）のCRUD。種類・アイコン・イメージカラー・画像・Markdownメモを持つ
- **品種管理:** 作物に紐づく品種（アイコ、桃太郎など）のCRUD。1作物：多品種の関係。アイコン・イメージカラー・画像は nullable で、未設定時は親作物から継承
- **場所管理:** 畑やプランターの場所のCRUD、画像サポート付き
- **キャンバスエディター:** バニラJSベースのビジュアル菜園レイアウトデザイナー（作物アイコンのドラッグ&ドロップ配置、背景画像選択）。植え付け登録時に見取り図配置ページへ自動遷移（スキップ可能）
- **見取り図プレビュー:** 場所詳細・植え付け詳細に読み取り専用の見取り図を表示（植え付けのハイライト・ディム対応）、場所詳細では日付スライダーで過去の配置状態を再現可能
- **栽培記録:** 作物と場所をリンクし、ステータス追跡（栽培中/栽培終了/削除済み）、タブフィルター付き一覧（`/plantings/`）、栽培観察記録の登録・管理
- **収穫記録:** 複数回の収穫を記録、収穫量・単位・メモ・画像対応、植え付けからの日数自動計算。収穫一覧・植え付け詳細の両方から「収穫を記録」可能で、新規フォームはモーダルから対象の植え付けを選択できる（種類・場所バッジフィルタ付き）
- **日記システム:** 複数エンティティ（作物、場所、植え付け、収穫）との関連付けと画像添付を持つ栽培日記。関連付けはカード型モーダルで複数選択（`entity-select-modal.js`）
- **画像サポート:** 作物、場所、日記、収穫記録の画像アップロード・管理（最大16MB）、一覧画面はサムネイル（800×600px JPEG）を使用して高速化
- **スライドショー:** 栽培記録一覧（植え付け詳細内）・収穫記録一覧の画像をフルスクリーンで閲覧（`slideshow.js` + `slideshow.css`）、日付・日数・キャプション表示、キーボード操作対応
- **検索とフィルター:** 一覧画面（作物・場所・植え付け・収穫）はクライアントサイドの種類バッジフィルター（`badge-filter.js`）、日記・タスクはサーバーサイドのキーワード検索・日付フィルター
- **ダッシュボード:** 統計情報と最近のアクティビティ概要、画像カルーセル（全データ種別の最近の画像をランダム再生、Bootstrap 5 Carousel使用）
- **カレンダービュー:** 月別カレンダーで作物・場所・日記・植え付け・収穫・タスクをアイコン表示、詳細ページへのリンク
- **タスク管理:** 栽培作業タスクのCRUD、ステータス管理（未着手/進行中/完了）、期限日設定、作物・場所・栽培記録との関連付け。関連付けはカード型モーダルで複数選択（`entity-select-modal.js`）
- **詳細画面ナビゲーション:** 全詳細画面（作物・場所・植え付け・栽培記録・収穫・日記・タスク）で前後データへの移動ボタンを表示。共通部品 `_detail_nav.html` を使用し、各モデルの `get_adjacent()` メソッドで一覧の表示順に基づく前後を取得
- **補足情報:** 作物・場所・日記・タスク・収穫の詳細画面に補足テキスト、追加画像、外部URL、YouTube動画埋め込みを複数添付可能。共通テンプレート `_supplements_section.html` + `supplements` テーブルで管理
- **写真プール:** モバイルで撮影した複数写真を先に一括アップロードし、後から各写真を選んで日記・収穫・栽培記録・作物・場所・補足情報の登録/編集画面へ送り込める機能（`/photo_pool/`）。プール写真は `uploads/photo_pool/` に独立保存し、登録時に対象エンティティのフォルダへコピー（使い回し可）。使用回数は `photo_pool_usages` 中間テーブルで追跡。各登録/編集画面の画像フィールドからは「写真プールから選択」ボタンで共通モーダル（`_photo_pool_picker_modal.html`）を開いて選択可能（ローカルファイル選択と排他UI、使用状況フィルター付き）

---

## ディレクトリ別ガイドへの目次

このルート CLAUDE.md にはコアの情報のみを載せている。機能単位の詳しい規約は以下のネストされた CLAUDE.md を参照（Claude Code は該当ディレクトリを触るときに自動で読み込む）。

| ファイル | カバー範囲 |
|---------|-----------|
| `app/models/CLAUDE.md` | データベーススキーマ、テーブル/VIEW定義、モデル層の実装規約、SQLite Row の重複カラム名問題 |
| `app/routes/CLAUDE.md` | URL設計、Blueprint規約、新機能追加チェックリスト |
| `app/templates/CLAUDE.md` | `base.html` ブロック、作物名の表記ルール、画像サムネイル、詳細画面カード/サイドバー、一覧のバッジフィルター・グルーピング、エンティティ選択モーダル、スライドショー、ダッシュボードカルーセル、補足情報 |
| `app/static/js/CLAUDE.md` | 見取り図機能（エディター・プレビュー・フルスクリーン・800×800px座標系）、植え付け登録フロー |

---

## プロジェクト構造

```
garden-app/
├── app/                      # メインアプリケーションパッケージ
│   ├── __init__.py          # Flaskファクトリパターン
│   ├── config.py            # 環境ベース設定
│   ├── database.py          # SQLite接続管理
│   ├── schema.sql           # 初期データベーススキーマ
│   ├── models/              # データモデル（静的メソッドパターン）→ CLAUDE.md
│   │   ├── crop.py          # 作物モデル（crops テーブル）
│   │   ├── variety.py       # 品種モデル（varieties テーブル、crops に 1:多）
│   │   ├── location.py
│   │   ├── planting.py      # 植え付けモデル（plantings テーブル、variety_id nullable）
│   │   ├── diary.py
│   │   ├── harvest.py       # 収穫記録モデル
│   │   ├── calendar.py      # カレンダーデータ取得モデル
│   │   ├── task.py          # タスクモデル
│   │   ├── planting_record.py # 栽培記録モデル（planting_records テーブル）
│   │   └── supplement.py    # 補足情報モデル（supplements テーブル）+ YouTube ID抽出
│   ├── routes/              # Flask ブループリント → CLAUDE.md
│   │   ├── crop_routes.py
│   │   ├── variety_routes.py       # Blueprint名: varieties（品種CRUD）
│   │   ├── location_routes.py
│   │   ├── diary_routes.py
│   │   ├── harvest_routes.py
│   │   ├── calendar_routes.py
│   │   ├── task_routes.py
│   │   ├── planting_routes.py       # Blueprint名: plantings
│   │   └── supplement_routes.py    # Blueprint名: supplements（補足情報CRUD）
│   ├── utils/               # ユーティリティ
│   │   ├── upload.py        # 画像アップロードヘルパー（サムネイル自動生成含む）
│   │   ├── migration.py     # マイグレーションユーティリティ
│   │   ├── migrate_crops_split.py  # 作物/品種分割の1回限り移行スクリプト
│   │   ├── generate_thumbnails.py  # 既存画像の一括サムネイル生成スクリプト
│   │   ├── split_sprite.py  # 作物アイコンスプライトシート分割ユーティリティ
│   │   └── trim_icons.py    # アイコン余白トリムユーティリティ
│   ├── migrations/          # データベースマイグレーション（増分SQL）
│   ├── templates/           # Jinja2 テンプレート → CLAUDE.md
│   │   ├── base.html        # ナビバー付きベースレイアウト
│   │   ├── _macros.html     # Jinja2マクロ（crop_label等）
│   │   ├── _detail_nav.html # 詳細画面の前後ナビゲーション共通部品
│   │   ├── _crop_info_card.html    # 作物情報サイドバーカード
│   │   ├── _location_info_card.html # 場所情報サイドバーカード
│   │   ├── _tasks_card.html        # タスク一覧サイドバーカード
│   │   ├── _related_plantings_card.html  # 関連する植え付けカード
│   │   ├── _related_harvests_card.html   # 関連する収穫カード
│   │   ├── _related_diaries_card.html    # 関連する日記カード
│   │   ├── _related_crops_card.html      # 関連する作物カード
│   │   ├── _related_locations_card.html  # 関連する場所カード
│   │   ├── _crop_select_multi_modal.html     # 作物選択モーダル（複数選択、日記・タスク用）
│   │   ├── _location_select_multi_modal.html # 場所選択モーダル（複数選択、日記・タスク用）
│   │   ├── _planting_select_multi_modal.html # 植え付け選択モーダル（複数選択、日記・タスク用）
│   │   ├── _harvest_select_multi_modal.html  # 収穫選択モーダル（複数選択、日記用）
│   │   ├── _supplements_section.html    # 補足情報セクション共通部品
│   │   ├── index.html       # ダッシュボード
│   │   ├── crops/           # 作物テンプレート
│   │   ├── varieties/       # 品種テンプレート（list/detail/form）
│   │   ├── locations/       # 場所テンプレート（canvas.html, _canvas_preview.html）
│   │   ├── diary/           # 日記テンプレート
│   │   ├── harvests/        # 収穫記録テンプレート
│   │   ├── plantings/       # 栽培記録テンプレート（list/detail/record_detail/form/place）
│   │   ├── calendar/        # カレンダーテンプレート
│   │   └── tasks/           # タスクテンプレート
│   └── static/              # 静的アセット
│       ├── css/             # Bootstrap カスタマイズ
│       ├── js/              # canvas-editor.js, canvas-placement.js, canvas-preview.js, canvas-history.js, slideshow.js, badge-filter.js, entity-select-modal.js, ユーティリティ → CLAUDE.md
│       ├── images/          # UIアイコン・静的画像
│       │   ├── location_bg_images/  # 見取り図の背景画像（手動配置）
│       │   │   ├── bg_image_default.png  # デフォルト背景
│       │   │   └── bg_image_001.png〜    # 追加背景画像
│       │   └── crop_icons/  # 作物アイコン（icon_{row:02d}_{col:02d}.png）
│       └── uploads/         # ユーザーアップロード画像（crops/, varieties/, locations/, diary/, harvests/, supplements/）
│                            # 各フォルダに thumbs/ サブフォルダ（サムネイル置き場）
├── instance/                # Flask インスタンスフォルダ（garden.db）
├── run.py                   # アプリケーション起動スクリプト
├── test_data.py             # テストデータ投入スクリプト
└── pyproject.toml           # プロジェクトメタデータ（uvパッケージマネージャー）
```

## 開発サーバー起動

```bash
uv run python run.py
```

---

## 作物と品種のデータモデル

作物（`crops`）と品種（`varieties`）は 1:多 の別テーブルに分離されている。詳しいスキーマ定義は `app/models/CLAUDE.md` を参照。

この関係はアプリ全体のクエリ・継承ロジック・表記ルールに影響するため、ルート CLAUDE.md で概要を維持する。

### 責務分担

| テーブル | カラム | 備考 |
|---------|--------|------|
| `crops` | `name`, `crop_type`, `notes`, `icon_path`, `image_color`, `image_path` | 作物マスタ。`notes` は Markdown 統合形式（植え付け時期・収穫時期・特性・メモ）|
| `varieties` | `crop_id`, `name`, `notes`, `icon_path`, `image_color`, `image_path` | 品種マスタ。外観3カラムは **nullable** で、未設定時は親作物から継承 |
| `plantings` | `crop_id`, `variety_id` | `variety_id` は **nullable**（品種を指定せず作物単位で植えた場合 NULL）|

### VIEW `crop_variety_view`

植え付け・収穫・カレンダーなど「作物と品種を合わせて表示したい」クエリ向けに、次の VIEW を提供する。

```sql
CREATE VIEW crop_variety_view AS
-- 品種あり
SELECT c.id AS crop_id, v.id AS variety_id,
       c.name AS crop_name, c.crop_type, v.name AS variety,
       COALESCE(v.notes, c.notes)             AS notes,
       COALESCE(v.icon_path, c.icon_path)     AS icon_path,
       COALESCE(v.image_color, c.image_color) AS image_color,
       COALESCE(v.image_path, c.image_path)   AS image_path
FROM crops c JOIN varieties v ON v.crop_id = c.id
UNION ALL
-- 品種なし（variety_id が NULL の行を必ず返す）
SELECT c.id AS crop_id, NULL AS variety_id,
       c.name AS crop_name, c.crop_type, NULL AS variety,
       c.notes, c.icon_path, c.image_color, c.image_path
FROM crops c;
```

- **UNION ALL の理由**: `LEFT JOIN` だと「品種を持つ作物」の variety_id=NULL 行が返らず、`variety_id IS NULL` な植え付けと JOIN できない（IFNULL マッチ失敗）
- COALESCE により品種の外観が未設定なら親作物の値にフォールバック（継承ロジックはVIEW内で完結）

### JOIN パターン（`_CV_JOIN` 定数）

植え付け（`plantings` エイリアス `lc`）や収穫（`h`）を VIEW と結合するときは以下の定数を使う。`app/models/planting.py` 等で `_CV_JOIN` として定義済み：

```python
_CV_JOIN = (
    'JOIN crop_variety_view cv ON cv.crop_id = lc.crop_id '
    'AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)'
)
```

- `IFNULL(..., -1)` で NULL を仮値に置換してマッチさせる（SQLite は `NULL = NULL` が false のため）
- `cv.*` を使ってはならない（SQLite Row の重複カラム名問題。詳細は `app/models/CLAUDE.md`）。必要カラムは `cv.crop_name, cv.variety, cv.icon_path, cv.image_color` のように明示する

### 継承ロジックの実装箇所

| 箇所 | 実装 |
|------|------|
| VIEW経由（植え付け・収穫・カレンダー等） | `crop_variety_view` の `COALESCE` で自動継承 |
| 品種画面（一覧・詳細） | `variety_routes.py` の `_apply_inheritance(variety)` が `effective_icon_path` / `effective_image_color` / `effective_image_path` を付与 |
| テンプレート側 | `effective_*` または VIEW 由来のカラムをそのまま表示 |

### 補足情報（supplements）の紐付け

- **作物のみの情報**（種類全体に関する補足） → `entity_type='crop', entity_id=crop.id`
- **品種固有の情報**（品種ごとの補足） → `entity_type='variety', entity_id=variety.id`

旧データ移行時は「旧 crops レコードに variety があったか否か」で自動振り分けされている。

---

## ドキュメント更新チェックリスト

モデルやスキーマを変更した際は必ず以下も更新すること：

- **`app/models/CLAUDE.md`**: テーブル定義・カラム定義の追加・変更・削除を反映
- **`CLAUDE.md`（このファイル）**: プロジェクト構造・機能概要・データモデル（作物/品種の責務分担やVIEW）など関連セクションを更新
- **`app/routes/CLAUDE.md` / `app/templates/CLAUDE.md` / `app/static/js/CLAUDE.md`**: 該当領域の規約変更を反映
- **`README.md`**: ユーザー向けの機能説明・プロジェクト構造を更新
