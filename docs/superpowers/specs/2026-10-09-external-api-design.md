# 外部登録・更新API（エージェント連携）設計書

- 作成日: 2026-10-09
- ステータス: レビュー待ち

## 1. 背景と目的

スマホ（Telegram）→ AIエージェント（Hermes Agent、Ubuntu Server 192.168.11.24）→ 本アプリ、の流れで写真付きの菜園データを登録・更新できるようにする。エージェントに渡すのは「API を呼ぶ権限」だけで、アプリのファイル・DB・既存Web画面には触らせない。

### 要件（ユーザー確認済み）

- 対象: 作物・品種・場所・植え付け・栽培記録・**収穫**・料理・日記・タスク（＋写真プール）
- 操作: 作成（POST）・部分更新（PATCH）・参照（一覧/検索/詳細）。**削除は作らない**
- 植え付けの栽培終了は専用アクション `POST /plantings/{id}/end`（見取り図スナップショット保存・配置解除を含む）
- 画像: 本体1枚＋追加画像は補足情報（supplements の image 型）として添付。写真プールへのアップロードと `photo_pool_id` 指定も可能
- 名前検索（「ミニトマト」→ID）
- Bearer トークン必須。トークンは `.env` で管理しコミットしない
- 画像のサイズ・形式チェック
- バリデーションエラーは項目名と理由を含める
- エージェントPC（.24）からは API にのみ到達でき、既存Web画面（認証なし）には到達できない
- **将来アプリを Ubuntu（エージェントPC）へ移設する前提**で、移設時の変更が `.env` とサービス登録だけで済む設計にする（メインPCは普段電源を落としている）

### スコープ外

- 削除系エンドポイント、植え付けの `removed` 化
- 見取り図（`canvas_data`・`position_x/y`・`canvas_snapshot`）の API 操作
- 補足情報のテキスト/URL/YouTube 型の追加（画像型のみ）
- エージェント側の一時保存・再送キュー（移設で不要になるため）
- 実際の Ubuntu 移設作業（手順書のみ作成）
- 既存Web画面の認証追加

## 2. 全体構成

### 移設後の最終形（Ubuntu）

```
スマホ ──LAN──▶ 0.0.0.0:5000    既存Web画面（認証なし、変更なし）
Hermes ──────▶ 127.0.0.1:5001  APIアプリ（/api/v1/* のみ、Bearer 必須）
  └ 両アプリは同一 waitress プロセス・Linux ユーザー garden で動作
  /opt/garden-app/ … garden 所有・0700。Hermes 実行ユーザーは読めない
```

### 移設前の暫定形（Windows）

```
スマホ ──▶ :5000（FW: LocalSubnet 許可、192.168.11.24 はブロック）
Hermes(.24) ──▶ :5001（FW: 192.168.11.24 のみ許可）
```

### 構成要素

| 要素 | 内容 |
|---|---|
| `create_api_app(config_name)`（`app/__init__.py`） | API Blueprint **のみ**を登録した Flask アプリ。画面ルート・Jinja フィルター・ダッシュボードを持たない。`init_db` は共有 |
| `app/api/` パッケージ | Blueprint `api`（`url_prefix='/api/v1'`）。エンティティごとに1モジュール＋共通モジュール |
| `server.py` | waitress で Web アプリ（`HOST`:5000）と API アプリ（`API_HOST`:`API_PORT`）を同一プロセスで起動。`API_TOKEN` 未設定・32文字未満なら API は起動せず警告ログ |
| `run.py` | 従来どおり Web のみ（debug）。**API は起動しない**（Werkzeug デバッガを LAN に晒さないため） |

両アプリは同じ `garden.db` と `app/static/uploads/` を共有する。書き込みは同一プロセス内スレッドからなので、現状の waitress（threads=10）と同条件。

### 環境変数（`.env`）

| 変数 | 既定 | 用途 |
|---|---|---|
| `API_TOKEN` | なし（必須） | Bearer トークン。32文字以上。生成: `uv run python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `API_HOST` | `127.0.0.1` | API の待受。Windows 暫定期は `0.0.0.0`、移設後は `127.0.0.1` |
| `API_PORT` | `5001` | API のポート |
| `API_MAX_IMAGE_MB` | `20` | 画像1枚の上限 |
| `WEB_BASE_URL` | `http://localhost:5000` | レスポンスの `web_url` / `image_url` 生成用 |
| `DATABASE` | `<cwd>/instance/garden.db` | DB パス上書き（systemd 等で cwd に依存しないため） |
| `SECRET_KEY` | 既存どおり | |

移設時の変更は `API_HOST` と Hermes 側の `GARDEN_API_URL` のみ。アップロード先は `app/static/uploads` のまま（表示が `url_for('static')` に依存しているため移動しない。アプリディレクトリごと 0700 で保護する）。OS 依存コードは書かない（パスは `os.path`/`pathlib`）。

## 3. API 仕様

### 3.1 命名

- ベース: `/api/v1`。リソースは英語複数形 snake_case
- 項目名は DB カラム名を基本とし、`location_crop_id` は API 上 **`planting_id`** に読み替える（モデル呼び出し時に変換）

| リソース | パス | テーブル | 補足情報の entity_type |
|---|---|---|---|
| 作物 | `/crops` | crops | crop |
| 品種 | `/varieties` | varieties | variety |
| 場所 | `/locations` | locations | location |
| 植え付け | `/plantings` | plantings | （なし） |
| 栽培記録 | `/planting_records` | planting_records | （なし） |
| 収穫 | `/harvests` | harvests | harvest |
| 料理 | `/cooking_records` | cooking | cooking |
| 日記 | `/diary_entries` | diary_entries | diary |
| タスク | `/tasks` | tasks | task |
| 写真プール | `/photos` | photo_pool | — |

### 3.2 エンドポイント

共通（写真プール以外の9リソース）:

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/{res}` | 一覧・検索。`q`（部分一致）、`limit`（既定50・最大200）、`offset`、リソース別フィルタ |
| GET | `/{res}/{id}` | 詳細（関連先の名前を展開） |
| POST | `/{res}` | 作成 |
| PATCH | `/{res}/{id}` | 部分更新（送った項目のみ変更） |

DELETE・PUT は定義しない（405 になる）。

個別:

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/health` | 疎通確認（認証必須）。`{"ok":true,"data":{"status":"ok"}}` |
| GET | `/meta` | 選択肢一覧（下記） |
| GET | `/lookup?q=&types=crop,variety,location` | 名前の横断検索。完全一致→前方一致→部分一致の順。各候補 `{type, id, name, display_name, crop_id?}` |
| POST | `/plantings/{id}/end` | 栽培終了。`{"end_date": "YYYY-MM-DD"}`（省略時は今日 JST）。既存 `end_cultivation` と同じ処理（スナップショット→`Planting.harvest`→`Location.remove_from_canvas`）。active 以外は 422 |
| POST | `/{res}/{id}/images` | 追加画像を補足情報（image 型）として添付。multipart `extra_images`（複数）または JSON `{"extra_photo_pool_ids": [...]}`。対象: crops, varieties, locations, harvests, cooking_records, diary_entries, tasks |
| POST | `/photos` | 写真プールへ一括アップロード（multipart `files` 複数、任意 `data` に `{"notes": "..."}`）。EXIF 撮影日時を抽出 |
| GET | `/photos` | 一覧。`unused=true` で未使用のみ |
| GET | `/photos/{id}` | 詳細（使用履歴つき） |

`/meta` の内容:

```json
{"planting_statuses": ["active", "harvested", "removed"],
 "task_statuses": ["pending", "in_progress", "completed"],
 "sun_exposures": ["全日", "半日", "日陰"],
 "weathers": ["晴れ", "曇り", "雨", "雪", "晴れ時々曇り", "曇り時々雨"],
 "crop_types": [既存値], "location_types": [既存値], "harvest_units": [既存値],
 "cooking_categories": [既存値], "crop_icons": [ファイル名], "bg_images": [ファイル名],
 "date_format": "YYYY-MM-DD", "relation_keys": {...リソース別に使えるキー...}}
```

リソース別フィルタ:

| リソース | フィルタ | `q` の対象 |
|---|---|---|
| crops | `crop_type` | name |
| varieties | `crop_id` | 品種名・作物名 |
| locations | `location_type` | name |
| plantings | `status`（active/harvested/removed/all、既定 active）、`crop_id`（`effective_crop_id`＝品種経由含む）、`variety_id`、`location_id` | 作物名・品種名・場所名 |
| planting_records | `planting_id`、`crop_id`、`date_from`、`date_to` | notes |
| harvests | `planting_id`、`crop_id`、`date_from`、`date_to` | notes・作物名・品種名 |
| cooking_records | `category`、`date_from`、`date_to` | title・notes |
| diary_entries | `date_from`、`date_to` | title・content |
| tasks | `status`、`date_from`、`date_to`（due_date） | title・description |

### 3.3 リソース別の項目

凡例: 必=作成時必須、RO=読み取り専用（送ると 422）。全リソース `id`・`created_at`・`updated_at` は RO。

| リソース | 書き込み可能項目 |
|---|---|
| crops | name(必,≤100), crop_type(必,≤50), notes, icon_path(`/meta.crop_icons` のいずれか), image_color(`#RRGGBB`) |
| varieties | crop_id(必,存在), name(必,≤100), notes, icon_path, image_color（未設定は親作物から継承、レスポンスに `effective_*` を付与） |
| locations | name(必,≤100), location_type(必,≤50), area_size(≥0), sun_exposure(選択肢), notes, bg_image(`/meta.bg_images`)。canvas_data は RO |
| plantings | location_id(必), crop_id / variety_id（**どちらか一方のみ必**。両方→422）, planted_date, quantity(整数≥0), notes。status / position_* / canvas_snapshot は RO（終了は `/end`）。end_date は status=harvested のときのみ PATCH で修正可（active で送ると 422）。PATCH は status に関わらず `Planting.update_all()` を使う |
| planting_records | planting_id(必,存在), recorded_at(必), notes |
| harvests | planting_id(必,存在), harvest_date(必), quantity(≥0), unit(≤20), notes |
| cooking_records | title(必,≤200), cooked_date(必), category(≤100), notes, relations{crop_ids, variety_ids, planting_ids, harvest_ids} |
| diary_entries | title(必,≤200), entry_date(必), content, weather(≤50), status(既定 published), relations{crop_ids, variety_ids, location_ids, planting_ids, harvest_ids} |
| tasks | title(必,≤200), description, due_date, status(選択肢), relations{crop_ids, variety_ids, location_ids, planting_ids} |

画像関連の共通項目（画像を持つリソース: crops, varieties, locations, planting_records, harvests, cooking_records, diary_entries）:

- multipart `image`: 本体画像（既存画像は置き換え、旧ファイルは既存画面と同様に削除）
- `photo_pool_id`: 写真プールから本体画像をコピー（`image` と同時指定は 422）
- `remove_image: true`: 本体画像を外す
- multipart `extra_images` / `extra_photo_pool_ids`: 追加画像を補足情報として添付（planting_records は補足情報を持たないため 422。複数枚は記録を複数件作る）

### 3.4 リクエスト形式

- JSON: `Content-Type: application/json`
- 画像付き: `multipart/form-data`。パーツ `data`（JSON 文字列。JSON リクエストと同じ構造）、`image`（1枚）、`extra_images`（複数）
- 空文字・`null`: 任意項目は「値を消す」。必須項目は 422
- 未知の項目は 422（使える項目一覧を reason に含める）
- PATCH の `relations`: **送ったキーだけ置き換え**、送らなかったキーは維持。`"crop_ids": []` でその種類の関連を全解除
- 関連 ID は存在チェックする（存在しなければ 422）

### 3.5 レスポンス形式

```json
// 単体（POST 201 / GET・PATCH 200）
{"ok": true, "data": {"id": 5, ...,
  "web_url": "http://<WEB_BASE_URL>/plantings/5",
  "image_url": "http://<WEB_BASE_URL>/static/uploads/growth_records/xxx.jpg",
  "extra_images": [{"supplement_id": 3, "image_url": "..."}]}}
// 一覧
{"ok": true, "data": [...], "meta": {"total": 12, "limit": 50, "offset": 0}}
// エラー
{"ok": false, "error": {"code": "validation_error", "message": "入力内容に誤りがあります（2件）",
  "details": [{"field": "planted_date", "reason": "YYYY-MM-DD 形式で指定してください", "value": "10/9"},
              {"field": "variety_id", "reason": "ID 99 の品種は存在しません。GET /api/v1/lookup?q=... で検索してください"}]}}
```

関連先は展開して返す。例（植え付け）: `crop: {id, name}`, `variety: {id, name} | null`, `display_name: "アイコ（トマト）"`（既存の作物名表記ルール）, `location: {id, name}`。日記・料理・タスクは `relations: {crop_ids: [...], ...}` と `relation_items: [{type, id, display_name}]` の両方を返す。

| HTTP | code | 場面 |
|---|---|---|
| 400 | `bad_request` | JSON 不正、`data` パーツが JSON でない |
| 401 | `unauthorized` | トークン無し・不一致（理由の詳細は返さない） |
| 404 | `not_found` | パスの ID が存在しない、未定義パス |
| 405 | `method_not_allowed` | DELETE 等 |
| 413 | `too_large` | 画像・リクエストのサイズ超過 |
| 415 | `unsupported_image` | 画像形式が対応外（HEIC 含む） |
| 422 | `validation_error` | 項目の不備（`details` 必須） |
| 500 | `internal_error` | 想定外の例外（内容はログのみ） |

## 4. バリデーション

- `app/api/validation.py` に項目定義（型・必須・最大長・選択肢・参照先）と共通検証関数を置き、各リソースは定義表を宣言する
- 型: `str`（最大長）、`int` / `decimal`（範囲）、`date`（`YYYY-MM-DD` かつ実在日）、`enum`、`color`（`#RRGGBB`）、`ref`（存在チェック）、`file_choice`（`crop_icons` / `bg_images` の一覧）
- **全項目を検証してから** 422 を返す（最初の1件で止めない）
- PATCH は「既存行を取得 → 送られた項目を上書き → マージ結果を検証 → 既存モデルの `update()`/`update_all()` に渡す」。モデル層は変更しない
- 書き込み順序: 項目検証 → 画像検証 → 画像保存 → DB 書き込み。DB 書き込みで例外が出たら、このリクエストで保存した画像ファイルを削除してから 500 を返す
- 関連の保存は既存の `save_relations()` を使う（PATCH ではマージ済みの全関連を渡す）。`planting_ids` → `location_crop_ids` に変換

## 5. 画像チェック

`app/api/images.py`:

- 1枚 ≤ `API_MAX_IMAGE_MB`（既定20MB）、API アプリの `MAX_CONTENT_LENGTH` = 100MB、1リクエスト ≤ 20枚
- 拡張子は信用せず Pillow で開いて `verify()`、`format` が JPEG / PNG / GIF / WEBP であること。保存拡張子は実形式から決める（`save_image` に渡す前に filename を正規化）
- 画素数上限 5000万画素（超過・`DecompressionBombWarning` は 413）
- HEIC/HEIF は 415「HEIC は未対応です。JPEG で送ってください」
- 保存は既存 `save_image` / `copy_image`（サムネイル生成込み）。写真プール使用時は `PhotoPool.record_usage()`

## 6. セキュリティ

- 認証: `Authorization: Bearer <API_TOKEN>` を全エンドポイントで必須（`before_request`）。`hmac.compare_digest` で比較
- API アプリは `/api/v1/*` のみ。static 配信もしない。debug では起動しない
- 例外の詳細・スタックトレースはレスポンスに含めない
- 監査ログ: ロガー `app.api` に INFO で `日時 送信元IP メソッド パス ステータス 対象ID`。トークン・本文は出さない
- CORS ヘッダーなし、レート制限なし（LAN 内1台が相手）

### Windows ファイアウォール（暫定期）

管理者 PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Garden API (Hermes only)" -Direction Inbound -Protocol TCP -LocalPort 5001 -RemoteAddress 192.168.11.24 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Garden Web (LAN)"        -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress LocalSubnet   -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Garden Web block Hermes" -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress 192.168.11.24 -Action Block
```

- 初回起動ダイアログで作られた python.exe の**プログラム単位許可ルール**があると全ポートが開くため、確認・無効化する手順を手順書に含める（`Get-NetFirewallApplicationFilter | Where-Object Program -like '*python*'`）
- 確認: .24 から `curl :5001/api/v1/health` 成功、`:5000/` 失敗。スマホから `:5000/` 成功、`:5001` 失敗

## 7. テスト

- `tests/api/` に段階ごとのテスト。`conftest.py` に `api_app`（tmp_path DB + `create_api_app`）と認証ヘッダー付き `api_client` フィクスチャを追加
- 観点: 401、作成・取得・部分更新（送っていない項目が不変）、422 の `details`（項目名・理由）、植え付けの排他、`/end` の見取り図処理、関連の部分置き換え、画像（正常・破損・拡張子偽装・サイズ超過・HEIC）、DELETE が 405、API アプリから画面 URL が 404、`/lookup` の並び順
- 実データ確認は `docs/dev-workflow-tips.md` に従いコピー DB で curl（`instance/garden.db` は使わない）

## 8. 実装段階

各段階でテスト追加 → 実装 → `docs/api/curl-examples.md` に curl 例を追記 → コミット。

| 段階 | 内容 |
|---|---|
| 0 | 土台: config の環境変数化、`create_api_app`、`server.py` 2ポート、認証、エラー形式、検証基盤、画像チェック、`/health`・`/meta` |
| 1 | crops・varieties（追加画像含む）＋ `/lookup` |
| 2 | locations |
| 3 | plantings（排他・`/end`） |
| 4 | planting_records・harvests |
| 5 | diary_entries・cooking_records・tasks（関連） |
| 6 | photos と各リソースの `photo_pool_id` / `extra_photo_pool_ids` |
| 7 | ドキュメント: `docs/api/README.md`（リファレンス）、FW 手順、`docs/api/migration-to-ubuntu.md`、`docs/api/hermes-skill/SKILL.md`、CLAUDE.md 群・README 更新 |

## 9. Hermes 用スキル（`docs/api/hermes-skill/SKILL.md`）

- YAML frontmatter（name, description）＋本文。`GARDEN_API_URL` / `GARDEN_API_TOKEN` を環境変数から読む
- 手順: `/meta` で選択肢確認 → `/lookup` で ID 解決 → 候補が複数・0件ならユーザーに確認 → 作成/更新 → `web_url` を返す
- PATCH は対象をユーザーに確認してから
- 写真は Telegram から受け取ったファイルパスを multipart で送る
- 422 は `details` を読んで修正し再送は1回まで。接続失敗時は再送せず「メインPCが起動していない可能性」を伝える
- 削除依頼は「API では削除できない。画面から操作してください」と返す
- 例: 「アイコに花が咲いた（写真）」→栽培記録、「ミニトマト300g収穫」→収穫、「明日追肥」→タスク

## 10. 移設手順書（`docs/api/migration-to-ubuntu.md`）

1. Linux ユーザー `garden` 作成、`/opt/garden-app` に clone、所有者 garden・0700。Hermes 実行ユーザーに sudo が無いことを確認
2. uv で依存導入、`.env` 作成（`API_HOST=127.0.0.1`、`HOST=0.0.0.0`、`DATABASE` 絶対パス）
3. データ移行: Windows 側でアプリ停止 → `garden.db` と `app/static/uploads/` をコピー
4. systemd ユニット（`User=garden`、`WorkingDirectory`、`ExecStart=uv run python server.py`、`Restart=on-failure`）
5. ufw: 5000/tcp を LAN サブネットに許可（5001 は 127.0.0.1 待受のため不要）。同じ PC 内の通信は ufw の受信ルールで止まらないため、`ufw-before-output` に `--uid-owner <Hermes の実行ユーザー>` で 5000 番宛てを REJECT するルールを追加し、エージェントが認証なしの Web 画面に届かないようにする
6. バックアップ: cron で `sqlite3 garden.db ".backup ..."` と uploads の rsync
7. Hermes の `GARDEN_API_URL` を `http://127.0.0.1:5001` に変更
