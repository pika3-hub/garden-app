# ルート開発ガイド

Flask Blueprint ベースのルーティング規約と URL 設計。

## URL設計

| 機能 | Blueprint | 一覧 | 詳細 | 新規 | 編集 |
|-----|-----------|------|------|------|------|
| 作物 | crops | /crops/ | /crops/{id} | /crops/new | /crops/{id}/edit |
| 品種 | varieties | /varieties/ | /varieties/{id} | /varieties/new（`?crop_id={id}` でプリセレクト可） | /varieties/{id}/edit |
| 場所 | locations | /locations/ | /locations/{id} | /locations/new | /locations/{id}/edit |
| 日記 | diary | /diary/ | /diary/{id} | /diary/new | /diary/{id}/edit |
| 収穫 | harvests | /harvests/ | /harvests/{id} | /harvests/new?location_crop_id={id}（任意） | /harvests/{id}/edit |
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
| `plantings.end_cultivation` | POST `/plantings/<location_crop_id>/end` | 栽培終了（植え付け詳細から） |
| `plantings.delete` | POST `/plantings/record/<record_id>/delete` | 栽培記録削除 |

`url_for` 例:
- `url_for('plantings.index')` → `/plantings/`
- `url_for('plantings.detail', location_crop_id=1)` → `/plantings/1`
- `url_for('plantings.place', location_crop_id=1)` → `/plantings/1/place`
- `url_for('plantings.record_detail', record_id=1)` → `/plantings/record/1`
- `url_for('plantings.edit', record_id=1)` → `/plantings/record/1/edit`
- `url_for('plantings.end_cultivation', location_crop_id=1)` → `/plantings/1/end`（POST）
- `url_for('diary.detail', diary_id=1)` → `/diary/1`

## Blueprint規約

- Blueprint名はファイル名から `_routes` を除いた形（例: `crop_routes.py` → Blueprint名 `crops`）
- 例外: `variety_routes.py` → `varieties`、`planting_routes.py` → `plantings`、`supplement_routes.py` → `supplements`（命名ルール「複数形に統一」）
- テンプレートフォルダは Blueprint 名と揃える（`app/templates/{blueprint}/`）

## 新機能追加チェックリスト

1. **モデル作成**: `app/models/{feature}.py` - 静的メソッドパターン、`get_db()`使用
2. **ルート作成**: `app/routes/{feature}_routes.py` - Blueprint名は `{feature}`
3. **Blueprint登録**: `app/__init__.py` の `create_app()` 内に追加
4. **テンプレート**: `app/templates/{feature}/` フォルダ作成（Blueprint名に合わせる）
5. **CSS（任意）**: `app/static/css/{feature}.css`
6. **JS（任意）**: `app/static/js/{feature}.js`
7. **ナビ追加**: `app/templates/base.html` のナビゲーションに追加

## 関連ドキュメント

- テンプレート規約（詳細画面カード・サイドバー・一覧フィルター等）: `app/templates/CLAUDE.md`
- モデル・スキーマ: `app/models/CLAUDE.md`
- フロントエンドJS（見取り図・モーダル等）: `app/static/js/CLAUDE.md`
