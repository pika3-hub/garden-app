# Hermes とのチャット画面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ログイン中に Hermes の画面のタブ「チャット」から、対象のデータなしの会話を複数持って相談・依頼でき、パネルの会話も一覧から続けられ、会話の題名変更・削除ができるようにする。

**Architecture:** 会話の表 `hermes_chats` に題名の列を足し、削除した会話の Hermes ID を覚える表 `deleted_conversations` を作る。中継（`hermes_ask_routes.py`）に「会話の行の id で扱う」JSON のルートを足し、パネルと同じ `hermes-ask.js` を URL を data 属性で受け取る形にして両方で使う。チャット画面は新しい Blueprint `hermes_chat`（`/hermes/chat`）で、左の一覧はサーバーで描き、右はパネルと同じ部品。

**Tech Stack:** Flask / SQLite / Jinja2 / Bootstrap 5 / バニラ JS。新しい依存・CDN なし。

**Spec:** `docs/superpowers/specs/2026-10-30-hermes-chat-design.md`

## Global Constraints

- 中継は全部ログイン必須・CSRF 照合（POST は `app/auth.py` の既定の拒否、GET は `OWNER_ONLY_GET_ENDPOINTS` に足す）
- `HERMES_API_KEY` を HTML・JS・JSON に出さない。8642 番を LAN に開けない
- `innerHTML` に入れるのはサーバーで Markdown を変換した `html` だけ。`delta`・コマンド・エラー文・題名は `textContent`
- 新しい CDN は足さない
- マイグレーションは `app/migrations/027_hermes_chat_titles_and_deletes.sql`。`CREATE ... IF NOT EXISTS`。`ALTER TABLE ... ADD COLUMN` は再実行時の `duplicate column` 警告で済む（既存の 021 と同じ）
- 削除・更新の SQL は `WHERE` で絞る（`docs/db-validation-safety.md`）
- 改行コード: 既存ファイルは元の改行を保つ（`git ls-files --eol <file>`）、新規は LF。Python のテキストモードで書かない。Edit ツールを使う
- 画面の文言は日本語。テストは `uv run python -m pytest`

## Review Focus

1. **圧縮で ID が変わった続きの会話**（`parent_hermes_id` が消した会話を指す）が取り込みで復活しない。孫の代（子の子）も復活しない → Task 2 のテスト `test_upload_ignores_descendant_of_deleted`
2. **変えた題名が取り込みで戻らない**（Hermes の題名で `POST /conversations` が来ても、続きの子の会話でも） → Task 1 `test_upsert_keeps_custom_title_for_child`
3. **走っている途中の会話を消した**あと、ブラウザの events・承認が 404 で終わり 500 にならない → Task 3 `test_events_after_delete_is_404`
4. **対象のデータが消えたパネルの会話**を一覧から開いて続けられる（指示は対象なしの扱い） → Task 3 `test_chat_runs_for_deleted_target_uses_free_instructions`
5. **他の会話の id を書き換えた POST**（存在しない id、Element X の会話の id）で何も消えない・Hermes に何も送らない → Task 3 / Task 5 の 404 テスト

---

### Task 1: 表の変更とモデル（題名・削除）

**Files:**
- Create: `app/migrations/027_hermes_chat_titles_and_deletes.sql`
- Modify: `app/models/hermes_chat.py`, `app/models/conversation.py`
- Test: `tests/test_hermes_chat_model.py`

**Interfaces:**
- Produces:
  - 列 `hermes_chats.title TEXT`（最初の質問から自動）、`hermes_chats.custom_title TEXT`（ユーザーが変えた題名。NULL なら未変更）
  - 表 `deleted_conversations(hermes_id TEXT PRIMARY KEY, deleted_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')))`
  - `HermesChat.create_free(title: str) -> dict`（対象なしの新しい行。`active=0` で作る＝パネルの active の仕組みに乗せない）
  - `HermesChat.get_by_id(chat_id: int) -> dict | None`
  - `HermesChat.set_title_if_empty(chat_id: int, title: str) -> None`
  - `HermesChat.list_for_chat() -> list[dict]`（全行。各行に `display_title` = `COALESCE(custom_title, title, conversations.title)`。`conversations` は `hermes_id = session_id` で LEFT JOIN。並びは `last_used_at DESC, id DESC`）
  - `HermesChat.rename(chat_id: int, title: str) -> bool`（`custom_title` を変え、`conversations.title` も `hermes_id = session_id OR parent_hermes_id = session_id` の行で変える。行が無ければ False）
  - `HermesChat.delete(chat_id: int) -> list[str] | None`（消した縮小版の相対パスの一覧を返す。行が無ければ None。下記）
  - `Conversation.is_deleted(hermes_id: str, parent_hermes_id: str | None) -> bool`
  - `Conversation.upsert(session)` は題名を `custom_title` 優先にする（下記）
  - 定数 `FREE_TITLE_LENGTH = 30`（`app/models/hermes_chat.py`）と `make_title(text: str) -> str`（改行を空白にして前後を詰め、30文字を超えたら29文字＋「…」）

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_hermes_chat_model.py` に追加。`sql` が無ければ `get_db().execute` で書く）

```python
def test_create_free_is_not_active_and_many(app):
    with app.app_context():
        a = HermesChat.create_free('オクラ')
        b = HermesChat.create_free('にんにく')
        assert a['session_id'].startswith('garden-free-') and a['active'] == 0
        assert a['id'] != b['id'] and HermesChat.get_active(None, None) is None

def test_make_title():
    assert make_title('  来年オクラを\n作りたい  ') == '来年オクラを 作りたい'
    assert make_title('あ' * 40) == 'あ' * 29 + '…'

def test_list_for_chat_titles_and_order(app):
    # パネルの会話（title なし）は conversations.title、custom_title があればそれ
    # last_used_at の新しい順

def test_rename_updates_conversation_and_child(app):
    # conversations に hermes_id=session_id の行と parent_hermes_id=session_id の子の行を作り、
    # rename 後は両方の title が新しい題名、hermes_chats.custom_title も新しい題名

def test_upsert_keeps_custom_title_for_child(app):
    # rename 後に Conversation.upsert({'hermes_id': 子のID, 'parent_hermes_id': session_id,
    #   'title': 'Hermesの題名', ...}) → title は変えた題名のまま
    # 変えていない会話は Hermes の題名で更新される（今の動きのまま）

def test_delete_removes_rows_and_remembers_ids(app):
    # 自分と子の conversations（発言・写真・結び付きを1件ずつ）を作って delete
    # → hermes_chats の行・conversations 2行・発言・写真・結び付きが 0 件
    # → deleted_conversations に session_id と子の hermes_id
    # → 戻り値は写真の image_path の一覧
    # → 別の会話の行は残る
    # → advices は残る

def test_delete_unknown_returns_none(app):
    with app.app_context():
        assert HermesChat.delete(999) is None
```

- [ ] **Step 2: 失敗を確かめる**

Run: `uv run python -m pytest tests/test_hermes_chat_model.py -v`
Expected: FAIL（`create_free` などが無い）

- [ ] **Step 3: マイグレーションとモデルを書く**

  - `delete` は1つのトランザクションで: 対象の `conversations` の行（`hermes_id = :sid OR parent_hermes_id = :sid`）の id と `hermes_id` を取る → 写真の `image_path` を集める → `deleted_conversations` に `:sid` と子の `hermes_id` を `INSERT OR IGNORE` → `DELETE FROM conversations WHERE id IN (...)`（発言・写真・結び付きは `ON DELETE CASCADE`。`get_db()` が `PRAGMA foreign_keys = ON` にしているか確かめ、していなければ3表も明示して消す）→ `DELETE FROM hermes_chats WHERE id = ?` → commit
  - `Conversation.upsert` の題名: `title = COALESCE((SELECT custom_title FROM hermes_chats WHERE session_id IN (:hermes_id, :parent_hermes_id) AND custom_title IS NOT NULL ORDER BY id DESC LIMIT 1), :title)` を INSERT と UPDATE の両方で使う
  - `is_deleted`: `hermes_id` か `parent_hermes_id` が `deleted_conversations` にあれば True

- [ ] **Step 4: 通ることを確かめる**

Run: `uv run python -m pytest tests/test_hermes_chat_model.py tests/api/test_api_conversations.py -v`
Expected: PASS

- [ ] **Step 5: `app/models/CLAUDE.md` の表の定義（`hermes_chats` の2列、`deleted_conversations`）を更新してコミット**

```bash
git add app/migrations/027_hermes_chat_titles_and_deletes.sql app/models/hermes_chat.py app/models/conversation.py app/models/CLAUDE.md tests/test_hermes_chat_model.py
git commit -m "チャット画面: 会話の題名と削除（hermes_chats の題名、deleted_conversations）"
```

---

### Task 2: 取り込みで削除済みの会話を登録しない

**Files:**
- Modify: `app/api/conversations.py`（`upload_conversation`）, `docs/api/README.md`（「会話の取り込み」の節）
- Test: `tests/api/test_api_conversations.py`

**Interfaces:**
- Consumes: `Conversation.is_deleted(hermes_id, parent_hermes_id)`（Task 1）、表 `deleted_conversations`
- Produces: 削除済みの会話を送られたら、登録せず **200** で `{'id': None, 'hermes_id': …, 'message_count': 0, 'image_count': 0, 'skipped_images': [], 'ignored': True}`。親が削除済みで送られた会話は、自分の `hermes_id` も `deleted_conversations` に足す（孫の代も止めるため）

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_upload_ignores_deleted(api, sql):
    # deleted_conversations に '20261025_165529_f52993ca' を入れて POST
    # → 200, data['ignored'] is True, data['id'] is None, conversations は 0 件

def test_upload_ignores_descendant_of_deleted(api, sql):
    # 'garden-free-aaaa' を削除済みにする
    # 子 payload(id='c1', parent_session_id='garden-free-aaaa') → ignored、'c1' が deleted_conversations に入る
    # 孫 payload(id='c2', parent_session_id='c1') → ignored、conversations は 0 件
```

- [ ] **Step 2: 失敗を確かめる** — Run: `uv run python -m pytest tests/api/test_api_conversations.py -v` / Expected: 2件 FAIL
- [ ] **Step 3: 検証のあと、`Conversation.upsert` の前で判定して返す**（写真は保存しない）
- [ ] **Step 4: 通ることを確かめる** — 同じコマンドで PASS
- [ ] **Step 5: README の「削除はできない」を「アプリで削除した会話（とその続き）は、送られても登録せず `ignored: true` で返す」に直してコミット**

```bash
git add app/api/conversations.py docs/api/README.md tests/api/test_api_conversations.py
git commit -m "会話の取り込み: アプリで削除した会話とその続きは登録しない"
```

---

### Task 3: 会話の行の id で扱う中継のルート

**Files:**
- Modify: `app/routes/hermes_ask_routes.py`, `app/utils/hermes_context.py`, `app/auth.py`（`OWNER_ONLY_GET_ENDPOINTS`）
- Test: `tests/test_hermes_ask_routes.py`, `tests/test_hermes_context.py`

**Interfaces:**
- Consumes: `HermesChat.create_free / get_by_id / set_title_if_empty / delete`、`make_title`（Task 1）
- Produces（JSON の形は今のパネルのルートと同じ）:
  - `GET /hermes/ask/chats/<int:chat_id>/history` → endpoint `hermes_ask.chat_history`。`{'ok', 'target', 'messages', 'running_run_id'}`。`target` は対象なしなら `None`、対象が消えていれば `{'kind_label': None, 'label': '（削除済み）'}`
  - `POST /hermes/ask/chats/<int:chat_id>/runs` → endpoint `hermes_ask.chat_start`。`{'ok', 'run_id'}`。題名が空なら `make_title(text)` を入れる
  - `POST /hermes/ask/chats/runs` → endpoint `hermes_ask.chat_create`。`create_free(make_title(text))` してから run を始める。`{'ok', 'run_id', 'chat_id', 'chat_url': url_for('hermes_chat.show', chat_id=…), 'title'}`。Hermes に届かなければ作った行を消して 503（空の会話を一覧に残さない）
  - `build_instructions(target, place='panel')`。`place='chat'` かつ対象なしなら新しい定数 `_INSTRUCTIONS_CHAT`:
    `'ユーザーはアプリ（家庭菜園管理アプリ）のチャット画面から相談している。見ているデータは無い。\n答えは画面いっぱいに表示されるので、Element X と同じくらいの長さでよい。'`
    対象があるときは `place` に関係なく今の `_INSTRUCTIONS_WITH_TARGET`（パネルと同じ）
  - 今の `history` / `start` の中身を `_history_payload(chat, target)` / `_start_run(chat, target, place)` に分け、パネルのルートとチャットのルートの両方から呼ぶ（パネルの振る舞いは変えない）
  - `OWNER_ONLY_GET_ENDPOINTS` に `'hermes_ask.chat_history'`

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_chat_create_starts_free_run(client, fake_open):
    fake_open.reply(202, {'run_id': 'run_1'})
    r = client.post('/hermes/ask/chats/runs', json={'text': '来年オクラを作りたい', 'request_key': 'k'})
    assert r.json['ok'] and r.json['run_id'] == 'run_1' and r.json['title'] == '来年オクラを作りたい'
    assert r.json['chat_url'] == f"/hermes/chat/{r.json['chat_id']}"
    body = json.loads(fake_open.calls[0].data)
    assert body['session_id'].startswith('garden-free-') and 'チャット画面' in body['instructions']

def test_chat_create_hermes_down_leaves_no_chat(client, app, fake_open):
    # fake_open.raise_(urllib.error.URLError('down')) → 503、hermes_chats は 0 件

def test_chat_runs_continue_panel_chat_with_target(client, fake_open, planting_id):
    # パネルで1回送った会話の chat_id に POST /chats/<id>/runs → 同じ session_id、指示に GET /plantings/<id>

def test_chat_runs_for_deleted_target_uses_free_instructions(client, app, fake_open, crop_id):
    # crop のパネルの会話を作り、作物を消してから /chats/<id>/runs → 200、指示は _INSTRUCTIONS_CHAT

def test_chat_history_free_and_unknown(client, fake_open):
    # 対象なしの行 → target None。存在しない id → 404 で Hermes に何も送らない

def test_events_after_delete_is_404(client, app, fake_open):
    # chat_create → HermesChat.delete → GET /hermes/ask/runs/run_1/events と POST .../approval が 404

def test_anonymous_rejected_for_chat_routes(anon_client, fake_open):
    # /chats/runs, /chats/1/runs, /chats/1/history が 400/401 か login への 302、fake_open.calls == []
```

`tests/test_hermes_context.py` に `build_instructions(None, place='chat')` と `build_instructions(None)`（今の文のまま）のテストを足す。

- [ ] **Step 2: 失敗を確かめる** — Run: `uv run python -m pytest tests/test_hermes_ask_routes.py tests/test_hermes_context.py tests/test_auth_gate.py -v` / Expected: 新しいテストが FAIL
- [ ] **Step 3: ルートと指示を書く**
- [ ] **Step 4: 通ることを確かめる**（同じコマンドで PASS。既存のパネルのテストも全部 PASS）
- [ ] **Step 5: コミット**

```bash
git add app/routes/hermes_ask_routes.py app/utils/hermes_context.py app/auth.py tests/test_hermes_ask_routes.py tests/test_hermes_context.py
git commit -m "Hermes の中継: 会話の行の id で扱うルート（チャット画面用）"
```

---

### Task 4: `hermes-ask.js` を URL を受け取る形にする

**Files:**
- Modify: `app/static/js/hermes-ask.js`, `app/templates/_hermes_ask_panel.html`, `docs/frontend/hermes-ask-panel.md`
- Test: `tests/test_hermes_ask_panel.py`

**Interfaces:**
- Produces: JS は `[data-hermes-ask]` の要素ごとに動く。data 属性:
  - `data-history-url`（無ければ履歴を読まず、すぐ送れる状態にする＝新しい会話）
  - `data-runs-url`（送る先）
  - `data-new-url`（「新しく始める」。無ければボタンを探さない）
  - `data-autoload`（あればすぐ履歴を読む。無ければパネルの `show.bs.offcanvas` で読む＝今どおり）
  - 承認・events は今どおり `/hermes/ask/runs/<run_id>/…`
  - 送った応答に `chat_id` があれば（新しい会話）: 以後の `runs-url` を `/hermes/ask/chats/<chat_id>/runs` に変え、`history.replaceState(null, '', data.chat_url)` し、要素に `CustomEvent('hermes:chat-created', {detail: {chat_id, chat_url, title}, bubbles: true})` を投げる
  - `done` / `failed` のあと `CustomEvent('hermes:run-finished', {bubbles: true})` を投げる（一覧の時刻の更新用。使わなくてもよい）
- パネルの部品は `data-hermes-ask data-history-url="/hermes/ask/<type>/<id>/history" data-runs-url=".../runs" data-new-url=".../new"` を出す（`id="hermes-ask-panel"` と `data-entity-type` / `data-entity-id` は残す。既存テストが見ている）

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_panel_carries_urls(client, fake_open, planting_id):
    html = client.get(f'/plantings/{planting_id}').get_data(as_text=True)
    assert f'data-history-url="/hermes/ask/planting/{planting_id}/history"' in html
    assert f'data-runs-url="/hermes/ask/planting/{planting_id}/runs"' in html
```

- [ ] **Step 2: 失敗を確かめる** — `uv run python -m pytest tests/test_hermes_ask_panel.py -v` / FAIL
- [ ] **Step 3: JS とテンプレートを直す**（`init` を `document.querySelectorAll('[data-hermes-ask]').forEach(setup)` に。中身の吹き出し・承認・events の処理は変えない）
- [ ] **Step 4: 通ることを確かめる**、続けてコピー DB のサーバー（`docs/dev-workflow-tips.md` の「実データ DB を汚さないブラウザ確認」）で植え付けの詳細を開き、パネルを開いてコンソールにエラーが無いこと（Hermes は手元に無いので 503 の「Hermes に届きません」が出れば正しい）
- [ ] **Step 5: `docs/frontend/hermes-ask-panel.md` の「部品」「振る舞い」に data 属性を書いてコミット**

```bash
git add app/static/js/hermes-ask.js app/templates/_hermes_ask_panel.html docs/frontend/hermes-ask-panel.md tests/test_hermes_ask_panel.py
git commit -m "hermes-ask.js: URL を data 属性で受け取り、パネル以外でも使えるようにする"
```

---

### Task 5: チャット画面（一覧・続き・題名変更・削除）とナビ・タブ

**Files:**
- Create: `app/routes/hermes_chat_routes.py`（Blueprint `hermes_chat`、`url_prefix='/hermes/chat'`）, `app/templates/hermes_chat/index.html`, `app/static/css/hermes-chat.css`, `tests/test_hermes_chat_routes.py`
- Modify: `app/__init__.py`（Blueprint 登録）, `app/auth.py`, `app/templates/base.html`（ナビの「Hermes」）, `app/templates/_hermes_tabs.html`, `app/static/js/hermes-ask.js`（必要なら一覧への差し込みだけ。別ファイル `hermes-chat.js` でもよい）

**Interfaces:**
- Consumes: Task 1 のモデル、Task 3 のルート、Task 4 の data 属性とイベント
- Produces:
  - `GET /hermes/chat/` → `hermes_chat.index`（右は新しい会話: `data-runs-url="/hermes/ask/chats/runs"`、履歴なし）
  - `GET /hermes/chat/<int:chat_id>` → `hermes_chat.show`（右はその会話: `data-history-url="/hermes/ask/chats/<id>/history" data-runs-url="/hermes/ask/chats/<id>/runs" data-autoload`）。無い id は 404
  - `POST /hermes/chat/<int:chat_id>/rename`（フォームの `title`、1〜200文字。空は flash でエラー）→ `hermes_chat.show` へ戻る
  - `POST /hermes/chat/<int:chat_id>/delete` → `HermesChat.delete` → 返ってきた写真を `app/utils/upload.delete_image` で消す → flash「会話を削除しました」→ `hermes_chat.index`。無い id は 404
  - 両方の GET を `OWNER_ONLY_GET_ENDPOINTS` に（未ログインは `/auth/login` へ）。endpoint 名に `list` / `detail` を使わない（`tests/test_auth_gate.py` の閲覧用パターンに当たるため）
  - `hermes_ask_enabled()` が False（キー未設定）なら、画面は開けて右に「Hermes への接続が設定されていません」と出し送れない
- 画面:
  - 上に `_hermes_tabs.html`（`hermes_tab = 'chat'`）。タブの先頭に「チャット」（`hermes_ask_enabled()` のときだけ）
  - 左（`col-md-3`）: 「＋ 新しい会話」（`hermes_chat.index` へのリンク）、`HermesChat.list_for_chat()` の行。1行に題名・最後の時刻（`last_used_at` の `MM/DD HH:MM`）・パネルの会話なら対象の印（`describe_target` の `kind_label: label`、消えていれば「（削除済み）」）。選んでいる行は強調
  - 右（`col-md-9`）: 見出しに題名、題名変更（鉛筆のボタンで見出しの下に小さなフォームを開く）と削除（`onsubmit="return confirm('この会話を削除しますか？会話の履歴からも消えます（Hermes の中の記録とアドバイスは残ります）');"`）。下はパネルと同じ吹き出しと入力欄（`data-hermes-ask` の要素。部品の HTML は `_hermes_ask_panel.html` から吹き出し・入力欄の部分を `_hermes_ask_body.html` に切り出して両方で include してよい）
  - `hermes:chat-created` で左の一覧の先頭に新しい行（題名は `textContent`）を差し込み、選んだ状態にし、見出しの題名を入れる
  - スマホ幅（`md` 未満）では一覧を上、会話を下に縦に積む。会話の欄の高さは `calc(100vh - …)` で画面に収め、吹き出しの欄だけスクロール
- ナビ: 「Hermes」の `href` は `url_for('hermes_chat.index') if hermes_ask_enabled() else url_for('conversations.list')`。active 判定に `hermes_chat.` を足す

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_hermes_chat_routes.py`。`fake_open` を使う）

```python
def test_owner_sees_chat_page_with_tabs(client, fake_open):
    html = client.get('/hermes/chat/').get_data(as_text=True)
    assert 'data-runs-url="/hermes/ask/chats/runs"' in html and '>チャット<' in html

def test_anonymous_redirected_to_login(anon_client, fake_open):
    r = anon_client.get('/hermes/chat/')
    assert r.status_code == 302 and '/auth/login' in r.headers['Location']

def test_nav_hermes_link_depends_on_login(client, anon_client, fake_open):
    # client の '/' のナビに href="/hermes/chat/"、anon_client は href="/conversations/" でタブに「チャット」が無い

def test_list_shows_free_and_panel_chats(client, app, fake_open, planting_id):
    # create_free('オクラの育て方') とパネルの会話を作る → 一覧に「オクラの育て方」と「植え付け:」の印

def test_show_unknown_is_404(client, fake_open):
    assert client.get('/hermes/chat/999').status_code == 404

def test_rename(client, app, fake_open):
    # POST rename title='オクラ' → 302 で show へ、custom_title が 'オクラ'。空の title は custom_title を変えない

def test_delete_removes_from_chat_and_conversations(client, app, fake_open):
    # create_free → conversations に hermes_id=session_id の行と写真ファイル（tmp の UPLOAD_FOLDER に置く）
    # POST delete → 302 で index、/conversations/ に題名が出ない、写真ファイルが無い

def test_delete_unknown_is_404_and_deletes_nothing(client, app, fake_open):
    # POST /hermes/chat/999/delete → 404、他の hermes_chats の行は残る

def test_key_not_in_chat_page(client, fake_open):
    assert 'test-hermes-key' not in client.get('/hermes/chat/').get_data(as_text=True)
```

- [ ] **Step 2: 失敗を確かめる** — `uv run python -m pytest tests/test_hermes_chat_routes.py tests/test_auth_gate.py -v` / FAIL
- [ ] **Step 3: ルート・テンプレート・CSS・ナビ・タブを書く**
- [ ] **Step 4: 通ることを確かめる**（全テスト `uv run python -m pytest`）。続けてコピー DB のサーバーで Chrome から: ログインしてナビの「Hermes」でチャットが開く／未ログインで会話の一覧が開きタブにチャットが無い／一覧の行・題名変更・削除（確認のダイアログはユーザーに押してもらうか JS で `window.confirm` を一時的に差し替える）／幅 375px で横にはみ出さない（`docs/dev-workflow-tips.md` の iframe の方法）／コンソールにエラーが無い
- [ ] **Step 5: 文書を更新してコミット**: `app/routes/CLAUDE.md`（URL 設計表に `/hermes/chat`）、`docs/frontend/hermes-chat.md`（新規。部品・振る舞い・守ること）と `app/templates/CLAUDE.md` のガイド一覧表

```bash
git add app/routes/hermes_chat_routes.py app/templates/hermes_chat/ app/static/css/hermes-chat.css app/__init__.py app/auth.py app/templates/base.html app/templates/_hermes_tabs.html app/templates/_hermes_ask_panel.html app/static/js/ tests/test_hermes_chat_routes.py app/routes/CLAUDE.md app/templates/CLAUDE.md docs/frontend/hermes-chat.md
git commit -m "Hermes とのチャット画面（自由な会話・パネルの会話の続き・題名変更・削除）"
```

---

### Task 6: Hermes への指示と文書

**Files:**
- Modify: `docs/api/hermes-skill/SKILL.md`, `CLAUDE.md`（機能概要の「Hermes に聞くパネル」の近くに「Hermes とのチャット」）, `README.md`, `docs/wishlist.md`, `docs/api/hermes-ask-panel.md`（本番の設定に変わりが無いことを1行）

- [ ] **Step 1: SKILL.md の「アプリのパネルからの相談」に足す**: 指示に「チャット画面から相談している」とあるときは対象なしとして扱い、答えの長さは Element X と同じ。相談への答えは「相談・アドバイスの保存」と同じに保存し、ひも付けは話の中で出てきた登録済みの作物・品種・植え付けがあればそれ、無ければ無し。同じチャットの会話の同じ話題は `PATCH`。対応表（47 行目）の行にも「チャット画面から届いた質問」を足す
- [ ] **Step 2: wishlist**: 「一覧からの自由な会話」の行を消し、「Hermes の中の記録（`state.db`）も消す手段」（登録日 2026-10-30、背景: チャット画面の削除はアプリの中だけ。ユーザーがいつか作りたいと希望）を足す
- [ ] **Step 3: CLAUDE.md・README.md の機能説明を更新**
- [ ] **Step 4: `git diff --name-only main...HEAD | xargs git ls-files --eol | grep crlf` で新規ファイルが CRLF になっていないことを確かめてコミット**

```bash
git add docs/api/hermes-skill/SKILL.md CLAUDE.md README.md docs/wishlist.md docs/api/hermes-ask-panel.md docs/superpowers/specs/2026-10-29-hermes-ask-panel-design.md docs/superpowers/specs/2026-10-30-hermes-chat-design.md docs/superpowers/plans/2026-10-30-hermes-chat.md
git commit -m "Hermes とのチャット画面: SKILL.md と文書"
```

---

## 本番での確認（PR を作ったあと。ユーザーと一緒に）

1. PR を作る → サーバーを PR のブランチに切り替え（`docs/api/migration-to-ubuntu.md` の「9. 更新の手順」、バックアップを先に）
2. SKILL.md を scp でサーバーへ送る
3. HTTPS の入口でログインし、ゴールの 1〜7 を確かめる（新しい会話でオクラを相談→登録まで、パネルの会話を一覧から続ける、題名変更、削除して 15 分後の取り込みのあとも `/conversations/` に出ない）
4. マージはユーザーが GitHub で行う → サーバーを main に戻す
