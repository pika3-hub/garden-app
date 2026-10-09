# 外部API リファレンス（/api/v1）

AI エージェント（Hermes Agent など）から、菜園データを参照・作成・部分更新するための JSON API。
既存の Web 画面（認証なし）とは**別アプリ・別ポート**で動き、エージェントは API にしか到達できない。
**削除はできない**（DELETE は 405）。

- 実装: `app/api/`（`create_api_app()` 専用。Web アプリには登録されない）
- curl の例: [`curl-examples.md`](curl-examples.md)
- Windows ファイアウォール: [`firewall-windows.md`](firewall-windows.md)
- Ubuntu への移設: [`migration-to-ubuntu.md`](migration-to-ubuntu.md)
- エージェント用スキル: [`hermes-skill/SKILL.md`](hermes-skill/SKILL.md)
- 設計書: `docs/superpowers/specs/2026-10-09-external-api-design.md`

## 1. 設定と起動

`.env`（コミットしない）:

| 変数 | 既定 | 説明 |
|---|---|---|
| `API_TOKEN` | なし（必須） | Bearer トークン。**32文字以上**。無い・短いと API は起動せず Web のみ起動 |
| `API_HOST` | `127.0.0.1` | API の待受。Windows 暫定期は `0.0.0.0`、Ubuntu 移設後は `127.0.0.1` |
| `API_PORT` | `5001` | API のポート |
| `API_MAX_IMAGE_MB` | `20` | 画像1枚の上限（MB） |
| `WEB_BASE_URL` | `http://localhost:5000` | レスポンスの `web_url` / `image_url` の基準。スマホから開ける URL にする（例 `http://192.168.11.10:5000`） |
| `DATABASE` | `<起動ディレクトリ>/instance/garden.db` | DB の絶対パス（systemd 等で起動ディレクトリに依存しないため） |

トークンの生成:

```bash
uv run python -c "import secrets;print(secrets.token_urlsafe(32))"
```

起動は **`uv run python server.py`**（waitress。5000 で Web、`API_PORT` で API を同じプロセスで待ち受ける）。
`run.py`（開発サーバー、debug）では API は起動しない（デバッガを LAN に晒さないため）。

## 2. リクエスト

- すべてのリクエストに `Authorization: Bearer <API_TOKEN>`
- JSON: `Content-Type: application/json` で本文に JSON オブジェクト
- 画像付き: `multipart/form-data`
  - `data` パーツ: JSON 文字列（JSON リクエストの本文と同じ構造）
  - `image`: 本体画像（1枚）
  - `extra_images`: 追加画像（複数可。補足情報として添付される）
- 空文字・`null` は「値を消す」（必須項目なら 422）
- 知らない項目・読み取り専用の項目を送ると 422（打ち間違いで更新したつもりになる事故を防ぐ）
- 日付は `YYYY-MM-DD`。数値に単位を付けない（`"quantity": 300, "unit": "g"`）。数字の文字列（`"300"`）は受け付ける

## 3. レスポンス

```json
// 単体（POST 201 / GET・PATCH 200）
{"ok": true, "data": {"id": 5, "...": "...", "web_url": "http://…:5000/plantings/5"}}
// 一覧
{"ok": true, "data": [...], "meta": {"total": 12, "limit": 50, "offset": 0}}
// エラー
{"ok": false, "error": {"code": "validation_error", "message": "入力内容に誤りがあります（2件）",
  "details": [{"field": "planted_date", "reason": "YYYY-MM-DD 形式の実在する日付で指定してください（例: 2026-10-09）", "value": "10/9"}]}}
```

| HTTP | code | 場面 |
|---|---|---|
| 400 | `bad_request` | JSON が壊れている、Content-Type が対応外 |
| 401 | `unauthorized` | トークンが無い・違う |
| 404 | `not_found` | パスの ID が存在しない、未定義の URL |
| 405 | `method_not_allowed` | DELETE / PUT など |
| 413 | `too_large` | 画像が大きすぎる・画素数が多すぎる・リクエスト合計100MB超 |
| 415 | `unsupported_image` | 画像として読めない、HEIC/HEIF、JPEG/PNG/GIF/WebP 以外 |
| 422 | `validation_error` | 項目の誤り（`details` に全件） |
| 500 | `internal_error` | 想定外のエラー（詳細はサーバーログのみ） |

422 の `details` は最初の1件で止めず、すべての誤りを返す。`reason` には直し方（使える値、ID の探し方など）を含める。

## 4. 共通エンドポイント

写真プール以外の9リソースで共通:

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/{res}` | 一覧・検索。`q`（部分一致、`%` `_` も文字として扱う）、`limit`（既定50・最大200）、`offset`、リソース別の条件 |
| GET | `/{res}/{id}` | 詳細 |
| POST | `/{res}` | 作成 |
| PATCH | `/{res}/{id}` | 部分更新（送った項目だけ変わる） |
| POST | `/{res}/{id}/images` | 追加画像の添付（`extra_images` ファイル、または JSON `{"extra_photo_pool_ids": [...]}`）。本体画像・補足情報を持つリソースのみ |

知らない検索条件は 422。

## 5. リソース別の項目

凡例: **必** = 作成時に必須。全リソース共通で `id` / `created_at` / `updated_at` / `image_path` は読み取り専用。

### 作物 `/crops`
| 項目 | 型 | 備考 |
|---|---|---|
| name | 文字列 ≤100 | **必** |
| crop_type | 文字列 ≤50 | **必**（既存値は `/meta` の `crop_types`） |
| notes | 文字列 | Markdown |
| icon_path | 選択肢 | `/meta` の `crop_icons` |
| image_color | `#RRGGBB` | 未指定は `#4CAF50` |

検索条件: `crop_type`。詳細に `varieties`（品種の一覧）。画像: 本体・追加あり。

### 品種 `/varieties`
| 項目 | 型 | 備考 |
|---|---|---|
| crop_id | 作物 ID | **必** |
| name | 文字列 ≤100 | **必** |
| notes | 文字列 | |
| icon_path / image_color | 作物と同じ | 未設定なら親作物から継承（NULL のまま保存） |

検索条件: `crop_id`、`q` は品種名・作物名。詳細に `crop`、`display_name`（「アイコ（トマト）」）、`effective_icon_path` / `effective_image_color` / `effective_image_url`（継承後の値）。

### 場所 `/locations`
| 項目 | 型 | 備考 |
|---|---|---|
| name | 文字列 ≤100 | **必** |
| location_type | 文字列 ≤50 | **必** |
| area_size | 数値 ≥0 | ㎡ |
| sun_exposure | 選択肢 | 全日 / 半日 / 日陰 |
| notes | 文字列 | |
| bg_image | 選択肢 | `/meta` の `bg_images` |

`canvas_data`（見取り図）は読み取り専用。検索条件: `location_type`。詳細に `active_plantings`。

### 植え付け `/plantings`
| 項目 | 型 | 備考 |
|---|---|---|
| location_id | 場所 ID | **必** |
| crop_id | 作物 ID | 作物として植えた場合。**crop_id と variety_id はどちらか一方だけ** |
| variety_id | 品種 ID | 品種として植えた場合 |
| planted_date | 日付 | |
| quantity | 整数 ≥0 | 株数 |
| notes | 文字列 | |
| end_date | 日付 | 栽培終了済み（harvested）のときだけ PATCH で修正可 |

- `status` / `position_x` / `position_y` / `canvas_snapshot` は読み取り専用
- PATCH で `variety_id` を送ると `crop_id` は自動で外れる（逆も同じ）
- 検索条件: `status`（active / harvested / removed / all、**既定 active**）、`crop_id`（品種経由の植え付けも含む）、`variety_id`、`location_id`、`q`（作物名・品種名・場所名）
- 詳細に `status`、`display_name`、`crop`、`variety`、`location`、`days_from_planting`
- **栽培終了**: `POST /plantings/{id}/end`（本文 `{"end_date": "YYYY-MM-DD"}`、省略時は今日）。見取り図に配置されていればスナップショットを残して配置を外す（画面の「栽培終了」と同じ処理）。active 以外は 422

### 栽培記録 `/planting_records`
| 項目 | 型 | 備考 |
|---|---|---|
| planting_id | 植え付け ID | **必**。作成後は変更不可（変更すると 422） |
| recorded_at | 日付 | **必** |
| notes | 文字列 | |

画像: 本体1枚のみ（追加画像は不可。複数枚の写真は記録を複数件作る）。検索条件: `planting_id`、`crop_id`、`date_from`、`date_to`。詳細に `planting`、`days_from_planting`。

### 収穫 `/harvests`
| 項目 | 型 | 備考 |
|---|---|---|
| planting_id | 植え付け ID | **必**。作成後は変更不可 |
| harvest_date | 日付 | **必** |
| quantity | 数値 ≥0 | |
| unit | 文字列 ≤20 | 既存値は `/meta` の `harvest_units` |
| notes | 文字列 | |

画像: 本体・追加あり。検索条件: `planting_id`、`crop_id`、`date_from`、`date_to`、`q`（メモ・作物名・品種名）。

### 料理 `/cooking_records`
| 項目 | 型 | 備考 |
|---|---|---|
| title | 文字列 ≤200 | **必** |
| cooked_date | 日付 | **必** |
| category | 文字列 ≤100 | 既存値は `/meta` の `cooking_categories` |
| notes | 文字列 | |
| relations | 関連 | `crop_ids`, `variety_ids`, `planting_ids`, `harvest_ids` |

画像: 本体・追加あり。検索条件: `category`、`date_from`、`date_to`。

### 日記 `/diary_entries`
| 項目 | 型 | 備考 |
|---|---|---|
| title | 文字列 ≤200 | **必** |
| entry_date | 日付 | **必** |
| content | 文字列 | Markdown |
| weather | 文字列 ≤50 | 画面の選択肢は `/meta` の `weathers` |
| status | 文字列 ≤20 | 未指定は `published` |
| relations | 関連 | `crop_ids`, `variety_ids`, `location_ids`, `planting_ids`, `harvest_ids` |

画像: 本体・追加あり。検索条件: `date_from`、`date_to`、`q`（タイトル・本文）。

### タスク `/tasks`
| 項目 | 型 | 備考 |
|---|---|---|
| title | 文字列 ≤200 | **必** |
| description | 文字列 | |
| due_date | 日付 | |
| status | 選択肢 | pending / in_progress / completed（未指定は pending） |
| relations | 関連 | `crop_ids`, `variety_ids`, `location_ids`, `planting_ids` |

画像: **本体画像なし**、追加画像のみ。検索条件: `status`、`date_from` / `date_to`（期限日）、`q`。

## 6. 画像

| 指定 | 意味 |
|---|---|
| multipart `image` | 本体画像。既存があれば置き換え（旧ファイルは削除） |
| `"photo_pool_id": 12` | 写真プールの写真を本体画像としてコピー（`image` と同時指定は 422） |
| `"remove_image": true` | 本体画像を外す |
| multipart `extra_images`（複数） | 追加画像（補足情報の画像として添付） |
| `"extra_photo_pool_ids": [13, 14]` | 写真プールの写真を追加画像としてコピー |

- 形式: JPEG / PNG / GIF / WebP。拡張子ではなく中身で判定し、保存時の拡張子も中身に合わせる
- HEIC/HEIF は 415（Telegram では「写真」として送れば JPEG になる）
- 1枚 `API_MAX_IMAGE_MB`（既定20MB）まで、5000万画素まで、1リクエスト20枚まで、合計100MBまで
- 写真プールから使った場合は使用履歴（`photo_pool_usages`）に記録される

## 7. 関連（relations）

日記・料理・タスクの `relations` は `{"crop_ids": [1], "planting_ids": [5]}` の形。

- **PATCH では送ったキーだけ置き換え、送らなかったキーはそのまま**。`[]` でその種類を全解除
- ID は存在チェックする。重複は1件にまとめる
- 詳細には `relations`（ID）と `relation_items`（`type` / `id` / `display_name`）の両方を返す
- 使えるキーは `/meta` の `relation_keys`

## 8. 補助エンドポイント

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/health` | 疎通確認 |
| GET | `/meta` | 選択肢の一覧（ステータス、天気、日当たり、既存の種類・単位・カテゴリ、アイコン、背景画像、関連キー、画像の制限） |
| GET | `/lookup?q=名前&types=crop,variety,location&limit=20` | 名前の横断検索。完全一致 → 前方一致 → 部分一致の順。品種は `display_name` と `crop_id` 付き |
| POST | `/photos` | 写真プールへ一括アップロード（multipart `files` 複数、任意で `data` に `{"notes": "..."}`）。EXIF の撮影日時を取り込む |
| GET | `/photos?unused=true` | 写真プールの一覧（`unused=true` で未使用のみ） |
| GET | `/photos/{id}` | 詳細（`usages` 付き） |

## 9. 監査ログ

POST / PATCH はサーバーログ（ロガー `app.api`）に1行ずつ出る。トークンや本文は出さない。

```
INFO in __init__: 192.168.11.24 POST /api/v1/harvests -> 201 id=42
```
