# Hermes との会話の履歴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** サーバーの Hermes の会話（Matrix）をスクリプトでアプリの API に送り、アプリで会話の一覧・詳細と、各データの詳細画面の「このデータが出てきた会話」を見られるようにする。

**Architecture:** Hermes の実行ユーザーで動く標準ライブラリだけのスクリプトが `~/.hermes/state.db` を読み取り専用で開き、Matrix の会話を `POST /api/v1/conversations` に送る。アプリは会話・発言を Hermes の ID で上書き保存し、写真は縮小版だけ保存し、curl のコマンドと応答から「作った・変えた・見た」の結び付けを作り直す。Web 画面は新しい Blueprint `conversations` と、各詳細画面に include する共通部品で表示する。

**Tech Stack:** Python 3.12 / Flask / SQLite / Jinja2 / Bootstrap 5 / Pillow（アプリ側）、Python 3 標準ライブラリのみ（スクリプト）、pytest

**Spec:** `docs/superpowers/specs/2026-10-26-hermes-conversations-design.md`

## Global Constraints

- データの流れは Hermes → API だけ。アプリから `~/.hermes` を読む・Hermes に接続する作りにしない
- スクリプトは `state.db` を `file:<path>?mode=ro` の URI で開き、書き込まない。必要な列が無ければ何も送らずに終了コード 1
- 対象は `sessions.source = 'matrix'` だけ
- 同じ会話を何度送っても同じ結果。送られなかった発言・写真は消さない
- 写真は縮小版（`make_thumbnail` と同じ `THUMBNAIL_SIZE` の JPEG）だけ保存し、元のファイルは残さない
- 「見た」は ID を指定した GET（`/{種類}/{id}`、`/{種類}/{id}/image`）だけ。一覧・検索・`/lookup` は数えない
- 区分の表示の優先は 作った > 変えた > 見た
- API の DELETE は作らない。Hermes の SKILL.md にこの API を書かない
- 公開リポジトリなので文書に IP・ユーザー名・ホスト名を書かない（`<user>` などの記号）
- 時刻は他のテーブルと同じ日本時間の `'YYYY-MM-DD HH:MM:SS'` 文字列で保存する（`state.db` の UNIX 秒を `timezone(timedelta(hours=9))` で変換）
- マイグレーションは起動のたびに全ファイルが流れるので、`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` で書く
- テストは `uv run pytest`。メイン PC では HEIC のテスト6件がスキップされるのは正常

## Review Focus

- 発言の本文にユーザーが `[Image attached at: /home/<user>/.ssh/id_rsa]` のような文を書いた → スクリプトは画像キャッシュのフォルダ外・画像の拡張子以外のファイルを読まず送らない（Task 6 のテスト `test_image_refs_outside_cache_are_ignored`）
- 同じ会話を、写真付きで2回送る／1回目の途中で失敗して送り直す → 発言・写真・結び付けが二重にならない（Task 3 のテスト `test_resend_is_idempotent`）
- Hermes が書き込み中で `state.db` がロックされている → スクリプトはエラーで終わり、状態のファイルを進めない。次の回に送り直す（Task 6 のテスト `test_send_failure_keeps_state`）
- 前に送った発言が次の送信に含まれない（圧縮）→ 古い発言は残り、結び付けは保存済みの全発言から作り直される（Task 3 のテスト `test_missing_messages_are_kept_and_links_use_all`）
- 結び付いたデータを画面で削除した → 会話の詳細・各詳細画面は 500 にならず「削除済み」と出す（Task 4 のテスト `test_detail_shows_deleted_link`）

---

## ファイルの構成

| ファイル | 役割 |
|---|---|
| `app/migrations/023_add_conversations.sql` | 4テーブル（作成） |
| `app/models/conversation.py` | `Conversation`（保存・取得・検索・前後・結び付け）（作成） |
| `app/utils/conversation_links.py` | 発言から結び付けを取り出す純粋関数（作成） |
| `app/api/conversations.py` | `POST /api/v1/conversations`（作成） |
| `app/api/__init__.py` | 上の import を追加 |
| `app/__init__.py` | Blueprint 登録、Jinja グローバル `hermes_conversations`、CLI `relink-conversations` |
| `app/routes/conversation_routes.py` | 一覧・詳細（作成） |
| `app/templates/conversations/list.html`, `detail.html` | 画面（作成） |
| `app/templates/_hermes_conversations_section.html` | 各詳細画面に入れる欄（作成） |
| `app/static/css/conversations.css` | 吹き出し（作成） |
| `app/models/photo_pool.py`, `app/routes/photo_pool_routes.py` | ラベルとリンク先に `planting` を追加 |
| `tools/hermes_conversation_sync.py` | 送るスクリプト（作成） |
| `docs/api/hermes-conversation-sync.md` | 配置・確かめ方・止め方（作成） |

---

### Task 1: テーブルとモデル

**Files:**
- Create: `app/migrations/023_add_conversations.sql`
- Create: `app/models/conversation.py`
- Test: `tests/test_conversation_model.py`

**Interfaces:**
- Produces（`app/models/conversation.py`、他のモデルと同じ静的メソッドのクラス `Conversation`。戻り値の行は `dict`）:
  - `upsert(session: dict) -> tuple[int, bool]` — `session` は Task 3 の `session` オブジェクト（時刻は変換済みの文字列）。`hermes_id` で探し、あれば更新・無ければ作成。`(アプリの id, 作ったか)` を返す
  - `upsert_messages(conversation_id: int, messages: list[dict]) -> None` — `hermes_message_id` で上書き・追加。渡されなかった発言は消さない
  - `get_messages(conversation_id: int, *, include_tools: bool = False) -> list[dict]` — 時刻・`hermes_message_id` の順。`include_tools=False` なら `role in ('user','assistant')` かつ本文が空でないものだけ
  - `has_image(conversation_id: int, file_name: str) -> bool` / `add_image(conversation_id: int, file_name: str, image_path: str) -> None` / `get_images(conversation_id: int) -> dict[str, str]`（`{file_name: image_path}`）
  - `replace_links(conversation_id: int, links: list[dict]) -> None` — その会話の結び付けを全部消して入れ直す。`links` の要素は `{'entity_type', 'entity_id', 'kind', 'hermes_message_id'}`
  - `get_links(conversation_id: int) -> list[dict]` / `get_by_entity(entity_type: str, entity_id: int) -> list[dict]` — 後者は会話の `id, title, last_activity_at` と `kind` を持ち、新しい順。1つの会話に複数の区分があれば優先の高い1つにまとめる
  - `get_all() -> list[dict]` / `search(keyword: str) -> list[dict]` — 新しい順（`COALESCE(last_activity_at, started_at) DESC, id DESC`）。各行に `message_count`（表示する発言の数）、`image_count`（印の数ではなく保存済みの写真の数）、`has_image_marker`、`link_count`。検索は題名と、`user` / `assistant` の本文の部分一致
  - `get_by_id(conversation_id: int) -> dict | None` / `get_by_hermes_id(hermes_id: str) -> dict | None`
  - `get_adjacent(conversation_id: int) -> tuple[dict | None, dict | None]` — 一覧の並びで (古い方, 新しい方)。`DiaryEntry.get_adjacent` と同じ形
  - `all_ids() -> list[int]`
  - 定数 `KIND_PRIORITY = {'created': 3, 'updated': 2, 'viewed': 1}`、`KIND_LABELS = {'created': '作った', 'updated': '変えた', 'viewed': '見た'}`

- [ ] **Step 1: テーブルを書く**

`023_add_conversations.sql`（列名はこのとおり。`created_at` / `updated_at` の既定は他のテーブルと同じ `datetime('now', '+9 hours')`）:
- `conversations`: `id` PK, `hermes_id TEXT NOT NULL UNIQUE`, `source TEXT NOT NULL`, `title TEXT`, `started_at TIMESTAMP`, `ended_at TIMESTAMP`, `last_activity_at TIMESTAMP`, `end_reason TEXT`, `parent_hermes_id TEXT`, `created_at`, `updated_at`
- `conversation_messages`: `id` PK, `conversation_id` → `conversations(id) ON DELETE CASCADE`, `hermes_message_id INTEGER NOT NULL`, `role TEXT NOT NULL`, `content TEXT`, `tool_calls TEXT`（JSON）, `tool_call_id TEXT`, `tool_name TEXT`, `display_kind TEXT`, `timestamp TIMESTAMP`, `UNIQUE(conversation_id, hermes_message_id)`
- `conversation_images`: `id` PK, `conversation_id`（CASCADE）, `file_name TEXT NOT NULL`, `image_path TEXT NOT NULL`, `created_at`, `UNIQUE(conversation_id, file_name)`
- `conversation_links`: `id` PK, `conversation_id`（CASCADE）, `entity_type TEXT NOT NULL`, `entity_id INTEGER NOT NULL`, `kind TEXT NOT NULL CHECK(kind IN ('created','updated','viewed'))`, `hermes_message_id INTEGER`, `UNIQUE(conversation_id, entity_type, entity_id, kind)`、索引 `(entity_type, entity_id)`

- [ ] **Step 2: 失敗するテストを書く**（`app` フィクスチャと `app.app_context()` を使う）

```python
def test_upsert_creates_then_updates(app):
    s = {'hermes_id': '20261025_165529_f52993ca', 'source': 'matrix', 'title': 'じゃがいも',
         'started_at': '2026-10-25 16:55:29', 'ended_at': None, 'last_activity_at': '2026-10-25 16:56:00',
         'end_reason': None, 'parent_hermes_id': None}
    cid, created = Conversation.upsert(s)
    assert created is True
    cid2, created2 = Conversation.upsert({**s, 'title': '変更後'})
    assert (cid2, created2) == (cid, False)
    assert Conversation.get_by_id(cid)['title'] == '変更後'

def test_upsert_messages_keeps_unsent(app):
    # 1045, 1046 を入れたあと 1046(本文変更), 1047 だけ渡す → 3件、1046 は変更後
    ...
    assert [m['hermes_message_id'] for m in Conversation.get_messages(cid, include_tools=True)] == [1045, 1046, 1047]

def test_get_messages_hides_tools_and_empty(app):
    # role=tool と、本文が空の assistant（tool_calls だけ）は include_tools=False で出ない

def test_get_by_entity_merges_kinds(app):
    # 同じ会話に planting 45 の viewed と updated → get_by_entity('planting', 45) は1件で kind='updated'

def test_search_matches_title_and_text_not_tools(app):
    # 'じゃがいも' は user の本文で当たる。tool の本文にだけある 'skill_view' では当たらない

def test_list_counts(app):
    # message_count は user/assistant の表示分だけ、link_count は結び付けの件数
```

- [ ] **Step 3: 失敗を確かめる**

Run: `uv run pytest tests/test_conversation_model.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.conversation`）

- [ ] **Step 4: `app/models/conversation.py` を実装する**

`upsert` / `upsert_messages` は `INSERT ... ON CONFLICT(...) DO UPDATE` で書く（`updated_at` も更新する）。`get_by_entity` の区分のまとめは SQL の `MAX(CASE kind ...)` か Python のどちらでもよい。

- [ ] **Step 5: 通ることを確かめる**

Run: `uv run pytest tests/test_conversation_model.py tests/test_fresh_db_schema.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/migrations/023_add_conversations.sql app/models/conversation.py tests/test_conversation_model.py
git commit -m "会話の履歴のテーブルとモデルを追加"
```

---

### Task 2: 発言から結び付けを取り出す

**Files:**
- Create: `app/utils/conversation_links.py`
- Test: `tests/test_conversation_links.py`

**Interfaces:**
- Consumes: なし（純粋関数。DB に触れない）
- Produces: `extract_links(messages: list[dict]) -> list[dict]` — `messages` は `Conversation.get_messages(..., include_tools=True)` の行（`role`, `content`, `tool_calls`（JSON 文字列または None）, `tool_call_id`, `hermes_message_id`）。戻り値は `{'entity_type', 'entity_id', 'kind', 'hermes_message_id'}` のリスト（重複なし、`hermes_message_id` は curl を出した assistant の発言）
- 定数 `RESOURCE_TYPES = {'crops': 'crop', 'varieties': 'variety', 'locations': 'location', 'plantings': 'planting', 'planting_records': 'planting_record', 'harvests': 'harvest', 'cooking_records': 'cooking', 'diary_entries': 'diary', 'tasks': 'task', 'photos': 'photo_pool'}`

規則（設計書の「データとの結び付け」）:
- コマンドは assistant の `tool_calls` のうち `function.name == 'terminal'` の `function.arguments`（JSON 文字列）の `command`
- 1つのコマンドを `curl` ごとに区切り、各 curl の API の URL を拾う。API の URL は `$GARDEN_API_URL/`、`${GARDEN_API_URL}/`、`/api/v1/` のどれかに続くパス（クエリは除く）
- メソッド: `-X` / `--request` の値。無ければ `-F` / `--form` / `-d` / `--data*` があり `-G` / `--get` が無いとき POST、それ以外は GET
- `POST /{res}` → 作った。ID は、その呼び出しの ID（`tool_calls[i].id`、無ければ `call_id`）と `tool_call_id` が一致する tool の発言の本文を JSON として読み、`data` が dict なら `data.id`、list なら各 `id`。**そのコマンドに API の POST が2つ以上あるときは「作った」を拾わない**
- `PATCH /{res}/{id}`、`POST /{res}/{id}/end`、`POST /{res}/{id}/images` → 変えた
- `GET /{res}/{id}`、`GET /{res}/{id}/image` → 見た
- それ以外（`GET /{res}`、`/lookup`、`/meta`、`/health`、知らない種類）は拾わない

- [ ] **Step 1: 失敗するテストを書く**（実データと同じ形のコマンドを使う）

```python
TOKEN_HDR = '-H "Authorization: Bearer $GARDEN_API_TOKEN"'

def call(mid, command, call_id='call_1'):
    return {'hermes_message_id': mid, 'role': 'assistant', 'content': '', 'tool_call_id': None,
            'tool_calls': json.dumps([{'id': call_id, 'call_id': call_id,
                'function': {'name': 'terminal', 'arguments': json.dumps({'command': command, 'timeout': 30})}}])}

def result(mid, body, call_id='call_1'):
    return {'hermes_message_id': mid, 'role': 'tool', 'content': body, 'tool_calls': None, 'tool_call_id': call_id}

def test_get_with_id_is_viewed():
    msgs = [call(1, f'curl -sS {TOKEN_HDR} "$GARDEN_API_URL/plantings/45"')]
    assert extract_links(msgs) == [{'entity_type': 'planting', 'entity_id': 45, 'kind': 'viewed', 'hermes_message_id': 1}]

def test_image_download_is_viewed():
    # curl ... -o /tmp/x.jpg "$GARDEN_API_URL/planting_records/312/image?size=thumb" → planting_record 312 viewed

def test_list_search_and_lookup_are_ignored():
    # -G "$GARDEN_API_URL/plantings" --data-urlencode 'crop_id=1' と "$GARDEN_API_URL/lookup" --data-urlencode 'q=ジャガイモ' → []

def test_post_created_from_matching_result():
    # call(1, curl -X POST ... "$GARDEN_API_URL/planting_records" -F data=...) と
    # result(2, '{"ok": true, "data": {"id": 312, ...}}') → planting_record 312 created（hermes_message_id=1）

def test_post_photos_list_creates_each():
    # POST /photos の応答 data が [{"id": 7}, {"id": 8}] → photo_pool 7, 8 created

def test_patch_end_images_are_updated():
    # -X PATCH "$GARDEN_API_URL/plantings/45"、-X POST ".../plantings/45/end"、-X POST ".../crops/3/images" → すべて updated

def test_form_without_x_is_post_and_g_is_get():
    # -F ... "$GARDEN_API_URL/harvests" は POST、-G -d 'q=a' "$GARDEN_API_URL/harvests/9" は GET（viewed）

def test_two_posts_in_one_command_skip_created():
    # "curl -X POST .../crops ... && curl -X POST .../varieties ..." と応答 → created なし

def test_literal_url_and_braced_var():
    # "http://127.0.0.1:5001/api/v1/tasks/4" と "${GARDEN_API_URL}/tasks/5" → task 4, 5 viewed

def test_broken_json_is_ignored():
    # arguments が JSON でない、tool の本文が JSON でない → 例外を出さず拾わない
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_conversation_links.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `extract_links` を実装する**

curl の引数の分解は `shlex.split`（失敗したら空白で分割）。`&&` `;` `|` で区切った後、トークンが `curl` で始まる区間ごとに処理する。

- [ ] **Step 4: 通ることを確かめる**

Run: `uv run pytest tests/test_conversation_links.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/utils/conversation_links.py tests/test_conversation_links.py
git commit -m "Hermes の curl から作った・変えた・見たデータを取り出す処理を追加"
```

---

### Task 3: API `POST /api/v1/conversations` と作り直しのコマンド

**Files:**
- Create: `app/api/conversations.py`
- Modify: `app/api/__init__.py`（import に `conversations` を追加）
- Modify: `app/__init__.py`（CLI コマンド `relink-conversations`）
- Modify: `docs/api/README.md`（8章の補助エンドポイントの後に「会話の履歴（同期スクリプト専用）」の節）
- Test: `tests/api/test_api_conversations.py`

**Interfaces:**
- Consumes: Task 1 の `Conversation.*`、Task 2 の `extract_links`、既存の `parse_request(('images',))`、`check_image`、`ok`、`validation_error`、`detail`、`make_thumbnail`
- Produces:
  - 本文（multipart の `data` か JSON）:
    ```json
    {"session": {"id": "20261025_165529_f52993ca", "source": "matrix", "title": "…",
                 "started_at": 1761378929.5, "ended_at": null, "last_activity_at": 1761379000.0,
                 "end_reason": null, "parent_session_id": null},
     "messages": [{"id": 1045, "role": "user", "content": "…", "tool_calls": null,
                   "tool_call_id": null, "tool_name": null, "timestamp": 1761378929.6, "display_kind": null}]}
    ```
    写真は `images` パーツ（複数）。ファイル名は印の `img_xxxx.jpg` のまま
  - 応答 `ok({'id', 'hermes_id', 'message_count', 'image_count', 'skipped_images'}, 201 か 200)`。`message_count` はアプリに保存済みの全発言数、`image_count` は保存済みの写真数、`skipped_images` は読めなかった写真のファイル名
  - `relink_conversation(conversation_id: int) -> int`（`app/api/conversations.py` に置かずモデルから呼べる場所なら可。目安: `app/models/conversation.py` の `Conversation.relink(conversation_id) -> int` として、保存済みの全発言で `extract_links` → `replace_links`。件数を返す）
  - CLI: `uv run flask --app app relink-conversations` で全会話を作り直し、件数を表示

検証（誤りは既存どおり 422 の `details` に全件）:
- 本文の最上位は `session` と `messages` だけ。`session` の項目は上の8つだけ、`messages` の各要素は上の8つだけ（知らない項目は 422）
- `session.id`: 必須、`^[A-Za-z0-9_.-]{1,128}$`。`source`: 必須の文字列。`title` / `end_reason` / `parent_session_id`: 文字列か null。時刻: 数値か null（`started_at` は必須）
- `messages`: 配列、最大 5000 件。`id` 必須の整数、`role` は `user` / `assistant` / `tool`、`timestamp` 必須の数値、`content` / `tool_call_id` / `tool_name` / `display_kind` は文字列か null、`tool_calls` は配列か null（保存時は `json.dumps(..., ensure_ascii=False)`）
- `images`: 最大 `MAX_FILES_PER_REQUEST` 枚、ファイル名は `^[A-Za-z0-9_.-]{1,100}$`（違えば 422）。**画像として読めないものは 415 にせず `skipped_images` に入れて続ける**（同期スクリプトが同じ会話で止まり続けないため）
- 写真の保存: 同じ会話に同じ `file_name` があれば何もしない。無ければ一時ファイルに保存し（HEIC は既存の処理で JPEG に）、`make_thumbnail(一時ファイル, uploads/conversations/<uuid>.jpg)` で縮小版だけ作り、一時ファイルを消す。`image_path` は `conversations/<uuid>.jpg`（`thumbs/` は作らない）
- 処理の順: 検証 → `upsert` → `upsert_messages` → 写真 → `Conversation.relink`。`g.api_target_id` にアプリの id

- [ ] **Step 1: 失敗するテストを書く**（`api` / `anon` / `sql` フィクスチャ。画像は既存のテストの作り方（`tests/api/helpers.py`）に合わせる）

```python
def test_create_then_update(api):
    r = api.post('/api/v1/conversations', json=payload())
    assert r.status_code == 201 and r.json['data']['message_count'] == 3
    r = api.post('/api/v1/conversations', json=payload(title='変更'))
    assert r.status_code == 200

def test_resend_is_idempotent(api, sql):
    # 同じ本文＋同じ写真 img_aaa.jpg を2回 → conversation_messages / conversation_images / conversation_links の件数が変わらない

def test_missing_messages_are_kept_and_links_use_all(api, sql):
    # 1回目: GET /plantings/45 の curl を含む発言、2回目: その発言を含まない別の発言だけ
    # → 発言は両方残り、planting 45 viewed の結び付けも残る

def test_thumbnail_only(api, api_app):
    # 写真付きで送る → uploads/conversations/ に JPEG が1つだけ、長辺が THUMBNAIL_SIZE 以下、thumbs/ は無い

def test_unreadable_image_is_skipped(api):
    # images に 'img_bad.jpg'（中身がテキスト）→ 201、skipped_images == ['img_bad.jpg']

def test_validation_errors(api):
    # session.id 無し、role='system'、知らない項目 'foo'、messages が配列でない → 422 で details に全件

def test_bad_image_name_is_422(api):
    # ファイル名 '../x.jpg' → 422

def test_requires_token(anon):
    assert anon.post('/api/v1/conversations', json=payload()).status_code == 401

def test_times_are_jst_strings(api, sql):
    # started_at の UNIX 秒 → 日本時間の 'YYYY-MM-DD HH:MM:SS'（UNIX 秒を +9 時間）

def test_relink_command(api_app, api, sql):
    # 結び付けを手で消してから app.test_cli_runner().invoke(args=['relink-conversations']) → 結び付けが戻る
```

（`test_times_are_jst_strings` の期待値は、テストの中で `datetime.fromtimestamp(ts, timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')` から作る）

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/api/test_api_conversations.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 実装する**（`app/api/conversations.py`、`Conversation.relink`、CLI、`app/api/__init__.py` の import）

CLI コマンドは `create_app` の中で `@app.cli.command('relink-conversations')`。API アプリ（`create_api_app`）には登録しなくてよい。

- [ ] **Step 4: 通ることを確かめる**

Run: `uv run pytest tests/api -v`
Expected: PASS（既存の API のテストも含めて）

- [ ] **Step 5: `docs/api/README.md` に節を足す**

`POST /conversations` の本文・応答・写真の扱い・「同期スクリプト専用。Hermes の SKILL.md には書かない」を書く。冒頭の「削除はできない」の記述と矛盾しないこと。

- [ ] **Step 6: Commit**

```bash
git add app/api/conversations.py app/api/__init__.py app/models/conversation.py app/__init__.py docs/api/README.md tests/api/test_api_conversations.py
git commit -m "API に会話の受け取り（POST /conversations）と結び付けの作り直しコマンドを追加"
```

---

### Task 4: 会話の一覧・詳細の画面

**Files:**
- Create: `app/routes/conversation_routes.py`（Blueprint 名 `conversations`、`url_prefix='/conversations'`）
- Create: `app/templates/conversations/list.html`, `app/templates/conversations/detail.html`
- Create: `app/static/css/conversations.css`
- Modify: `app/__init__.py`（Blueprint 登録）、`app/templates/base.html`（ナビの「タスク」の後、「写真プール」の前に「Hermes」。アイコンは `bi-chat-dots`。`is_conversations` は既存の `is_*` と同じ作り方）
- Modify: `app/models/photo_pool.py`（`_LABEL_QUERIES` に `'planting'`。ラベルは `_crop_label(...)` と場所名、例「トマト（アイコ） 畑A」）、`app/routes/photo_pool_routes.py`（`_DETAIL_ENDPOINTS` に `'planting': ('plantings.detail', 'location_crop_id')`）
- Test: `tests/test_conversation_routes.py`

**Interfaces:**
- Consumes: Task 1 の `Conversation.*` と `KIND_LABELS`、`app/models/photo_pool._labels(db, entity_type, ids)`、`app/routes/photo_pool_routes.usage_url(link)`（`link` は `label` / `target_type` / `target_id` を持つ dict。`label` が None なら削除済み）
- Produces:
  - `GET /conversations/`（エンドポイント `conversations.list`、`?keyword=`）
  - `GET /conversations/<int:conversation_id>`（`conversations.detail`）
  - `strip_image_markers(text: str) -> tuple[str, list[str]]`（`conversation_routes.py`。印 `[Image attached at: …]` と `[screenshot]` を除いた本文と、印のファイル名（パスの最後）のリスト）
  - `link_items(links: list[dict]) -> list[dict]`（`conversation_routes.py`。`Conversation.get_links` の行に `label` / `target_type` / `target_id` / `kind_label` を付け、区分の優先でまとめ、作った・変えた・見たの順に並べる。Task 5 でも使う）

画面:
- 一覧: 日記の一覧と同じ年・季節・月のバッジ（`date-badge-filter.js`、日付は `last_activity_at`、無ければ `started_at`）とキーワード検索。1行に日時、題名、発言数、写真のアイコン（印があれば）、結び付けの件数
- 詳細: 題名、始まり・最後の時刻、`_detail_nav.html`（`get_adjacent`）、前の会話（`parent_hermes_id` がアプリにあればリンク）。発言は user を右・assistant を左の吹き出し、assistant の本文は `|markdown`、user の本文はエスケープして改行を保つ。`display_kind == 'failed_turn'` は「失敗したやりとり」のバッジ。写真は印ごとに、保存済みなら `url_for('static', filename='uploads/' + path)` の縮小版、無ければ「写真あり（保存されていません）」。最後に「この会話で Hermes が作った・変えた・見たデータ」（`link_items`、削除済みは「削除済み」、`photo_pool` は `/photo_pool/` へのリンク）

- [ ] **Step 1: 失敗するテストを書く**（`client` フィクスチャ。データは `Conversation` のメソッドで直接入れる）

```python
def test_strip_image_markers():
    text, names = strip_image_markers('登録して  [Image attached at: /home/u/.hermes/cache/images/img_7e4f.jpg] [screenshot]')
    assert text.strip() == '登録して' and names == ['img_7e4f.jpg']

def test_list_and_keyword(client):
    # 2件入れて /conversations/ に両方の題名、?keyword=じゃがいも で片方だけ

def test_detail_hides_tools_and_markers(client):
    # tool の本文 'SKILL_BODY' と印の文字列 'Image attached at' が出ない、user と assistant の本文は出る

def test_detail_shows_saved_and_missing_photos(client):
    # 印2つのうち1つだけ保存済み → img タグ1つと「写真あり（保存されていません）」

def test_detail_shows_links(client):
    # 作物を作り、その crop を created で結び付け → 作物の詳細へのリンクと「作った」

def test_detail_shows_deleted_link(client):
    # 存在しない planting 999 の viewed → 200 で「削除済み」

def test_detail_404_redirects(client):
    # 無い id → 一覧へリダイレクト（日記と同じ）

def test_nav_has_menu(client):
    assert '/conversations/' in client.get('/').get_data(as_text=True)
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_conversation_routes.py -v`
Expected: FAIL

- [ ] **Step 3: ルート・テンプレート・CSS・ナビ・ラベルを実装する**

- [ ] **Step 4: 通ることを確かめる**

Run: `uv run pytest tests/test_conversation_routes.py tests/test_photo_pool_usage_links.py -v`
Expected: PASS

- [ ] **Step 5: ブラウザで確かめる**（`docs/dev-workflow-tips.md` のコピー DB の手順。実データの `instance/garden.db` に会話を入れない）

テスト用の会話をコピー DB に API で入れ、一覧・詳細・写真・リンクが崩れないこと、スマホ幅で吹き出しがはみ出さないことを見る。

- [ ] **Step 6: Commit**

```bash
git add app/routes/conversation_routes.py app/templates/conversations app/static/css/conversations.css app/__init__.py app/templates/base.html app/models/photo_pool.py app/routes/photo_pool_routes.py tests/test_conversation_routes.py
git commit -m "Hermes との会話の一覧・詳細の画面を追加"
```

---

### Task 5: 各詳細画面の「このデータが出てきた Hermes との会話」

**Files:**
- Create: `app/templates/_hermes_conversations_section.html`
- Modify: `app/__init__.py`（Jinja グローバル `hermes_conversations`）
- Modify: 詳細テンプレート9つ: `crops/detail.html`, `varieties/detail.html`, `locations/detail.html`, `plantings/detail.html`, `plantings/record_detail.html`, `harvests/detail.html`, `cooking/detail.html`, `diary/detail.html`, `tasks/detail.html`
- Test: `tests/test_conversation_sections.py`

**Interfaces:**
- Consumes: `Conversation.get_by_entity(entity_type, entity_id)`、Task 4 の `KIND_LABELS`
- Produces: Jinja グローバル `hermes_conversations(entity_type: str, entity_id: int) -> list[dict]`（各要素に `id`, `title`, `last_activity_at`, `kind`, `kind_label`）。部品は `{% set conv_items = hermes_conversations('crop', crop.id) %}{% include '_hermes_conversations_section.html' %}` で使い、`conv_items` が空なら何も出さない

- [ ] **Step 1: 失敗するテストを書く**

```python
@pytest.mark.parametrize('entity_type,make,url', [...9種類...])
def test_section_shows_linked_conversation(client, entity_type, make, url):
    # make() でデータを作り、会話に結び付け → url の詳細画面に会話の題名・区分・/conversations/<id> へのリンク

def test_section_hidden_without_links(client):
    # 結び付けの無い作物の詳細画面に「Hermes との会話」の見出しが出ない

def test_crop_page_excludes_variety_links(client):
    # 品種 variety にだけ結び付け → 親の作物の画面には出ない（設計書: 品種経由は含めない）
```

（データの作り方は既存のテスト `tests/test_photo_pool_usage_links.py` などに合わせる）

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_conversation_sections.py -v`
Expected: FAIL

- [ ] **Step 3: 部品・グローバル・9つのテンプレートを実装する**

置き場所は各画面の本文の列の最後（補足情報の欄がある画面はその直後）。

- [ ] **Step 4: 全テストを通す**

Run: `uv run pytest`
Expected: PASS（HEIC の6件はスキップ）

- [ ] **Step 5: Commit**

```bash
git add app/templates/_hermes_conversations_section.html app/__init__.py app/templates tests/test_conversation_sections.py
git commit -m "各詳細画面にそのデータが出てきた Hermes との会話を表示"
```

---

### Task 6: 同期スクリプト

**Files:**
- Create: `tools/hermes_conversation_sync.py`
- Test: `tests/test_hermes_conversation_sync.py`（`tests/test_matrix_helper.py` と同じく `importlib` で読み込み、送信は偽物に差し替える）

**Interfaces:**
- Consumes: Task 3 の本文の形と応答
- Produces（すべて標準ライブラリ）:
  - `REQUIRED_COLUMNS = {'sessions': {...}, 'messages': {...}}`（送るのに使う列）
  - `class SchemaError(Exception)`
  - `open_db(path: str) -> sqlite3.Connection` — `mode=ro` の URI、`timeout=10`、`row_factory=sqlite3.Row`
  - `check_schema(conn) -> None` — 足りない列があれば `SchemaError`（メッセージに列名）
  - `fingerprint(conn, session_row) -> list` — `[最大の messages.id, title, ended_at, end_reason]`
  - `select_sessions(conn, state: dict) -> list[sqlite3.Row]` — `source='matrix'` で、`state['sessions'][id]['fingerprint']` と違うもの。古い順
  - `build_payload(conn, session_row, tool_limit: int = 20000) -> dict` — Task 3 の本文。`role` は `user` / `assistant` / `tool` だけ。`tool` は `tool_name == 'terminal'` のものだけで本文は `tool_limit` 文字で切る。assistant の `tool_calls` は `function.name == 'terminal'` の要素だけを `{'id', 'call_id', 'function': {'name', 'arguments'}}` に絞り、残らなければ null。`reasoning*` は送らない
  - `image_refs(payload: dict, cache_dir: str) -> list[str]` — user の本文の印 `[Image attached at: <path>]` のうち、`realpath` が `cache_dir` の直下で拡張子が `.jpg/.jpeg/.png/.webp/.gif/.heic/.heif` で、ファイルが存在するもの（重複なし）
  - `post(url: str, token: str, payload: dict, image_paths: list[str], transport=None) -> tuple[int, dict]` — multipart（`data` に JSON、`images` に各ファイル）。既定の transport は `urllib.request`
  - `main(argv=None, transport=None) -> int` — 引数 `--db`（既定 `~/.hermes/state.db`）、`--state`（既定 `~/.local/state/garden-conversation-sync.json`）、`--env`（既定 `~/.config/garden-api.env`）、`--cache-dir`（既定 `~/.hermes/cache/images`）、`--dry-run`（送らずに対象の会話と件数を表示）
  - 状態のファイル: `{"sessions": {"<id>": {"fingerprint": [...], "sent_images": ["img_….jpg"]}}}`。2xx の会話だけ更新し、一時ファイルに書いてから `os.replace`、パーミッション 600。送る写真は `sent_images` に無いものだけ
  - 終了コード: 全件成功 0、失敗が1件でもあれば 1（成功した会話の状態は保存する）。ログは1会話1行（会話 ID・発言数・写真数・HTTP 状態）。トークン・本文は出さない

- [ ] **Step 1: 失敗するテストを書く**（tmp に設計書の列だけを持つ `sessions` / `messages` を作る）

```python
def test_check_schema_missing_column(tmp_path):
    # messages に tool_calls が無い DB → SchemaError、メッセージに 'tool_calls'

def test_selects_only_matrix_and_changed(tmp_path):
    # matrix 2件・cli 1件。state に片方の現在の fingerprint → もう片方だけ

def test_build_payload_filters(tmp_path):
    # session_meta は入らない、skill_view の tool は入らない、terminal の tool の本文は tool_limit で切れる、
    # assistant の tool_calls は terminal だけ、reasoning は入らない

def test_image_refs_outside_cache_are_ignored(tmp_path):
    # cache_dir 内の img_a.jpg（存在）、cache_dir 外の /etc/passwd、cache_dir 内の notes.txt、存在しない img_b.jpg → ['…/img_a.jpg'] だけ

def test_main_sends_and_saves_state(tmp_path):
    # 偽の transport が 201 → 状態のファイルに fingerprint と sent_images、2回目の main は何も送らない

def test_send_failure_keeps_state(tmp_path):
    # 偽の transport が 500 → 終了コード 1、状態のファイルは前のまま。DB がロック（別接続で BEGIN EXCLUSIVE）→ 終了コード 1 で送らない

def test_images_not_resent(tmp_path):
    # 1回目で img_a を送った会話に発言が増えた → 2回目は images を付けない

def test_dry_run_sends_nothing(tmp_path, capsys):
    # --dry-run → transport が呼ばれず、会話 ID と件数が表示される
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run pytest tests/test_hermes_conversation_sync.py -v`
Expected: FAIL

- [ ] **Step 3: スクリプトを実装する**

env ファイルは `KEY=VALUE` の行だけを読む（`export` や引用符は外す）。multipart の境界は `uuid4().hex`。

- [ ] **Step 4: 通ることを確かめる**

Run: `uv run pytest tests/test_hermes_conversation_sync.py -v`
Expected: PASS

- [ ] **Step 5: 実物の構造で空回しする**（メイン PC に `state.db` は無いので、サーバーで `--dry-run` するのは Task 8）

- [ ] **Step 6: Commit**

```bash
git add tools/hermes_conversation_sync.py tests/test_hermes_conversation_sync.py
git commit -m "Hermes の会話をアプリに送る同期スクリプトを追加"
```

---

### Task 7: 文書

**Files:**
- Create: `docs/api/hermes-conversation-sync.md`
- Modify: `docs/api/hermes-local-chat.md`（参照を1行）、`CLAUDE.md`（主な機能に「Hermes との会話の履歴」）、`app/models/CLAUDE.md`（4テーブル）、`app/routes/CLAUDE.md`（URL 設計に `/conversations/`）、`README.md`、`docs/wishlist.md`（この行を削除、「Hermes のアドバイスを植え付けの画面で見られるようにする」の行に案(1) はこの機能で対応したと追記）

`hermes-conversation-sync.md` に書くこと:
- 役割と流れ（設計書の図）、写真が24時間で消えること
- 配置: メイン PC から `scp tools/hermes_conversation_sync.py <user>@<サーバーのIP>:~/` → サーバーで `python3 ~/hermes_conversation_sync.py --dry-run` → `python3 ~/hermes_conversation_sync.py`（最初の取り込み）
- ユーザーの systemd の2ファイル（そのまま貼れる内容）:
  - `~/.config/systemd/user/garden-conversation-sync.service`: `Type=oneshot`、`ExecStart=/usr/bin/python3 %h/hermes_conversation_sync.py`
  - `~/.config/systemd/user/garden-conversation-sync.timer`: `OnCalendar=*:0/15`、`Persistent=true`、`WantedBy=timers.target`
  - `systemctl --user daemon-reload && systemctl --user enable --now garden-conversation-sync.timer`、確認は `systemctl --user list-timers garden-conversation-sync.timer` と `journalctl --user -u garden-conversation-sync -n 20`
- 止め方（`disable --now`）、状態のファイルを消すと全件送り直し（アプリ側は上書きなので二重にならない）
- Hermes を更新したときの確認: `--dry-run` が `SchemaError` にならないこと
- 結び付けの解析を直したら `uv run flask --app app relink-conversations`（本番は `/opt/garden-app` で `garden` ユーザーとして）

- [ ] **Step 1: 文書を書く**
- [ ] **Step 2: 固有値が無いことを確かめる**

Run: `git diff --cached -U0 | grep -nE "192\.168|pika3"`（`git add` の後）
Expected: 何も出ない

- [ ] **Step 3: Commit**

```bash
git add docs CLAUDE.md app/models/CLAUDE.md app/routes/CLAUDE.md README.md
git commit -m "会話の履歴の文書を追加・更新"
```

---

### Task 8: 本番への配置（ユーザーと一緒に。Claude はサーバーを操作できない）

コマンドを1ステップずつ示し、結果を貼ってもらう（`garden-app-private/next.md` の「進め方の注意」）。

- [ ] PR を作り、ユーザーにマージを依頼する。`gh pr view` でマージ済みを確かめる
- [ ] サーバーでアプリを更新する（`docs/api/migration-to-ubuntu.md` の更新の手順: バックアップ → `git pull` → 再起動）。起動ログに `Migration applied: 023_add_conversations.sql`
- [ ] スクリプトを送り、`--dry-run` で Matrix の12件前後が出ることを確かめる
- [ ] 最初の取り込みを実行し、アプリの「Hermes」の一覧に会話が出ること、直近24時間の写真が出ること、植え付けの詳細画面に会話が出ることを確かめる
- [ ] タイマーを有効にし、Element X で写真付きの依頼を1回送って、15分以内に一覧に出ることを確かめる
- [ ] worklog（`garden-app-private/worklog/2026-10-26-hermes-conversations.md`）と `next.md` を更新してコミットする
