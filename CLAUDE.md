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
- **AIメモ下書き:** 作物・品種フォームの「✨ AIで下書き」から Claude API でメモの下書き（設定画面の地域・栽培環境を基準にした時期、特性、栽培のコツ）を生成し、モーダルで確認して置き換え／追記できる。「Webで調べる」（品種は既定ON）で Web 検索を併用し参考URLを付与。APIキーは `.env` の `ANTHROPIC_API_KEY`、モデルは `ANTHROPIC_MODEL`（`claude-opus-5-5` 既定 / `claude-sonnet-5-5`）。地域は設定画面（`/settings/`）で `app_settings` テーブルに保存。実装は `app/utils/ai_notes.py` + `settings_routes.py` + `_ai_notes_button.html` / `_ai_notes_modal.html` / `ai-notes.js`
- **品種管理:** 作物に紐づく品種（アイコ、桃太郎など）のCRUD。1作物：多品種の関係。アイコン・イメージカラー・画像は nullable で、未設定時は親作物から継承
- **場所管理:** 畑やプランターの場所のCRUD、画像サポート付き
- **キャンバスエディター:** バニラJSベースのビジュアル菜園レイアウトデザイナー（作物アイコンのドラッグ&ドロップ配置、背景画像選択）。植え付け登録時に見取り図配置ページへ自動遷移（スキップ可能）
- **見取り図プレビュー:** 場所詳細・植え付け詳細に読み取り専用の見取り図を表示（植え付けのハイライト・ディム対応）、場所詳細では日付スライダーで過去の配置状態を再現可能
- **栽培記録:** 作物と場所をリンクし、ステータス追跡（栽培中/栽培終了/削除済み）、タブフィルター付き一覧（`/plantings/`）、栽培観察記録の登録・管理。植え付け一覧の「栽培記録をまとめて登録」から複数の植え付けの栽培記録を一括登録も可能（`/plantings/bulk/new`）：複数の植え付けを選択→共通の記録日・既定画像を設定した上で、メモ・画像は植え付けごとに個別入力・上書き（写真プールからの選択も可）できる
- **収穫記録:** 複数回の収穫を記録、収穫量・単位・メモ・画像対応、植え付けからの日数自動計算。収穫一覧・植え付け詳細の両方から「収穫を記録」可能で、新規フォームはモーダルから対象の植え付けを選択できる（種類・場所バッジフィルタ付き）。収穫一覧の「まとめて登録」から一括登録も可能（`/harvests/bulk/new`）：複数の植え付けを選択→共通の収穫日・既定画像を設定した上で、収穫量・単位・メモ・画像は植え付けごとに個別入力・上書き（写真プールからの選択も可）できる
- **日記システム:** 複数エンティティ（作物、場所、植え付け、収穫）との関連付けと画像添付を持つ栽培日記。関連付けはカード型モーダルで複数選択（`entity-select-modal.js`）
- **画像サポート:** 作物、場所、日記、収穫記録の画像アップロード・管理（最大16MB）、一覧画面はサムネイル（800×600px JPEG）を使用して高速化
- **スライドショー:** 栽培記録一覧（植え付け詳細内）・収穫記録一覧の画像をフルスクリーンで閲覧（`slideshow.js` + `slideshow.css`）、日付・日数・キャプション表示、キーボード操作対応
- **検索とフィルター:** 一覧画面（作物・場所・植え付け・収穫）はクライアントサイドの種類バッジフィルター（`badge-filter.js`）、日記・タスクはサーバーサイドのキーワード検索・日付フィルター
- **ダッシュボード:** 統計情報と最近のアクティビティ概要、画像カルーセル（全データ種別の最近の画像をランダム再生、Bootstrap 5 Carousel使用）
- **カレンダービュー:** 月別カレンダーで作物・場所・日記・植え付け・収穫・タスクをアイコン表示、詳細ページへのリンク
- **タスク管理:** 栽培作業タスクのCRUD、ステータス管理（未着手/進行中/完了）、期限日設定、作物・場所・栽培記録との関連付け。関連付けはカード型モーダルで複数選択（`entity-select-modal.js`）
- **詳細画面ナビゲーション:** 全詳細画面（作物・場所・植え付け・栽培記録・収穫・日記・タスク）で前後データへの移動ボタンを表示。共通部品 `_detail_nav.html` を使用し、各モデルの `get_adjacent()` メソッドで一覧の表示順に基づく前後を取得
- **補足情報:** 作物・品種・場所・日記・タスク・収穫・料理の詳細画面に補足テキスト、追加画像、外部URL（OGP情報の自動取得付き）、YouTube動画埋め込みを複数添付可能。共通テンプレート `_supplements_section.html` + `supplements` テーブルで管理
- **写真プール:** モバイルで撮影した複数写真を先に一括アップロードし、後から各写真を選んで日記・収穫・栽培記録・作物・場所・補足情報の登録/編集画面へ送り込める機能（`/photo_pool/`）。プール写真は `uploads/photo_pool/` に独立保存し、登録時に対象エンティティのフォルダへコピー（使い回し可）。使用回数は `photo_pool_usages` 中間テーブルで追跡。各登録/編集画面の画像フィールドからは「写真プールから選択」ボタンで共通モーダル（`_photo_pool_picker_modal.html`）を開いて選択可能（ローカルファイル選択と排他UI、使用状況フィルター付き）
- **料理記録:** 収穫した野菜を使った料理のCRUD（`/cooking/`）。タイトル・カテゴリ・調理日（必須）・メモ・画像を記録。作物・品種・植え付け・収穫との多対多関連付け（`cooking_relations` テーブル）。補足情報対応（`entity_type='cooking'`）。メニュー順は収穫の直後

---

## ディレクトリ別ガイドへの目次

このルート CLAUDE.md にはコアの情報のみを載せている。機能単位の詳しい規約は以下のネストされた CLAUDE.md を参照（Claude Code は該当ディレクトリを触るときに自動で読み込む）。

| ファイル | カバー範囲 |
|---------|-----------|
| `app/models/CLAUDE.md` | データベーススキーマ、テーブル/VIEW定義、モデル層の実装規約、SQLite Row の重複カラム名問題 |
| `app/routes/CLAUDE.md` | URL設計、Blueprint規約、新機能追加チェックリスト |
| `app/templates/CLAUDE.md` | トピック別ガイド（`docs/frontend/*.md`）へのインデックス。詳細は `app/templates/CLAUDE.md` のガイド一覧表を参照 |
| `app/static/js/CLAUDE.md` | 見取り図機能（エディター・プレビュー・フルスクリーン・800×800px座標系）、植え付け登録フロー |

---

## プロジェクト構造

ファイル単位の網羅的な一覧はメンテナンスコストが高く陳腐化しやすいため、ここでは**ディレクトリ構成とファイル命名パターン**のみを示す。個々のファイルの正確な一覧・役割は各ディレクトリの一次情報（`app/models/CLAUDE.md` のテーブル一覧表、`app/routes/CLAUDE.md` のURL設計表、`app/templates/CLAUDE.md` のガイド一覧表）を参照すること。新機能を1つ追加すると、通常は次の5ファイルが1セットで増える: `app/models/{feature}.py`, `app/routes/{feature}_routes.py`, `app/templates/{feature}/{list,detail,form}.html`, （任意）`app/static/css/{feature}.css`, （任意）`app/static/js/{feature}.js`。

```
garden-app/
├── app/                      # メインアプリケーションパッケージ
│   ├── __init__.py          # Flaskファクトリパターン、ダッシュボード(index)ルート
│   ├── config.py            # 環境ベース設定
│   ├── database.py          # SQLite接続管理
│   ├── schema.sql           # 初期データベーススキーマ
│   ├── models/               # データモデル（静的メソッドパターン）。命名: {feature}.py = {feature}テーブルのCRUD
│   │                         # → 正確なテーブル一覧・モデル一覧は app/models/CLAUDE.md 参照
│   ├── routes/               # Flask ブループリント。命名: {feature}_routes.py、Blueprint名は原則複数形
│   │                         # → 正確なURL設計・Blueprint一覧は app/routes/CLAUDE.md 参照
│   ├── utils/                # ユーティリティ（アップロード、サムネイル生成、マイグレーション補助、アイコン加工等）
│   ├── migrations/           # データベースマイグレーション（増分SQL、連番ファイル名）
│   ├── templates/            # Jinja2 テンプレート
│   │   ├── base.html         # ナビバー付きベースレイアウト
│   │   ├── _macros.html      # Jinja2マクロ（crop_label等）
│   │   ├── _*.html           # 共通include部品（詳細ナビ・サイドバーカード・選択モーダル・補足情報等）
│   │   ├── index.html        # ダッシュボード
│   │   └── {feature}/         # 機能別テンプレート、通常 list.html/detail.html/form.html の3点セット
│   │                         # → 部品の役割・使い方は app/templates/CLAUDE.md（各 docs/frontend/*.md）参照
│   └── static/               # 静的アセット
│       ├── css/              # Bootstrap カスタマイズ（custom.css 中心、機能別CSSは任意）
│       ├── js/               # バニラJS部品（見取り図・フィルター・モーダル等）→ app/static/js/CLAUDE.md
│       ├── images/           # UIアイコン・静的画像（location_bg_images/, crop_icons/ 等）
│       └── uploads/          # ユーザーアップロード画像。機能ごとのフォルダ＋各 thumbs/ サブフォルダ
├── instance/                 # Flask インスタンスフォルダ（garden.db）
├── run.py                    # アプリケーション起動スクリプト
├── test_data.py              # テストデータ投入スクリプト
└── pyproject.toml            # プロジェクトメタデータ（uvパッケージマネージャー）
```

## 開発サーバー起動

```bash
uv run python run.py
```

## テスト

```bash
uv run pytest
```

テストは `tests/conftest.py` のフィクスチャで tmp_path 上の使い捨て DB を使う（`instance/garden.db` には触れない）。Claude API はフェイククライアントで差し替え、実 API は呼ばない。

---

## 作物と品種のデータモデル

作物（`crops`）と品種（`varieties`）は 1:多 の別テーブルに分離されている。詳しいスキーマ定義は `app/models/CLAUDE.md` を参照。

この関係はアプリ全体のクエリ・継承ロジック・表記ルールに影響するため、ルート CLAUDE.md で概要を維持する。

### 責務分担

| テーブル | カラム | 備考 |
|---------|--------|------|
| `crops` | `name`, `crop_type`, `notes`, `icon_path`, `image_color`, `image_path` | 作物マスタ。`notes` は Markdown 統合形式（植え付け時期・収穫時期・特性・メモ）|
| `varieties` | `crop_id`, `name`, `notes`, `icon_path`, `image_color`, `image_path` | 品種マスタ。外観3カラムは **nullable** で、未設定時は親作物から継承 |
| `plantings` | `crop_id`, `variety_id` | **排他関係**: 作物として植えた場合は `crop_id` のみ、品種として植えた場合は `variety_id` のみがセットされ、両方同時にセットされることはない（CHECK制約で強制） |

### plantings の排他ルール（重要）

- 「作物として植えた」→ `crop_id=X, variety_id=NULL`
- 「品種として植えた」→ `crop_id=NULL, variety_id=Y`（作物情報は品種の親を辿って解決）
- この排他性は DB 側の `CHECK` 制約 + `Planting._normalize_crop_variety()` で二重に保証
- 理由: 二重管理を排除し、「品種の親作物を変更しても植え付け側の作物ID（古いキャッシュ）がズレない」を保証する

### 品種削除時の挙動（重要）

`varieties` に対する `BEFORE DELETE` トリガー `trg_promote_variety_plantings_before_delete` により、品種単独削除時には関連する植え付けが「親作物の植え付け（品種なし）」に**昇格**する。

```sql
CREATE TRIGGER trg_promote_variety_plantings_before_delete
BEFORE DELETE ON varieties
FOR EACH ROW
BEGIN
    UPDATE plantings
       SET crop_id = OLD.crop_id, variety_id = NULL
     WHERE variety_id = OLD.id;
END;
```

- 品種単独削除 → 植え付けは親作物のものとして残る
- 作物削除（`plantings.crop_id ON DELETE CASCADE`、`varieties.crop_id ON DELETE CASCADE`、`plantings.variety_id ON DELETE CASCADE`）→ 変化した植え付けも含め連鎖削除

### VIEW `crop_variety_view`

植え付け・収穫・カレンダーなど「作物と品種を合わせて表示したい」クエリ向けに、次の VIEW を提供する。plantings の排他形式 `(crop_id, variety_id) = (X, NULL)` または `(NULL, Y)` に対応するよう **品種行は `crop_id=NULL`**、**作物行は `variety_id=NULL`** を返す。

```sql
CREATE VIEW crop_variety_view AS
-- 品種行（plantings の variety-only 行とマッチ）
SELECT NULL AS crop_id, v.id AS variety_id,
       c.id AS effective_crop_id,            -- 常に作物ID（集計用）
       c.name AS crop_name, c.crop_type, v.name AS variety,
       COALESCE(v.notes, c.notes)             AS notes,
       COALESCE(v.icon_path, c.icon_path)     AS icon_path,
       COALESCE(v.image_color, c.image_color) AS image_color,
       COALESCE(v.image_path, c.image_path)   AS image_path
FROM varieties v JOIN crops c ON v.crop_id = c.id
UNION ALL
-- 作物行（plantings の crop-only 行とマッチ）
SELECT c.id AS crop_id, NULL AS variety_id,
       c.id AS effective_crop_id,
       c.name AS crop_name, c.crop_type, NULL AS variety,
       c.notes, c.icon_path, c.image_color, c.image_path
FROM crops c;
```

- **`effective_crop_id`**: 常に作物ID（品種行なら親作物ID、作物行なら自身）。「作物Xの植え付け一覧（品種経由も含む）」は `WHERE cv.effective_crop_id = ?` で書く。品種の親作物変更が自動反映されるのはこの列のおかげ。
- **UNION ALL の理由**: 排他形式の plantings と NULL 同士でマッチさせるため、両辺を IFNULL 化した JOIN が必要。VIEW 側も正しい NULL パターンで列挙する必要がある。
- **COALESCE** により品種の外観が未設定なら親作物の値にフォールバック（継承ロジックはVIEW内で完結）

### JOIN パターン（`_CV_JOIN` 定数）

植え付け（`plantings` エイリアス `lc`）や収穫（`h`）を VIEW と結合するときは以下の定数を使う。`_CV_JOIN` は `app/models/planting.py`, `harvest.py`, `calendar.py`, `planting_record.py` の4ファイルにそれぞれ同一内容がコピーされて定義されている（共有インポートではない）。修正時は4箇所すべての同期が必要：

```python
_CV_JOIN = (
    'JOIN crop_variety_view cv ON '
    'IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1) '
    'AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)'
)
```

- **両側 IFNULL 必須**: plantings 側は `crop_id` または `variety_id` の片側が NULL のため、VIEW 側の NULL と等価比較するには両辺を `IFNULL(..., -1)` で揃える必要がある（SQLite は `NULL = NULL` が false のため）
- `cv.*` を使ってはならない（SQLite Row の重複カラム名問題。詳細は `app/models/CLAUDE.md`）。必要カラムは `cv.crop_name, cv.variety, cv.icon_path, cv.image_color, cv.effective_crop_id` のように明示する

### 「作物Xの植え付け/収穫」を取得するクエリ

品種経由の植え付けも含めて取得するには `cv.effective_crop_id` で絞り込む:

```python
# Good（品種経由も含む）
f'SELECT ... FROM plantings lc {_CV_JOIN} WHERE cv.effective_crop_id = ?'

# Bad（品種経由が漏れる）
'SELECT ... FROM plantings lc WHERE lc.crop_id = ?'
```

既に `Planting.get_by_crop()` / `Harvest.get_by_crop()` / `Harvest.search()` は `effective_crop_id` 経由に移行済み。`DiaryEntry.get_by_crop()` は未移行で、`crop_variety_view` を使わず `diary_relations` を `crop_id`/`variety_id`/`location_crop_id` の手動 OR 条件で直接クエリしている（品種経由の取得は別ロジックで担保）。

### 継承ロジックの実装箇所

| 箇所 | 実装 |
|------|------|
| VIEW経由（植え付け・収穫・カレンダー等） | `crop_variety_view` の `COALESCE` で自動継承 |
| 品種画面（一覧・詳細） | `app/models/variety.py` の `Variety.apply_inheritance(variety)` が `effective_icon_path` / `effective_image_color` / `effective_image_path` を付与（`variety_routes.py` から呼び出し） |
| テンプレート側 | `effective_*` または VIEW 由来のカラムをそのまま表示 |

### 補足情報（supplements）の紐付け

- **作物のみの情報**（種類全体に関する補足） → `entity_type='crop', entity_id=crop.id`
- **品種固有の情報**（品種ごとの補足） → `entity_type='variety', entity_id=variety.id`

旧データ移行時は「旧 crops レコードに variety があったか否か」で自動振り分けされている。

---

## DBを使った検証作業

`instance/garden.db` はユーザーの**実データ**である。マイグレーション・スキーマ変更・SQLの動作確認など、DBに対して検証を行う前に必ず [`docs/db-validation-safety.md`](docs/db-validation-safety.md) を参照すること。バックアップ手順、`WHERE`句必須ルール、テーブル再作成時の注意点などを記載している（過去のデータ消失事故を踏まえたガイドライン）。

---

## ドキュメント更新チェックリスト

モデルやスキーマを変更した際は必ず以下も更新すること：

- **`app/models/CLAUDE.md`**: テーブル定義・カラム定義の追加・変更・削除を反映
- **`CLAUDE.md`（このファイル）**: 機能概要・データモデル（作物/品種の責務分担やVIEW）など関連セクションを更新。プロジェクト構造はパターン記述のため、命名規則から外れる例外が生まれた場合のみ更新すればよい
- **`app/routes/CLAUDE.md` / `app/static/js/CLAUDE.md`**: 該当領域の規約変更を反映
- **`app/templates/CLAUDE.md` / `docs/frontend/*.md`**: 既存トピックへの追記で足りるものはそのトピックファイルを更新。新規の横断的トピックは新しいファイルを起こし、`app/templates/CLAUDE.md` のガイド一覧表に追記する（1トピック1ファイルの原則を崩さない）
- **`README.md`**: ユーザー向けの機能説明・プロジェクト構造を更新
