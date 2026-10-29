# Hermes に聞くパネル Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 植え付け・作物・品種の詳細画面の右から開くパネルで、見ている画面を前提に Hermes に相談・依頼でき、その会話を `/conversations/` にも出す。

**Architecture:** ブラウザ（ログイン中）→ アプリの中継ルート（Blueprint `hermes_ask`）→ Hermes の API Server（`127.0.0.1:8642`、`/v1/runs`）。対象ごとの Hermes の `session_id` はアプリの新しい表 `hermes_chats` で持つ。途中経過は Hermes の SSE をアプリが言い換えて SSE で中継する。一覧への取り込みは既存の同期スクリプトを `source='api_server'` にも広げる。

**Tech Stack:** Flask 3.1 / SQLite / 標準ライブラリの `urllib`（HTTP クライアントは新しく足さない）/ Bootstrap 5 の offcanvas / バニラ JS（`fetch` + `EventSource`）

**Spec:** `docs/superpowers/specs/2026-10-29-hermes-ask-panel-design.md`

## Global Constraints

- パネル・中継のルートはすべてログイン必須（`app/auth.py` の既定の拒否。GET のルートは `OWNER_ONLY_GET_ENDPOINTS` に足す）。POST は CSRF を照合（`csrf.js` が `fetch` に `X-CSRFToken` を付ける）
- Hermes の API Server のキー（`HERMES_API_KEY`）は HTML・JS・JSON・SSE のどこにも出さない
- 設定: `HERMES_API_URL`（既定 `http://127.0.0.1:8642`）、`HERMES_API_KEY`（未設定ならパネルを出さない）
- 道具の制限はしない（`platform_toolsets.api_server` は変えない）。承認はパネルで `once` / `deny` だけを返す（`session` / `always` は出さない）
- 対象の種類は `planting` / `crop` / `variety` の3つ。表と中継は「対象なし」（`entity_type IS NULL`）も扱えるようにするが、その入口の画面は作らない
- 依存パッケージを増やさない。外部の CDN を増やさない
- 改行コード: 既存ファイルは元の改行を保つ（`git ls-files --eol` で確認）、新規は LF。Python のテキストモードで書かない（Edit ツールを使う）
- 公開リポジトリ: 文書・コミットに実環境の固有値（IP、ユーザー名、ホスト名、パス）を書かない
- テストは `uv run python -m pytest`（Smart App Control が `pytest.exe` を止めることがある）。Hermes は呼ばず、`app.utils.hermes_client._open` を差し替える

## Review Focus

1. **Hermes が止まっている・キーが違う**: 質問を送ったら、パネルに「Hermes に届きません」（401 なら「Hermes のキーが合いません」）と出て、入力は消えない → Task 4 のテスト `test_start_run_hermes_down_returns_503`
2. **答えの途中で画面を移って戻る**: 戻ったときに、走っている run があれば続きの途中経過につながり、終わっていれば答えが履歴に出る → Task 4 のテスト `test_history_reports_running_run`
3. **対象のデータが消された・存在しない ID**: パネルの中継は 404 を返し、Hermes に何も送らない → Task 4 のテスト `test_unknown_target_404_and_nothing_sent`
4. **二重送信**（送るボタンの連打・通信の再送）: 同じ質問で run が2つ立たない → Task 4 のテスト `test_start_run_sends_idempotency_key`（キーはブラウザが送る1回ごとの値）と Task 5 の送信中のボタン無効化
5. **ログインしていない人・CSRF 無し**: 中継のすべてのルートが 401／400 で、Hermes に何も送らない → Task 4 のテスト `test_anonymous_rejected_and_nothing_sent`（既存の `tests/test_auth_gate.py` の分類テストにも通る）

---

### Task 0: 本番のサーバーで先に確かめる（実装の前・手作業）

Claude はサーバーを操作できない。コマンドを1段ずつ示し、結果を貼ってもらう。sudo を含むときは先頭に `sudo -v`、順番に意味がある複数のコマンドは `&&` でつなぐ。各段に「成功ならこう出る」を添えて照合する。結果は設計書の「先にサーバーで確かめること」の表に「結果」列として書き足してコミットする。**どれかがだめなら、Task 1 以降に進む前にユーザーと相談する。**

**Files:**
- Modify: `docs/superpowers/specs/2026-10-29-hermes-ask-panel-design.md`（結果を記録）
- Create（リポジトリの外）: `../garden-app-private/local-env.md` に API Server の実値（ポート、キーの置き場所）を追記

- [ ] **Step 1: Hermes の版**: `git -C ~/.hermes/hermes-agent log -1 --format='%h %ci'`。`73162b00ee` でなければ、その版をスクラッチに checkout し直し、`gateway/platforms/api_server_runs.py` の `_handle_runs` / `_handle_run_events` / `_handle_run_approval` と `website/docs/user-guide/features/api-server.md` を読み直して、以下の手順の値を合わせる
- [ ] **Step 2: 控えとキー**: `cp ~/.hermes/.env ~/.hermes/.env.bak-before-api-server && python3 -c "import secrets;print(secrets.token_urlsafe(32))"`。出たキーを `~/.hermes/.env` に `API_SERVER_ENABLED=true` と `API_SERVER_KEY=<キー>` で足す（ユーザーがエディタで。キーの値は貼らない。文字数だけ `grep -c '^API_SERVER_KEY=' ~/.hermes/.env` → `1`）
- [ ] **Step 3: gateway の再起動と待ち受け**: `systemctl --user restart hermes-gateway.service && sleep 5 && ss -ltnp | grep 8642`。期待: `127.0.0.1:8642` だけ（`0.0.0.0` や `*` が無い）。続けて Element X で「こんにちは」と送り、返事が来ること（Matrix が壊れていない）
- [ ] **Step 4: garden ユーザーから届くか**: `sudo -v && sudo -u garden curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8642/health`。期待: `200`。だめなら ufw のルールを見る（`sudo ufw status verbose`、`sudo grep -n 8642 /etc/ufw/*.rules`）。Hermes の実行ユーザーの 5000・443 の遮断は崩さない
- [ ] **Step 5: run を2回送って会話が続くか**: サーバーでキーを環境変数に読み（`export K=$(grep '^API_SERVER_KEY=' ~/.hermes/.env | cut -d= -f2-)`）、`session_id` を `garden-check-<今日の日付>` にして `POST /v1/runs`（`input`: 「テストです。数字の 7 を覚えておいて」、`instructions`: 「これは接続の確認です。道具は使わずに短く答えて」）→ `GET /v1/runs/{id}` を `completed` まで → 2回目（`input`: 「さっき覚えた数字は？」、同じ `session_id`）。期待: 2回目の `output` に 7。日本語の JSON は Write でファイルに書いて `--data-binary @file` で送る（`docs/dev-workflow-tips.md` の文字コードの節）
- [ ] **Step 6: SSE の形**: 3回目の run を送り、すぐ `curl -N -H "Authorization: Bearer $K" http://127.0.0.1:8642/v1/runs/<id>/events` を見る。`data:` 行の JSON の `event` の値（`tool.started` / `message.delta` / `run.completed` など）と、`tool.started` の項目名（`tool`, `preview`）、`run.completed` の `output` を記録する
- [ ] **Step 7: state.db の source と発言の取り方**: `sqlite3 -readonly ~/.hermes/state.db "SELECT id, source, parent_session_id FROM sessions WHERE id LIKE 'garden-check-%'"`。期待: `source` が `api_server`。`curl -s -H "Authorization: Bearer $K" 'http://127.0.0.1:8642/api/sessions/garden-check-<日付>/messages?inline_images=false' | head -c 1500` で発言の JSON の形（`role` / `content` / `tool_calls` / `tool_call_id` / `id` / `timestamp` の項目名）を記録する
- [ ] **Step 8: 承認待ち**: 4回目の run で `input` に「`rm -rf ~/garden-approval-check` を実行して（このフォルダは空のテスト用）」と送る（事前に `mkdir ~/garden-approval-check`）。events に `approval.request` が出て、`GET /v1/runs/{id}` が `waiting_for_approval` になること、その event の項目（`request_id`、コマンドの説明の項目名）を記録 → `POST /v1/runs/{id}/approval` に `{"choice":"deny"}` → run が続いて終わること
- [ ] **Step 9: 自動リセット**: `~/.hermes/config.yaml` の `session_reset` と、プラグイン `hermes-session-reset-policy` のソース（`~/.hermes/plugins/` の下）で、`session_id` を指定した API Server の run が対象になるかを読む。分からなければ、7時間後（`idle_minutes 360` を超えた後）に Step 5 の2回目と同じ質問を送って、7 を覚えているかで確かめる（その間に Task 1 以降を進めてよい。覚えていなければ Task 4 の前に相談）
- [ ] **Step 10: 記録してコミット**

```bash
git add docs/superpowers/specs/2026-10-29-hermes-ask-panel-design.md
git commit -m "Hermes の API Server をサーバーで確かめた結果を設計書に記録"
```

---

### Task 1: Hermes の API Server のクライアント

**Files:**
- Create: `app/utils/hermes_client.py`
- Modify: `app/config.py`（`Config` に `HERMES_API_URL` / `HERMES_API_KEY`）
- Test: `tests/test_hermes_client.py`

**Interfaces:**
- Produces:
  - `class HermesError(Exception)`（`.status: int | None`、`.message: str`）
  - `class HermesUnavailable(HermesError)`（接続できない・タイムアウト）
  - `is_configured() -> bool`（`current_app.config['HERMES_API_KEY']` が空でない）
  - `start_run(session_id: str, text: str, instructions: str, idempotency_key: str) -> str`（`POST /v1/runs`、返り値は `run_id`）
  - `get_run(run_id: str) -> dict`（`GET /v1/runs/{id}` の JSON）
  - `iter_events(run_id: str) -> Iterator[dict]`（`GET /v1/runs/{id}/events` の `data:` 行を JSON にして順に返す。`:` で始まる行と空行は飛ばす。`run.completed` / `run.failed` / `run.cancelled` / `run.interrupted` を返したら終わる）
  - `send_approval(run_id: str, choice: str, request_id: str | None) -> dict`（`choice` は `once` か `deny` だけ。それ以外は `ValueError`）
  - `get_session_messages(session_id: str) -> list[dict]`（`GET /api/sessions/{id}/messages?inline_images=false`。404 は空リスト）
  - `_open(req: urllib.request.Request, timeout: float)`（`urllib.request.urlopen` を呼ぶだけ。テストで差し替える）
- 値: 通常の要求のタイムアウト 15 秒、`iter_events` は 330 秒（keepalive が 10 秒ごとに来る）。ヘッダー `Authorization: Bearer <キー>`、POST は `Content-Type: application/json`、`start_run` は `Idempotency-Key: <idempotency_key>`。本文は `json.dumps(..., ensure_ascii=False).encode('utf-8')`
- Task 0 の Step 6〜8 で記録した項目名がソースの読みと違ったら、ここの値をそれに合わせる

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_hermes_client.py（要点。_open を差し替える FakeOpen は呼び出しを記録し、用意した応答を返す）
def test_start_run_sends_body_and_headers(app, fake_open):
    fake_open.reply(202, {'run_id': 'run_x', 'status': 'started'})
    with app.app_context():
        assert hermes_client.start_run('garden-planting-1-ab', '質問', '指示', 'idem-1') == 'run_x'
    req = fake_open.calls[0]
    assert req.full_url == 'http://127.0.0.1:8642/v1/runs'
    assert req.get_header('Authorization') == 'Bearer test-hermes-key'
    assert req.get_header('Idempotency-key') == 'idem-1'
    body = json.loads(req.data.decode('utf-8'))
    assert body == {'input': '質問', 'instructions': '指示', 'session_id': 'garden-planting-1-ab'}

def test_connection_error_is_unavailable(app, fake_open):
    fake_open.raise_(urllib.error.URLError('refused'))
    with app.app_context(), pytest.raises(HermesUnavailable):
        hermes_client.get_run('run_x')

def test_http_error_carries_status(app, fake_open):
    fake_open.reply(401, {'error': {'message': 'bad key'}})
    with app.app_context(), pytest.raises(HermesError) as e:
        hermes_client.get_run('run_x')
    assert e.value.status == 401

def test_iter_events_skips_keepalive_and_stops_at_terminal(app, fake_open):
    fake_open.stream([b': keepalive\n', b'\n',
                      b'data: {"event": "tool.started", "tool": "terminal"}\n', b'\n',
                      b'data: {"event": "run.completed", "output": "done"}\n', b'\n',
                      b'data: {"event": "never"}\n'])
    with app.app_context():
        events = list(hermes_client.iter_events('run_x'))
    assert [e['event'] for e in events] == ['tool.started', 'run.completed']

def test_send_approval_rejects_session_and_always(app):
    with app.app_context(), pytest.raises(ValueError):
        hermes_client.send_approval('run_x', 'always', None)

def test_get_session_messages_404_is_empty(app, fake_open):
    fake_open.reply(404, {'error': {'message': 'not found'}})
    with app.app_context():
        assert hermes_client.get_session_messages('garden-x') == []

def test_is_configured(app):
    with app.app_context():
        app.config['HERMES_API_KEY'] = ''
        assert hermes_client.is_configured() is False
```

共有のフィクスチャは `tests/hermes_fakes.py` に置き、各テストファイルで `from tests.hermes_fakes import fake_open, planting_id, crop_id, variety_id` のように import する（`pyproject.toml` の `pythonpath = ["."]` で `tests.api.helpers` と同じく import できる）:
- `fake_open(app, monkeypatch)`: `app.config['HERMES_API_KEY'] = 'test-hermes-key'` にし、`hermes_client._open` を差し替える。`.reply(status, json)` を積んだ順に返し、`.raise_(exc)` で例外、`.stream(lines)` で SSE の行を返す。`.calls` に `urllib.request.Request` を記録
- `planting_id` / `crop_id` / `variety_id`（`app` を使う）: 作物「玉ねぎ」、その品種「ネオアース」、場所「東の畑」、その品種の植え付けを作って ID を返す（Task 3〜6 で使う）

- [ ] **Step 2: 失敗を確かめる**: `uv run python -m pytest tests/test_hermes_client.py -v` → `ModuleNotFoundError: app.utils.hermes_client`
- [ ] **Step 3: `app/utils/hermes_client.py` と `Config` の2項目を実装する**（`Config.HERMES_API_URL = os.environ.get('HERMES_API_URL') or 'http://127.0.0.1:8642'`、`Config.HERMES_API_KEY = os.environ.get('HERMES_API_KEY') or ''`。HTTP の失敗は `urllib.error.HTTPError` を `HermesError(status=e.code)` に、`URLError` / `TimeoutError` / `ConnectionError` を `HermesUnavailable` に変える。ログにキーを出さない）
- [ ] **Step 4: 通ることを確かめる**: `uv run python -m pytest tests/test_hermes_client.py -v` → 全部 PASS
- [ ] **Step 5: コミット**

```bash
git add app/utils/hermes_client.py app/config.py tests/test_hermes_client.py tests/hermes_fakes.py
git commit -m "Hermes の API Server のクライアントを追加"
```

---

### Task 2: 対象ごとの会話の表（`hermes_chats`）

**Files:**
- Create: `app/migrations/026_add_hermes_chats.sql`、`app/models/hermes_chat.py`
- Modify: `app/models/CLAUDE.md`（表の定義）
- Test: `tests/test_hermes_chat_model.py`

**Interfaces:**
- 表 `hermes_chats`: `id INTEGER PK`、`entity_type TEXT`（`planting` / `crop` / `variety`、対象なしは NULL）、`entity_id INTEGER`（対象なしは NULL）、`session_id TEXT NOT NULL UNIQUE`、`active INTEGER NOT NULL DEFAULT 1`、`last_run_id TEXT`、`created_at` / `last_used_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))`。索引 `(entity_type, entity_id, active)`。`IF NOT EXISTS`（起動のたびに実行される）
- Produces（`app/models/hermes_chat.py`）:
  - `ENTITY_TYPES = ('planting', 'crop', 'variety')`
  - `HermesChat.get_or_create_active(entity_type: str | None, entity_id: int | None) -> dict`（active な行が無ければ作る）
  - `HermesChat.get_active(entity_type, entity_id) -> dict | None`
  - `HermesChat.start_new(entity_type, entity_id) -> dict`（今の active を 0 にして新しく作る）
  - `HermesChat.set_last_run(session_id: str, run_id: str) -> None`（`last_used_at` も更新）
  - `HermesChat.get_by_session_ids(session_ids: list[str]) -> dict[str, dict]`
  - `new_session_id(entity_type, entity_id) -> str`: `garden-{entity_type}-{entity_id}-{secrets.token_hex(8)}`、対象なしは `garden-free-{secrets.token_hex(8)}`

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_get_or_create_active_is_stable(app):
    with app.app_context():
        a = HermesChat.get_or_create_active('planting', 12)
        b = HermesChat.get_or_create_active('planting', 12)
        assert a['session_id'] == b['session_id']
        assert re.fullmatch(r'garden-planting-12-[0-9a-f]{16}', a['session_id'])

def test_targets_are_separate(app):
    with app.app_context():
        assert (HermesChat.get_or_create_active('planting', 12)['session_id']
                != HermesChat.get_or_create_active('planting', 13)['session_id'])

def test_start_new_replaces_active_and_keeps_old(app):
    with app.app_context():
        old = HermesChat.get_or_create_active('crop', 3)
        new = HermesChat.start_new('crop', 3)
        assert new['session_id'] != old['session_id']
        assert HermesChat.get_active('crop', 3)['session_id'] == new['session_id']
        assert set(HermesChat.get_by_session_ids([old['session_id'], new['session_id']])) == \
            {old['session_id'], new['session_id']}

def test_free_chat_has_no_target(app):
    with app.app_context():
        row = HermesChat.get_or_create_active(None, None)
        assert row['entity_type'] is None and row['session_id'].startswith('garden-free-')

def test_set_last_run(app):
    with app.app_context():
        row = HermesChat.get_or_create_active('variety', 5)
        HermesChat.set_last_run(row['session_id'], 'run_abc')
        assert HermesChat.get_active('variety', 5)['last_run_id'] == 'run_abc'
```

`entity_type IS NULL` の比較は `IS ?` で書く（`= NULL` は常に偽）。

- [ ] **Step 2: 失敗を確かめる**: `uv run python -m pytest tests/test_hermes_chat_model.py -v` → import エラー
- [ ] **Step 3: マイグレーションとモデルを実装する**（モデルは既存と同じ静的メソッドの形、`get_db()`）
- [ ] **Step 4: 通ることを確かめる**: 同じコマンドで PASS。`uv run python -m pytest tests/test_fresh_db_schema.py -v` も PASS
- [ ] **Step 5: コミット**

```bash
git add app/migrations/026_add_hermes_chats.sql app/models/hermes_chat.py app/models/CLAUDE.md tests/test_hermes_chat_model.py
git commit -m "Hermes に聞くパネルの会話の表 hermes_chats を追加"
```

---

### Task 3: 対象の説明と Hermes への指示、途中経過の言い換え

**Files:**
- Create: `app/utils/hermes_context.py`
- Test: `tests/test_hermes_context.py`

**Interfaces:**
- Consumes: `app.models.photo_pool._labels(db, entity_type, ids)`（ラベル）、`app.utils.conversation_links.extract_links(messages)`
- Produces:
  - `describe_target(entity_type: str, entity_id: int) -> dict | None`: `{'entity_type', 'entity_id', 'kind_label', 'label', 'api_path'}`。消えている・種類が違うなら None。`kind_label` は `植え付け` / `作物` / `品種`、`api_path` は `/plantings/{id}` / `/crops/{id}` / `/varieties/{id}`
  - `build_instructions(target: dict | None) -> str`
  - `friendly_tool_label(event: dict) -> str`: `tool.started` の event から「植え付けの情報を読んでいます」のような文。terminal の curl なら `preview` の URL から種類と方法（GET＝読んでいます、POST＝登録しています、PATCH＝更新しています）を拾う。拾えなければ「作業中…」。`web_search` 系は「Web で調べています」、`vision_analyze` は「写真を見ています」
  - `links_for_messages(messages: list[dict]) -> list[dict]`: Hermes の発言（Task 0 Step 7 で記録した形）を `extract_links` が受ける形（`role`, `content`, `tool_calls`（JSON 文字列）, `tool_call_id`, `hermes_message_id`）にそろえて渡し、結果を返す
- 指示の文面（`build_instructions` の対象ありの返り値。`{}` を埋める）:

```
ユーザーはアプリ（家庭菜園管理アプリ）の{kind_label}の画面を見ながら、画面の横のパネルから質問している。
見ている{kind_label}: {label}（id={entity_id}）
質問の主語や対象が省かれていたら、この{kind_label}のことと考える。
答える前に、API の GET {api_path} で中身を確かめる（植え付けなら栽培記録も）。
答えはパネルに表示されるので、Element X のときより少し短めにまとめる。
```

対象なし: `ユーザーはアプリ（家庭菜園管理アプリ）の画面のパネルから質問している。` の1行。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_describe_planting(app, planting_id):          # planting_id: 作物「玉ねぎ」品種「ネオアース」場所「東の畑」で作るフィクスチャ
    with app.app_context():
        t = describe_target('planting', planting_id)
    assert t['kind_label'] == '植え付け'
    assert t['api_path'] == f'/plantings/{planting_id}'
    assert '玉ねぎ' in t['label'] and '東の畑' in t['label']

def test_describe_missing_or_unknown_is_none(app):
    with app.app_context():
        assert describe_target('planting', 99999) is None
        assert describe_target('harvest', 1) is None

def test_instructions_contain_target(app, planting_id):
    with app.app_context():
        text = build_instructions(describe_target('planting', planting_id))
    assert f'id={planting_id}' in text and f'GET /plantings/{planting_id}' in text
    assert '省かれていたら' in text

def test_instructions_without_target():
    assert 'パネルから質問している' in build_instructions(None)

@pytest.mark.parametrize('preview,expected', [
    ('curl -s -H "Authorization: Bearer $GARDEN_API_TOKEN" http://127.0.0.1:5001/api/v1/plantings/12', '植え付けの情報を読んでいます'),
    ('curl -s -X POST http://127.0.0.1:5001/api/v1/tasks -d @t.json', 'タスクを登録しています'),
    ('curl -s -X PATCH http://127.0.0.1:5001/api/v1/diary_entries/3', '日記を更新しています'),
    ('ls -la', '作業中…'),
])
def test_friendly_tool_label_terminal(preview, expected):
    assert friendly_tool_label({'event': 'tool.started', 'tool': 'terminal', 'preview': preview}) == expected

def test_friendly_label_never_echoes_preview():
    label = friendly_tool_label({'event': 'tool.started', 'tool': 'terminal', 'preview': 'echo SECRET123'})
    assert 'SECRET123' not in label
```

種類の名前は API のパス（`/crops` 作物、`/varieties` 品種、`/locations` 場所、`/plantings` 植え付け、`/planting_records` 栽培記録、`/harvests` 収穫、`/cooking_records` 料理、`/diary_entries` 日記、`/tasks` タスク、`/advices` アドバイス、`/photos` 写真プール）から引く。

- [ ] **Step 2: 失敗を確かめる**: `uv run python -m pytest tests/test_hermes_context.py -v` → import エラー
- [ ] **Step 3: 実装する**（curl の解析は `conversation_links` の `_tokenize` / `_segments` / `_parse_curl` を使い、新しく書かない）
- [ ] **Step 4: 通ることを確かめる**: 同じコマンドで PASS
- [ ] **Step 5: コミット**

```bash
git add app/utils/hermes_context.py tests/test_hermes_context.py
git commit -m "Hermes に伝える対象の説明と途中経過の言い換えを追加"
```

---

### Task 4: 中継のルート（Blueprint `hermes_ask`）

**Files:**
- Create: `app/routes/hermes_ask_routes.py`
- Modify: `app/__init__.py`（Blueprint の登録、Jinja グローバル `hermes_ask_enabled`）、`app/auth.py`（`OWNER_ONLY_GET_ENDPOINTS` に GET の3つ）、`app/routes/CLAUDE.md`（URL 設計の表）
- Test: `tests/test_hermes_ask_routes.py`

**Interfaces:**
- Consumes: Task 1 の全部、Task 2 の `HermesChat`、Task 3 の `describe_target` / `build_instructions` / `friendly_tool_label` / `links_for_messages`、`app.utils.markdown_render.render_markdown`、`app.routes.photo_pool_routes.usage_url`
- Produces（すべて JSON。URL プレフィックス `/hermes/ask`）:

| メソッド・パス | エンドポイント | 内容 |
|---|---|---|
| GET `/<entity_type>/<int:entity_id>/history` | `hermes_ask.history` | `{ok, target: {kind_label, label}, messages: [{role, text, html, timestamp}], running_run_id}`。`html` は assistant だけ（`render_markdown`）。`running_run_id` は `last_run_id` の run が `queued` / `running` / `waiting_for_approval` のときだけ、それ以外は null |
| POST `/<entity_type>/<int:entity_id>/runs` | `hermes_ask.start` | 本文 `{text, request_key}`（`request_key` はブラウザが送信ごとに作る値。`Idempotency-Key` に `<session_id>:<request_key>` を渡す）→ `{ok, run_id}`。`text` が空、または 4000 文字を超えたら 400 |
| POST `/<entity_type>/<int:entity_id>/new` | `hermes_ask.new_chat` | `HermesChat.start_new` → `{ok}` |
| GET `/runs/<run_id>/events` | `hermes_ask.events` | `text/event-stream`。Hermes の event を言い換えて `data: <JSON>\n\n` で流す（下の表）。`X-Accel-Buffering: no`、`Cache-Control: no-cache` |
| GET `/runs/<run_id>` | `hermes_ask.run_status` | `{ok, status}` |
| POST `/runs/<run_id>/approval` | `hermes_ask.approval` | 本文 `{choice, request_id}`、`choice` は `once` / `deny` 以外 400 → `{ok}` |

- 中継する event（これ以外は流さない。Hermes の `preview` などの生の中身は流さない）:

| Hermes の event | ブラウザへ |
|---|---|
| `tool.started` | `{type: 'tool', label: friendly_tool_label(e)}` |
| `message.delta` | `{type: 'delta', text}` |
| `approval.request` | `{type: 'approval', request_id, command}`（項目名は Task 0 Step 8 の記録に合わせる） |
| `run.completed` | `{type: 'done', html: render_markdown(output), links: [{label, url, kind_label}]}`（links は `get_session_messages` の今回の run 分 → `links_for_messages` → `conversation_routes.link_items` と同じ整形） |
| `run.failed` / `run.cancelled` / `run.interrupted` | `{type: 'failed', error: '答えを受け取れませんでした（<状態>）'}` |

- `entity_type` が `ENTITY_TYPES` に無い、または `describe_target` が None なら 404（Hermes に何も送らない）
- `run_id` の中継（events / status / approval）は、その `run_id` が `hermes_chats.last_run_id` にあるものだけ受ける（それ以外は 404）
- Hermes の失敗: `HermesUnavailable` → 503 `{ok: false, error: 'Hermes に届きません'}`、`HermesError(status=401)` → 503 `'Hermes のキーが合いません'`、その他 → 502 `'Hermes でエラーが起きました'`。`HERMES_API_KEY` 未設定 → 503 `'Hermes への接続が設定されていません'`
- `hermes_ask_enabled()`（Jinja グローバル）は `is_owner() and hermes_client.is_configured()`

- [ ] **Step 1: 失敗するテストを書く**（`tests/hermes_fakes.py` の `fake_open` を使う）

```python
def test_anonymous_rejected_and_nothing_sent(anon_client, fake_open, planting_id):
    for method, path in [('get', f'/hermes/ask/planting/{planting_id}/history'),
                         ('post', f'/hermes/ask/planting/{planting_id}/runs'),
                         ('post', f'/hermes/ask/planting/{planting_id}/new'),
                         ('get', '/hermes/ask/runs/run_x'),
                         ('post', '/hermes/ask/runs/run_x/approval')]:
        resp = getattr(anon_client, method)(path, json={}, headers={'Accept': 'application/json'})
        assert resp.status_code in (400, 401)
    assert fake_open.calls == []

def test_start_run_sends_instructions_and_session(client, fake_open, planting_id):
    fake_open.reply(202, {'run_id': 'run_1', 'status': 'started'})
    resp = client.post(f'/hermes/ask/planting/{planting_id}/runs',
                       json={'text': 'そろそろ植え付けですかね？', 'request_key': 'k1'})
    assert resp.json == {'ok': True, 'run_id': 'run_1'}
    body = json.loads(fake_open.calls[0].data)
    assert body['session_id'].startswith(f'garden-planting-{planting_id}-')
    assert f'GET /plantings/{planting_id}' in body['instructions']

def test_start_run_sends_idempotency_key(client, fake_open, planting_id):
    fake_open.reply(202, {'run_id': 'run_1'})
    client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k1'})
    assert fake_open.calls[0].get_header('Idempotency-key').endswith(':k1')

def test_start_run_hermes_down_returns_503(client, fake_open, planting_id):
    fake_open.raise_(urllib.error.URLError('refused'))
    resp = client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k'})
    assert resp.status_code == 503 and resp.json['error'] == 'Hermes に届きません'

def test_unknown_target_404_and_nothing_sent(client, fake_open):
    assert client.post('/hermes/ask/planting/99999/runs', json={'text': 'q', 'request_key': 'k'}).status_code == 404
    assert client.post('/hermes/ask/harvest/1/runs', json={'text': 'q', 'request_key': 'k'}).status_code == 404
    assert fake_open.calls == []

def test_history_reports_running_run(client, fake_open, planting_id):
    fake_open.reply(202, {'run_id': 'run_1'})
    client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k'})
    fake_open.reply(200, [])                                  # get_session_messages
    fake_open.reply(200, {'run_id': 'run_1', 'status': 'running'})   # get_run
    data = client.get(f'/hermes/ask/planting/{planting_id}/history').json
    assert data['running_run_id'] == 'run_1'

def test_events_relay_only_translated(client, fake_open, planting_id):
    # run を開始 → events が tool.started(preview に秘密) / message.delta / run.completed
    ...
    text = resp.get_data(as_text=True)
    assert '"type": "tool"' in text and '"type": "done"' in text
    assert 'SECRET123' not in text and 'test-hermes-key' not in text

def test_approval_rejects_always(client, fake_open, planting_id):
    ...  # run を開始してから
    assert client.post('/hermes/ask/runs/run_1/approval', json={'choice': 'always'}).status_code == 400

def test_run_id_not_ours_404(client, fake_open):
    assert client.get('/hermes/ask/runs/run_someone_else').status_code == 404

def test_new_chat_changes_session(client, fake_open, planting_id):
    ...  # 2回の start の session_id が /new の前後で違う

def test_panel_hidden_without_key(client, app, planting_id):
    app.config['HERMES_API_KEY'] = ''
    assert 'hermes-ask-panel' not in client.get(f'/plantings/{planting_id}').get_data(as_text=True)
```

`test_events_relay_only_translated` と承認・新しい会話のテストは、上の2つと同じ作り方で書く（`...` の部分は start のテストと同じ前準備）。`test_panel_hidden_without_key` は Task 5 で通る（ここでは書いて失敗のままにせず、Task 5 の Step 1 に回す）。

- [ ] **Step 2: 失敗を確かめる**: `uv run python -m pytest tests/test_hermes_ask_routes.py -v` → 404（ルートが無い）
- [ ] **Step 3: Blueprint を実装し、登録と `OWNER_ONLY_GET_ENDPOINTS`（`hermes_ask.history`, `hermes_ask.events`, `hermes_ask.run_status`）を足す**。events は `stream_with_context` のジェネレーターで、Hermes との接続が切れたら `{type: 'failed', error: 'Hermes との接続が切れました'}` を流して終える。`run.completed` を受けたら `HermesChat.set_last_run` の `last_used_at` を更新する
- [ ] **Step 4: 通ることを確かめる**: `uv run python -m pytest tests/test_hermes_ask_routes.py tests/test_auth_gate.py tests/test_auth_csrf.py -v` → PASS
- [ ] **Step 5: コミット**

```bash
git add app/routes/hermes_ask_routes.py app/__init__.py app/auth.py app/routes/CLAUDE.md tests/test_hermes_ask_routes.py
git commit -m "Hermes に聞くパネルの中継のルートを追加"
```

---

### Task 5: パネルの画面（右から開く offcanvas）

**Files:**
- Create: `app/templates/_hermes_ask_panel.html`、`app/static/js/hermes-ask.js`、`app/static/css/hermes-ask.css`、`docs/frontend/hermes-ask-panel.md`
- Modify: `app/templates/plantings/detail.html`、`app/templates/crops/detail.html`、`app/templates/varieties/detail.html`（`{% include %}` を1行ずつ）、`app/templates/CLAUDE.md`（ガイド一覧表に1行）
- Test: `tests/test_hermes_ask_panel.py`

**Interfaces:**
- Consumes: Task 4 の URL と JSON の形
- 部品の呼び方: `{% set hermes_ask_target = ('planting', location_crop.id) %}{% include '_hermes_ask_panel.html' %}`（作物は `('crop', crop.id)`、品種は `('variety', variety.id)`）。部品の中で `{% if hermes_ask_enabled() %}` を判定する
- 見た目はモック A（設計書の「決まったこと」）: 右下の固定ボタン「Hermes に聞く」（`icon_hermes.webp`）→ Bootstrap 5 の `offcanvas offcanvas-end`、`data-bs-scroll="true" data-bs-backdrop="false"`（開いたまま画面をスクロールできる）。見出しに「Hermes に聞く」と「新しく始める」、その下に黄色の枠で「この植え付け: 〈label〉」、本文に日付の区切り付きの吹き出し、下に入力欄（`textarea`、Ctrl+Enter でも送る）と「送る」
- JS の振る舞い:
  - 開いたとき（初回だけ）に `history` を読み、吹き出しを並べる。`running_run_id` があれば events につなぐ
  - 送る: ボタンを無効にし、`request_key`（`crypto.randomUUID()`）付きで `runs` に POST → `EventSource` で events。`tool` は灰色の小さい行（最後の1行だけ残して上書き）、`delta` は答えの吹き出しに文字を足す、`approval` は「許可する」「しない」のボタン（押したら `approval` に POST し、ボタンを消す）、`done` は吹き出しを `html` に置き換え、`links` があれば「Hermes が作った・変えたデータ」のリンクを付ける、`failed` は赤い文字。終わったらボタンを戻す
  - 失敗（503 など）は入力欄の上に `error` の文を出し、入力した文は消さない
  - 「新しく始める」: 確認なしで `new` に POST し、吹き出しを空にする
  - 答えの吹き出しの `html` はサーバーで作ったものだけを `innerHTML` に入れる（`delta` の途中の文字は `textContent`）
- 新しい CDN は足さない。`hermes-ask.js` / `hermes-ask.css` は部品の中で読み込む（`extra_js` に手を入れずに済むよう、部品の末尾に `<script>` を置く）

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_panel_shown_for_owner_on_three_pages(client, planting_id, crop_id, variety_id):
    for path in (f'/plantings/{planting_id}', f'/crops/{crop_id}', f'/varieties/{variety_id}'):
        html = client.get(path).get_data(as_text=True)
        assert 'id="hermes-ask-panel"' in html and 'js/hermes-ask.js' in html

def test_panel_carries_target(client, planting_id):
    html = client.get(f'/plantings/{planting_id}').get_data(as_text=True)
    assert f'data-entity-type="planting"' in html and f'data-entity-id="{planting_id}"' in html

def test_panel_hidden_for_anonymous(anon_client, planting_id):
    assert 'hermes-ask-panel' not in anon_client.get(f'/plantings/{planting_id}').get_data(as_text=True)

def test_panel_hidden_without_key(client, app, planting_id):
    app.config['HERMES_API_KEY'] = ''
    assert 'hermes-ask-panel' not in client.get(f'/plantings/{planting_id}').get_data(as_text=True)

def test_key_not_in_page(client, planting_id):
    assert 'test-hermes-key' not in client.get(f'/plantings/{planting_id}').get_data(as_text=True)
```

- [ ] **Step 2: 失敗を確かめる**: `uv run python -m pytest tests/test_hermes_ask_panel.py -v` → FAIL
- [ ] **Step 3: 部品・JS・CSS を作り、3つの詳細画面に1行ずつ足す**（既存の改行コードを保つ）
- [ ] **Step 4: 通ることを確かめる**: `uv run python -m pytest -q` → 全体が PASS（HEIC の6件はスキップでよい）
- [ ] **Step 5: ブラウザで見た目を確かめる**: コピー DB のサーバー（`docs/dev-workflow-tips.md` の「実データ DB を汚さないブラウザ確認」）に `HERMES_API_URL` を、次の手順で動かす偽の Hermes に向けて起動する。偽の Hermes はスクラッチに置く小さい Flask（`/v1/runs` → `run_fake`、`/v1/runs/run_fake/events` → `tool.started`・`message.delta` を数回・`approval.request`・`run.completed` を1秒おきに流す、`/api/sessions/<id>/messages` → 空）。Chrome で、開く・スクロールしてもパネルが残る・送る・途中経過・承認ボタン・答えの Markdown・「新しく始める」・Hermes を止めたときの「Hermes に届きません」を確かめる。ログインは開発のパスキー（`http://localhost:5000` ではなくコピー DB のポート。パスキーの RP ID が `localhost` なら同じ `localhost` で開く）
- [ ] **Step 6: コミット**

```bash
git add app/templates/_hermes_ask_panel.html app/static/js/hermes-ask.js app/static/css/hermes-ask.css docs/frontend/hermes-ask-panel.md app/templates/CLAUDE.md app/templates/plantings/detail.html app/templates/crops/detail.html app/templates/varieties/detail.html tests/test_hermes_ask_panel.py
git commit -m "植え付け・作物・品種の詳細画面に Hermes に聞くパネルを追加"
```

---

### Task 6: 一覧への取り込みと、経路・対象の表示

**Files:**
- Modify: `tools/hermes_conversation_sync.py`（`select_sessions` の条件）、`app/routes/conversation_routes.py`（一覧・詳細に経路と対象を渡す）、`app/templates/conversations/list.html`、`app/templates/conversations/detail.html`、`docs/api/hermes-conversation-sync.md`
- Test: `tests/test_hermes_conversation_sync.py`（追記）、`tests/test_conversation_routes.py`（追記）

**Interfaces:**
- Consumes: Task 2 の `HermesChat.get_by_session_ids`、Task 3 の `describe_target`
- 同期: `WHERE source IN ('matrix', 'api_server')`（`api_server` の値は Task 0 Step 7 の記録に合わせる）。API Server の会話は圧縮で `session_id` が変わることがあるので、`garden-` での絞り込みはしない
- 画面: 一覧の各行と詳細の見出しに、経路のバッジ（`source == 'api_server'` なら「アプリ」、`matrix` なら「Element X」）と、対象（`HermesChat` の行が `hermes_id` で見つかればそれ、無ければ `parent_hermes_id` で見つかればそれ）の「植え付け: 〈label〉」とその詳細画面へのリンク。対象が消えていれば「（削除済み）」

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_hermes_conversation_sync.py
def test_selects_matrix_and_api_server(tmp_path):
    db = make_db(tmp_path)
    add_session(db, 'm', source='matrix'); add_session(db, 'garden-planting-1-aa', source='api_server')
    add_session(db, 'c', source='cli')
    conn = hs.open_db(str(db))
    assert sorted(r['id'] for r in hs.select_sessions(conn, {'sessions': {}})) == ['garden-planting-1-aa', 'm']

# tests/test_conversation_routes.py
def test_app_conversation_shows_source_and_target(client, planting_id):
    # HermesChat を planting_id で作り、その session_id で Conversation.upsert(source='api_server')
    ...
    html = client.get('/conversations/').get_data(as_text=True)
    assert 'アプリ' in html and f'/plantings/{planting_id}' in html

def test_matrix_conversation_badge(client):
    ...  # source='matrix' の会話の一覧に「Element X」
```

既存の `test_selects_only_matrix_and_changed` は名前と期待を新しい条件に合わせて直す（`cli` は選ばれないまま）。

- [ ] **Step 2: 失敗を確かめる**: `uv run python -m pytest tests/test_hermes_conversation_sync.py tests/test_conversation_routes.py -v` → FAIL
- [ ] **Step 3: 実装する**
- [ ] **Step 4: 通ることを確かめる**: 同じコマンドと `uv run python -m pytest -q` で PASS
- [ ] **Step 5: コミット**

```bash
git add tools/hermes_conversation_sync.py app/routes/conversation_routes.py app/templates/conversations/list.html app/templates/conversations/detail.html docs/api/hermes-conversation-sync.md tests/test_hermes_conversation_sync.py tests/test_conversation_routes.py
git commit -m "アプリのパネルでの会話も一覧に取り込み、経路と対象を表示"
```

---

### Task 7: SKILL.md・運用の文書・機能の説明

**Files:**
- Modify: `docs/api/hermes-skill/SKILL.md`（「アプリのパネルからの相談」の節）、`CLAUDE.md`（主な機能に「Hermes に聞くパネル」、「Hermes との会話の履歴」に経路が2つ）、`README.md`、`docs/wishlist.md`（この行を「作業2 完了」にし、「一覧からの自由な会話」「他の画面へのパネル」の2行を足す）
- Create: `docs/api/hermes-ask-panel.md`（本番の手順: キーの作り方、`~/.hermes/.env` と `/opt/garden-app/.env` の項目、gateway の再起動、`ss -ltnp` と `sudo -u garden curl …/health` での確かめ方、Task 0 で分かった注意。固有値は `<サーバーのIP>` などの記号）

- [ ] **Step 1: SKILL.md の節を書く**。内容: 指示（instructions）に「見ている画面」が書かれていたら、主語の省略はその対象のこととして扱う／答える前に API で中身を確かめる／アドバイスの保存は「相談・アドバイスの保存」と同じ決まり（同じパネルの会話の中の同じ話題は1件）／登録の依頼も Element X と同じ。具体的な日付などの毎回変わる値を例に入れない（`docs/dev-workflow-tips.md`）
- [ ] **Step 2: 残りの文書を更新する**
- [ ] **Step 3: 文書の固有値と改行を確かめる**: `git diff --name-only main...HEAD | xargs git ls-files --eol | grep crlf` で新しい CRLF が無いこと。`../garden-app-private/local-env.md` に書いた固有値（IP・ユーザー名・ホスト名・ローカルのパス）で `git diff main...HEAD` を grep し、何も出ないこと（grep のパターンはこの計画書やコミットに書かない）
- [ ] **Step 4: コミット**

```bash
git add docs/api/hermes-skill/SKILL.md docs/api/hermes-ask-panel.md CLAUDE.md README.md docs/wishlist.md
git commit -m "Hermes に聞くパネルの文書と SKILL.md を更新"
```

---

### Task 8: PR と本番での確認

- [ ] **Step 1: 全テスト**: `uv run python -m pytest -q` → PASS（HEIC の6件はスキップ）
- [ ] **Step 2: もう一人のレビュー**: `codex review --base main`（`docs/dev-workflow-tips.md` の「Codex をもう一人のレビュー役にする」）。指摘はコードで確かめてから直す
- [ ] **Step 3: push と PR**（`gh pr create`。本文の最後に `🤖 Generated with [Claude Code](https://claude.com/claude-code)`）
- [ ] **Step 4: 本番で確かめる**（`docs/api/migration-to-ubuntu.md` の「9. 更新の手順」。DB のバックアップを取ってからブランチに切り替え、マイグレーション 026 が通ること）: `/opt/garden-app/.env` に `HERMES_API_KEY`（Task 0 で作ったキー）を足して再起動 → PC の Chrome で `https://<サーバーのホスト名>.local/` にログイン → 玉ねぎの植え付けの画面で「そろそろ植え付けですかね？」→ 対象を取り違えずに答える／同じ画面を開き直すと履歴が出る／別の植え付けでは別の会話／「タスクに登録しておいて」でタスクができ、答えの下にリンク／承認ボタン（Task 0 Step 8 と同じ方法で）／HTTP の入口（`http://<サーバーのIP>:5000`）と未ログインではパネルが出ない／SKILL.md をサーバーに送り、Element X で `/new` してからも今までどおり動く／15分後に `/conversations/` に「アプリ」のバッジ付きで出る／承認待ちのまま別の画面へ移って戻ると承認ボタンが出て、返事を済ませたボタンは出直さない（「返事済み」の表示になる）／答えの途中で別の画面へ移って戻ると、続きが出て完了する／「タスクに登録しておいて」の答えの下にリンクが出る（run.completed の時点で Hermes が発言を保存済みかの確認）／一覧の会話の詳細に `instructions` の文が出ていない
- [ ] **Step 5: ユーザーがマージ → サーバーを main に戻す → 振り返りと worklog**（ルートの `CLAUDE.md` の「セッション終了時の振り返り」、`../garden-app-private/next.md` の更新）
