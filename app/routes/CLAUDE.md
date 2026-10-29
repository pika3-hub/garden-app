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
| 写真の振り分け | photo_sort | /photo_pool/sort/?ids=&pos=&done=&kind= | - | POST /photo_pool/sort/save | - |
| Hermes のアドバイス | advices | /advices/?keyword= | /advices/{id} | -（Hermes の API だけで作る） | /advices/{id}/edit、POST /advices/{id}/update、POST /advices/{id}/delete |
| Hermes との会話 | conversations | /conversations/?keyword= | /conversations/{id} | - | - |
| Hermes に聞くパネル（中継、JSON・SSE） | hermes_ask | - | GET /hermes/ask/{entity_type}/{entity_id}/history、GET /hermes/ask/runs/{run_id}（状態）、GET /hermes/ask/runs/{run_id}/events（SSE） | POST /hermes/ask/{entity_type}/{entity_id}/runs、POST /hermes/ask/{entity_type}/{entity_id}/new | POST /hermes/ask/runs/{run_id}/approval |
| 設定 | settings | - | - | - | GET/POST /settings/ |
| ログイン（パスキー） | auth | GET /auth/login | - | GET /auth/register/{token}（非常口の登録ページ） | POST /auth/login/options・/auth/login/verify・/auth/logout・/auth/passkeys/register/options・/auth/passkeys/register/verify・/auth/passkeys/{id}/rename・/auth/passkeys/{id}/delete |

補足情報・写真プールはページ単位のCRUDではなく、他画面に埋め込まれるモーダル/フォーム部品からのPOST操作が中心（詳細は `docs/frontend/supplements.md` / `docs/frontend/images-and-photo-pool.md` を参照）。

`settings` Blueprint は設定画面に加え、作物・品種フォーム共通の AI メモ下書き API `POST /settings/ai/notes-draft`（JSON）を持つ。リクエストは `{"mode": "crop", "crop_name", "crop_type", "use_web_search"}` または `{"mode": "variety", "crop_id", "variety_name", "use_web_search"}`。成功 200 `{"ok": true, "markdown"}`、入力不備 400（地域未設定は `need_settings: true`）、生成失敗 502。Claude API 呼び出しは `app/utils/ai_notes.py` に集約している。

`photo_sort` Blueprint（写真の振り分け）は、画面 `GET /photo_pool/sort/`（GET の値はそのまま入力欄に戻す。収穫量の欄の再描画に使う）、保存 `POST /photo_pool/sort/save`（`action=next` で次の写真、`stay` で同じ写真へリダイレクト。入力エラーは同じ写真を入力値つきで再描画）、AI 下書き `POST /photo_pool/sort/ai-draft`（JSON。`{photo_id, kind, date, location_crop_ids, name, related, planting_label, compare}`（`compare: true` は栽培記録のときだけ効き、写真のある前回の栽培記録の写真とメモも送る） → 成功 200 `{ok, fields}`、入力不備・キー未設定 400、生成失敗 502。保存はしない）を持つ。種類ごとの入力欄は `app/templates/photo_sort/_fields_{kind}.html`。

`hermes_ask` Blueprint（Hermes に聞くパネル）は、ブラウザと Hermes の API Server の中継だけを持つ（すべてログイン必須。GET の3つは `OWNER_ONLY_GET_ENDPOINTS`）。`entity_type` は `planting` / `crop` / `variety`、対象が無ければ 404 で Hermes に何も送らない。`run_id` を受けるルートは `hermes_chats.last_run_id` にある run だけを中継する（それ以外は 404）。events は Hermes の event を `{type: tool|delta|approval|approval_done|done|failed}` に言い換えて流し、tool の preview などの生の中身・キーは出さない。Hermes の `: keepalive` はコメント行としてそのまま流す（ブラウザが去ったことに書き込みで気づき、waitress のスレッドと Hermes への接続を放すため）。`run.completed` では `last_run_id` を変えず `last_used_at` だけ更新する（`HermesChat.touch`。後から始めた run を古い run に戻さない）。Hermes の失敗は届かない・キー違い・未設定が 503、その他 502。Hermes の呼び出しは `app/utils/hermes_client.py`、指示・言い換え・リンクは `app/utils/hermes_context.py` に集約している。

植え付け（plantings）は `?status=active|ended|all` でタブフィルター。

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
| `plantings.planting_edit_ended` | GET `/plantings/<location_crop_id>/edit-ended` | 植え付け編集フォーム（ended時） |
| `plantings.planting_update_ended` | POST `/plantings/<location_crop_id>/update-ended` | 植え付け更新処理（ended時） |
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

`location_routes.py` にも植え付けに関する操作系エンドポイント（`POST /locations/<id>/plant`（旧・1ステップ植え付け、現在は未使用のレガシー）、`POST /locations/<id>/remove/<location_crop_id>`、および見取り図系 `/locations/<id>/canvas*`）があるが、見取り図系は `app/static/js/CLAUDE.md` を参照。

## ログインと新しいルートの規約

Web アプリは `app/auth.py` の `before_request` で守られている（家族は閲覧だけ、編集は自分だけ。概要はルート `CLAUDE.md` の「ログイン（パスキー）」）。

- **GET・HEAD・OPTIONS 以外のルートは、何もしなくてもログインが無ければ拒否される**（既定で拒否）。`@login_required` のようなデコレーターは付けない。ログインなしで受けたい POST は `ANONYMOUS_POST_ENDPOINTS`（ログイン・パスキー登録の処理だけ）に足すが、普通は足さない
- **編集のための GET（新規・編集フォーム、見取り図の編集、一括登録、振り分けなど）は `app/auth.py` の `OWNER_ONLY_GET_ENDPOINTS` に `Blueprint名.関数名` で足す**。足したものだけが、ログインしていない人を `/auth/login` へ案内する。足し忘れると誰でも開ける
- `tests/test_auth_gate.py` の分類のテストは、GET だけのエンドポイントがすべて `OWNER_ONLY_GET_ENDPOINTS` か閲覧用の一覧のどちらかに入っていることを確かめる。新しい GET ルートでこのテストが落ちたら、編集用か閲覧用かを決めて分類する。**閲覧用の判定は名前の形（`*.list`、`*.detail`、`conversations.*`）で信用する部分がある**ので、`xxx.detail` のような名前の編集画面を作ったら、テストが通っても必ず `OWNER_ONLY_GET_ENDPOINTS` に足す
- GET でデータを変える・外部へ接続する・課金するルートは作らない（ログインしていない人にも開けてしまう）。必ず POST にする
- ログイン中の POST などはすべて CSRF トークンの照合を受ける（フォームの隠し項目 `csrf_token` か `X-CSRFToken` ヘッダー。合わなければ 400）。**`app/static/js/csrf.js` がページの読み込み時と送信時に、POST のフォームへ隠し項目を、同じ生成元への GET 以外の `fetch` へヘッダーを自動で付ける**ので、普通は何もしなくてよい。自動で付かない例外は2つ: (1) ページを読み込んだ後に JS で作った POST のフォームを `form.submit()` で送る（送信イベントが起きない）ときは、`csrf_token()` の値を隠し項目に自分で入れる、(2) GET のフォームの中の `formmethod="post"` のボタンには対応していない（POST は別のフォームにする）
- HTTP の入口（`http://<サーバーのIP>:5000`）にはログインの Cookie が届かないので、HTTP からは常にログインしていない扱いになる。ルートの動作をログイン前提にしたときは、テストでログイン済みのフィクスチャを使う
- 外部 API（`create_api_app`）にはこの仕組みは入れない（Bearer トークンで守る）

## Blueprint規約

- Blueprint名はファイル名から `_routes` を除き、複数形にする（例: `crop_routes.py` → Blueprint名 `crops`、`location_routes.py` → `locations`、`harvest_routes.py` → `harvests`、`task_routes.py` → `tasks`、`supplement_routes.py` → `supplements`）
- 不規則複数形の例外: `variety_routes.py` → `varieties`、`planting_routes.py` → `plantings`
- 単数・集合的な概念を表すものは複数形にしない: `diary_routes.py` → `diary`、`auth_routes.py` → `auth`、`calendar_routes.py` → `calendar`、`cooking_routes.py` → `cooking`、`photo_pool_routes.py` → `photo_pool`、`photo_sort_routes.py` → `photo_sort`
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
