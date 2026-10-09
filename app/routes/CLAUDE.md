# ルート開発ガイド

Flask Blueprint ベースのルーティング規約と URL 設計。

外部 JSON API（`/api/v1/*`）はここではなく `app/api/` にあり、Web アプリとは別の `create_api_app()` にだけ登録される（仕様は `docs/api/README.md`）。画面側の作成・更新処理を変えたときは、API 側の同じ処理（`app/api/{resource}.py`）も合わせて確認する。

## URL設計

| 機能 | Blueprint | 一覧 | 詳細 | 新規 | 編集 |
|-----|-----------|------|------|------|------|
| 作物 | crops | /crops/ | /crops/{id} | /crops/new | /crops/{id}/edit |
| 品種 | varieties | /varieties/ | /varieties/{id} | /varieties/new（`?crop_id={id}` でプリセレクト可） | /varieties/{id}/edit |
| 場所 | locations | /locations/ | /locations/{id} | /locations/new | /locations/{id}/edit |
| 日記 | diary | /diary/ | /diary/{id} | /diary/new | /diary/{id}/edit |
| 収穫 | harvests | /harvests/ | /harvests/{id} | /harvests/new?location_crop_id={id}（任意）、一括登録: /harvests/bulk/new | /harvests/{id}/edit |
| 植え付け | plantings | /plantings/?status= | /plantings/{lc_id} | /plantings/plant/new | /plantings/{lc_id}/edit |
| タスク | tasks | /tasks/ | /tasks/{id} | /tasks/new | /tasks/{id}/edit |
| カレンダー | calendar | /calendar/ | - | - | - |
| 料理 | cooking | /cooking/ | /cooking/{id} | /cooking/new | /cooking/{id}/edit |
| 補足情報 | supplements | - | - | POST /supplements/{entity_type}/{entity_id}/add | POST /supplements/{id}/update |
| 写真プール | photo_pool | /photo_pool/ | - | POST /photo_pool/upload | POST /photo_pool/{id}/update |
| 設定 | settings | - | - | - | GET/POST /settings/ |

補足情報・写真プールはページ単位のCRUDではなく、他画面に埋め込まれるモーダル/フォーム部品からのPOST操作が中心（詳細は `docs/frontend/supplements.md` / `docs/frontend/images-and-photo-pool.md` を参照）。

`settings` Blueprint は設定画面に加え、作物・品種フォーム共通の AI メモ下書き API `POST /settings/ai/notes-draft`（JSON）を持つ。リクエストは `{"mode": "crop", "crop_name", "crop_type", "use_web_search"}` または `{"mode": "variety", "crop_id", "variety_name", "use_web_search"}`。成功 200 `{"ok": true, "markdown"}`、入力不備 400（地域未設定は `need_settings: true`）、生成失敗 502。Claude API 呼び出しは `app/utils/ai_notes.py` に集約している。

植え付け（plantings）は `?status=active|harvested|all` でタブフィルター。

画面上の用語は URL パスで統一する:
- `/plantings/` 直下 → **「植え付け一覧」「植え付け詳細」**
- `/plantings/record` 直下 → **「栽培記録詳細」「栽培記録編集」**

| エンドポイント | URL | 画面名 |
|--------------|-----|-------|
| `plantings.index` | `/plantings/` | 植え付け一覧 |
| `plantings.detail` | `/plantings/<location_crop_id>` | 植え付け詳細（栽培記録一覧を含む） |
| `plantings.plant_new` | GET `/plantings/plant/new` | 植え付け登録フォーム（`?location_id=`, `?crop_id=&variety_id=` でプリセレクト可） |
| `plantings.plant_create` | POST `/plantings/plant/create` | 植え付け登録処理（登録後 `plantings.place` へリダイレクト） |
| `plantings.place` | `/plantings/<location_crop_id>/place` | 見取り図配置（植え付け登録後に遷移） |
| `plantings.planting_edit` | GET `/plantings/<location_crop_id>/edit` | 植え付け編集フォーム（active時） |
| `plantings.planting_update` | POST `/plantings/<location_crop_id>/update` | 植え付け更新処理（active時） |
| `plantings.planting_edit_harvested` | GET `/plantings/<location_crop_id>/edit-harvested` | 植え付け編集フォーム（harvested時） |
| `plantings.planting_update_harvested` | POST `/plantings/<location_crop_id>/update-harvested` | 植え付け更新処理（harvested時） |
| `plantings.new` | `/plantings/new/<location_crop_id>` | 栽培記録登録 |
| `plantings.bulk_new` | GET `/plantings/bulk/new`（`?location_crop_id=` 複数指定で行入力ステップへ） | 栽培記録の一括登録（植え付け選択→行入力の2ステップ） |
| `plantings.bulk_create` | POST `/plantings/bulk/create` | 栽培記録の一括登録処理 |
| `plantings.record_detail` | `/plantings/record/<record_id>` | 栽培記録詳細 |
| `plantings.edit` | `/plantings/record/<record_id>/edit` | 栽培記録編集 |
| `plantings.end_cultivation` | POST `/plantings/<location_crop_id>/end` | 栽培終了（植え付け詳細から） |
| `plantings.delete` | POST `/plantings/record/<record_id>/delete` | 栽培記録削除 |

上記の「植え付け編集」（`planting_edit`/`planting_update`系）は植え付けそのもの（作物・品種・場所・日付等）の編集で、「栽培記録編集」（`plantings.edit`）とは別物なので混同しないこと。

`url_for` 例:
- `url_for('plantings.index')` → `/plantings/`
- `url_for('plantings.detail', location_crop_id=1)` → `/plantings/1`
- `url_for('plantings.plant_new')` → `/plantings/plant/new`
- `url_for('plantings.place', location_crop_id=1)` → `/plantings/1/place`
- `url_for('plantings.record_detail', record_id=1)` → `/plantings/record/1`
- `url_for('plantings.edit', record_id=1)` → `/plantings/record/1/edit`
- `url_for('plantings.end_cultivation', location_crop_id=1)` → `/plantings/1/end`（POST）
- `url_for('diary.detail', diary_id=1)` → `/diary/1`

`location_routes.py` にも植え付けに関する操作系エンドポイント（`POST /locations/<id>/plant`（旧・1ステップ植え付け、現在は未使用のレガシー）、`POST /locations/<id>/complete-harvest/<location_crop_id>`、`POST /locations/<id>/remove/<location_crop_id>`、および見取り図系 `/locations/<id>/canvas*`）があるが、見取り図系は `app/static/js/CLAUDE.md` を参照。

## Blueprint規約

- Blueprint名はファイル名から `_routes` を除き、複数形にする（例: `crop_routes.py` → Blueprint名 `crops`、`location_routes.py` → `locations`、`harvest_routes.py` → `harvests`、`task_routes.py` → `tasks`、`supplement_routes.py` → `supplements`）
- 不規則複数形の例外: `variety_routes.py` → `varieties`、`planting_routes.py` → `plantings`
- 単数・集合的な概念を表すものは複数形にしない: `diary_routes.py` → `diary`、`calendar_routes.py` → `calendar`、`cooking_routes.py` → `cooking`、`photo_pool_routes.py` → `photo_pool`
- テンプレートフォルダは Blueprint 名と揃える（`app/templates/{blueprint}/`）

## 新機能追加チェックリスト

1. **モデル作成**: `app/models/{feature}.py` - 静的メソッドパターン、`get_db()`使用
2. **ルート作成**: `app/routes/{feature}_routes.py` - Blueprint名は原則 `{feature}` の複数形（上記「Blueprint規約」参照）
3. **Blueprint登録**: `app/__init__.py` の `create_app()` 内に追加
4. **テンプレート**: `app/templates/{feature}/` フォルダ作成（Blueprint名に合わせる）
5. **CSS（任意）**: `app/static/css/{feature}.css`
6. **JS（任意）**: `app/static/js/{feature}.js`
7. **ナビ追加**: `app/templates/base.html` のナビゲーションに追加

## 関連ドキュメント

- テンプレート規約（詳細画面カード・サイドバー・一覧フィルター等）: `app/templates/CLAUDE.md`
- モデル・スキーマ: `app/models/CLAUDE.md`
- フロントエンドJS（見取り図・モーダル等）: `app/static/js/CLAUDE.md`
