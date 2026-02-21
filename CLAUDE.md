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
- **キャンバスエディター:** Fabric.jsを使用したビジュアル菜園レイアウトデザイナー（作物、図形、テキストのドラッグ&ドロップ）
- **栽培記録:** 作物と場所をリンクし、ステータス追跡（栽培中/栽培終了/削除済み）、タブフィルター付き一覧（`/plantings/`）、栽培観察記録の登録・管理
- **収穫記録:** 複数回の収穫を記録、収穫量・単位・メモ・画像対応、植え付けからの日数自動計算
- **日記システム:** 複数エンティティ（作物、場所、植え付け、収穫）との関連付けと画像添付を持つ栽培日記
- **画像サポート:** 作物、場所、日記、収穫記録の画像アップロード・管理（最大16MB）
- **検索とフィルター:** エンティティ全体でのキーワード検索、日記・収穫記録の日付範囲フィルタリング
- **ダッシュボード:** 統計情報と最近のアクティビティ概要
- **カレンダービュー:** 月別カレンダーで作物・場所・日記・植え付け・収穫・タスクをアイコン表示、詳細ページへのリンク
- **タスク管理:** 栽培作業タスクのCRUD、ステータス管理（未着手/進行中/完了）、期限日設定、作物・場所・栽培記録との関連付け

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
│   │   ├── upload.py        # 画像アップロードヘルパー
│   │   └── migration.py     # マイグレーションユーティリティ
│   ├── migrations/          # データベースマイグレーション（増分SQL）
│   ├── templates/           # Jinja2 テンプレート
│   │   ├── base.html        # ナビバー付きベースレイアウト
│   │   ├── index.html       # ダッシュボード
│   │   ├── crops/           # 作物テンプレート
│   │   ├── locations/       # 場所テンプレート（+ canvas.html）
│   │   ├── diary/           # 日記テンプレート
│   │   ├── harvests/        # 収穫記録テンプレート
│   │   ├── plantings/       # 栽培記録テンプレート（list/detail/record_detail/form）
│   │   ├── calendar/        # カレンダーテンプレート
│   │   └── tasks/           # タスクテンプレート
│   └── static/              # 静的アセット
│       ├── css/             # Bootstrap カスタマイズ
│       ├── js/              # キャンバスエディター、ユーティリティ
│       └── uploads/         # ユーザー画像（crops/, locations/, diary/, harvests/）
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
- Fabric.js（キャンバス機能のみ）

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

**`plantings` Blueprint のエンドポイント一覧（`growth_record_routes.py`）:**

> ⚠️ ルートファイル名は `planting_routes.py`、Blueprint名は `plantings`。
> `url_for` では必ず `plantings.xxx` を使うこと（`growth_records.xxx` は存在しない）。

画面上の用語は URL パスで統一する:
- `/plantings/` 直下 → **「植え付け一覧」「植え付け詳細」**
- `/plantings/record` 直下 → **「栽培記録詳細」「栽培記録編集」**

| エンドポイント | URL | 画面名 |
|--------------|-----|-------|
| `plantings.index` | `/plantings/` | 植え付け一覧 |
| `plantings.detail` | `/plantings/<location_crop_id>` | 植え付け詳細（栽培記録一覧を含む） |
| `plantings.new` | `/plantings/new/<location_crop_id>` | 栽培記録登録 |
| `plantings.record_detail` | `/plantings/record/<record_id>` | 栽培記録詳細 |
| `plantings.edit` | `/plantings/record/<record_id>/edit` | 栽培記録編集 |
| `plantings.delete` | POST `/plantings/record/<record_id>/delete` | 栽培記録削除 |

`url_for` 例:
- `url_for('plantings.index')` → `/plantings/`
- `url_for('plantings.detail', location_crop_id=1)` → `/plantings/1`
- `url_for('plantings.record_detail', record_id=1)` → `/plantings/record/1`
- `url_for('plantings.edit', record_id=1)` → `/plantings/record/1/edit`
- `url_for('diary.detail', diary_id=1)` → `/diary/1`

### 新機能追加チェックリスト

1. **モデル作成**: `app/models/{feature}.py` - 静的メソッドパターン、`get_db()`使用
2. **ルート作成**: `app/routes/{feature}_routes.py` - Blueprint名は原則 `{feature}`
   - 例外: `growth_record_routes.py` の Blueprint名は `plantings`（歴史的経緯）
3. **Blueprint登録**: `app/__init__.py` の `create_app()` 内に追加
4. **テンプレート**: `app/templates/{feature}/` フォルダ作成（Blueprint名に合わせる）
5. **CSS（任意）**: `app/static/css/{feature}.css`
6. **JS（任意）**: `app/static/js/{feature}.js`
7. **ナビ追加**: `app/templates/base.html` のナビゲーションに追加

> ⚠️ `url_for` のエンドポイント名はルートファイル名でなく **Blueprint名** に依存する。
> 実装前に `app/routes/{feature}_routes.py` の `bp = Blueprint('xxx', ...)` を必ず確認すること。