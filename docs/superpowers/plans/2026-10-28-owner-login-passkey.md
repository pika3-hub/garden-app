# 自分だけが編集できるようにする（パスキーでログイン）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Web 画面の登録・編集・削除を、パスキーでログインした自分だけに限る。家族はログインなしで今までどおり閲覧できる。

**Architecture:** Flask のセッション（署名付き Cookie、本番は `Secure`）に「どのパスキーでログインしたか」を持ち、`before_request` で「GET 以外と編集用の GET は、ログインしていなければ拒否」を一括で行う。CSRF はセッションのトークンを、ベースのレイアウトで読み込む `csrf.js` がすべての POST フォームと `fetch` に自動で付ける。パスキーは py_webauthn で検証し、新しい表 `passkeys` に保存する。最初の1つ目はサーバーの CLI が出す1回限りの URL で登録する。

**Tech Stack:** Flask 3.1、SQLite、py_webauthn（`webauthn`）、バニラ JS、pytest

**Spec:** `docs/superpowers/specs/2026-10-28-owner-login-passkey-design.md`

## Global Constraints

- 新しく足す依存は `webauthn` だけ（`uv add "webauthn==3.0.1"`。試作で動いた版）。Flask-Login・Flask-WTF・ProxyFix は使わない（ProxyFix を入れない理由: 判定は Cookie とセッションだけで、`request.scheme` を使わない。WebAuthn の origin は設定値と照合する。Flask の `redirect` は相対の `Location` を返す。HTTP の入口から `X-Forwarded-*` を偽装されても影響しない）
- 公開リポジトリ。コード・文書・コミットに実環境の値（IP・ホスト名・ユーザー名・パス）を書かない。`<サーバーのIP>`、`<サーバーのホスト名>` などの記号で書く
- 改行コード: 既存ファイルは `git ls-files --eol <file>` で元の改行を確かめて保つ。新規ファイルは LF。Python のテキストモード（`open(p, 'w')`、`Path.write_text`）で書かず、Edit / Write ツールを使う。コミット前に `git diff --name-only main...HEAD | xargs git ls-files --eol | grep crlf` で、CRLF だったファイル以外に CRLF が無いことを確かめる
- テストは `uv run python -m pytest`（`pytest.exe` は Smart App Control に止められることがある）。HEIC のテスト 6 件のスキップと Windows セキュリティの警告は正常
- ログインの有効期限は 180 日。非常口の URL の期限は 15 分
- 設定値（`app/config.py` で環境変数から読む）: `PASSKEY_RP_ID`（既定 `localhost`）、`PASSKEY_ORIGIN`（既定 `http://localhost:5000`）、`OWNER_BASE_URL`（ログインの入口。既定は `PASSKEY_ORIGIN` と同じ）、`SESSION_COOKIE_SECURE`（`ProductionConfig` は既定で真、`.env` の `SESSION_COOKIE_SECURE=0` で偽。`DevelopmentConfig`・`TestingConfig` は偽）
- Hermes 用の API（`create_api_app`、`app/api/`）には何も入れない
- UI の文言は日本語。既存の画面の書き方（Bootstrap 5、`bi` アイコン）に合わせる

## Review Focus

1. **ログインしていない人の POST が、どこか1か所でも通る**（新しいルート、`fetch` 用の JSON ルート、アップロード）→ すべて 401（JSON）か、ログイン画面への 302。Task 2 の「全 POST を機械的に試す」テストで固定する
2. **HTTP（`Secure` の Cookie が届かない）側の閲覧が壊れる**（セッションが保存できないことで 500 になる、ログインの案内のループ）→ 閲覧の GET は 200 のまま。Task 2 で `SESSION_COOKIE_SECURE=True` のアプリに HTTP で GET するテストを足す
3. **パスキーを消したのに、その端末のログインが残る** → 次のリクエストからログインしていない人になる。Task 2 のテスト
4. **非常口の URL の使い回し・期限切れ・別のトークン** → 2回目・期限後・違う値は登録できない。Task 1 と Task 3 のテスト
5. **フォームを JS で `form.submit()` したときに CSRF トークンが付かない**（`submit` イベントが起きない）→ `csrf.js` は読み込み時にすべての POST フォームへ隠し項目を入れておく（`submit` のときだけに頼らない）。Task 2 の手動確認と、テンプレートの `<script>` の読み込みのテスト

---

## ファイルの構成

| ファイル | 役割 |
|---|---|
| `app/migrations/025_add_passkeys.sql`（新規） | 表 `passkeys` |
| `app/models/passkey.py`（新規） | パスキーの CRUD と、非常口のトークン（`app_settings` に保存） |
| `app/auth.py`（新規） | ログインの判定、CSRF、`before_request` の拒否、Jinja グローバル、`init_auth(app)` |
| `app/routes/auth_routes.py`（新規） | Blueprint `auth`（`/auth`）: ログイン・ログアウト・パスキーの登録・名前の変更・削除・非常口の URL |
| `app/templates/auth/login.html`、`app/templates/auth/register.html`（新規） | ログイン画面、非常口の登録画面 |
| `app/static/js/csrf.js`（新規） | POST フォームへの隠し項目と、`fetch` へのヘッダーの自動付与 |
| `app/static/js/passkey.js`（新規） | ブラウザ側の WebAuthn（base64url の変換、登録・ログインのボタン） |
| `app/__init__.py` | `init_auth(app)` の呼び出し、Blueprint の登録、CLI `passkey-register-link` |
| `app/config.py` | 上の設定値 |
| `app/templates/base.html` | CSRF の `<meta>`、`csrf.js` の読み込み、ナビのログイン／ログアウト |
| `app/templates/settings/index.html` | 「パスキー」の欄 |
| 編集のボタンがあるテンプレート約30（`grep -rlE "url_for\('[a-z_]+\.(new|edit|delete|create|update)" app/templates` と `method="post"` のフォーム） | `{% if is_owner %}` で囲む |
| `tests/conftest.py` | 既定の `client` をログイン済み＋CSRF 自動付与に、`anon_client` を追加 |
| `tests/test_auth_*.py`（新規） | 下の各タスク |

---

### Task 1: パスキーの表とモデル

**Files:**
- Create: `app/migrations/025_add_passkeys.sql`, `app/models/passkey.py`, `tests/test_passkey_model.py`
- Modify: `pyproject.toml` / `uv.lock`（`uv add "webauthn==3.0.1"`）

**Interfaces:**
- Produces:
  - 表 `passkeys(id INTEGER PK, credential_id TEXT NOT NULL UNIQUE（base64url）, public_key TEXT NOT NULL（base64url）, sign_count INTEGER NOT NULL DEFAULT 0, name VARCHAR(100) NOT NULL, created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')), last_used_at TIMESTAMP)`。`CREATE TABLE IF NOT EXISTS`（起動のたびに実行されるため）
  - `class Passkey`（静的メソッド、既存モデルの書き方にならう）:
    - `create(credential_id: str, public_key: str, sign_count: int, name: str) -> int`
    - `get_by_id(passkey_id: int) -> dict | None`
    - `get_by_credential_id(credential_id: str) -> dict | None`
    - `get_all() -> list[dict]`（登録の古い順）
    - `count() -> int`
    - `record_use(passkey_id: int, sign_count: int) -> None`（`sign_count` と `last_used_at` を更新）
    - `rename(passkey_id: int, name: str) -> None`
    - `delete(passkey_id: int) -> None`
    - `issue_registration_token(ttl_minutes: int = 15) -> str`（`secrets.token_urlsafe(32)` を返し、SHA-256 のハッシュと期限（JST、ISO 形式）を `app_settings` のキー `passkey_registration_token_hash` / `passkey_registration_token_expires` に保存。前のトークンは上書きで無効になる）
    - `check_registration_token(token: str) -> bool`（消さずに確かめる。期限内でハッシュが一致すれば真。比較は `hmac.compare_digest`）
    - `consume_registration_token(token: str) -> bool`（確かめて、真なら2つのキーを消す）

- [ ] **Step 1: 依存を足す** — `uv add "webauthn==3.0.1"` → `uv run python -c "import webauthn, cryptography"` が通る
- [ ] **Step 2: 失敗するテストを書く**（`tests/test_passkey_model.py`、`app` フィクスチャの `app.app_context()` の中で）
  - `test_create_and_get`: `create('cid', 'pk', 0, 'PC')` の ID で `get_by_id` → `name == 'PC'`、`get_by_credential_id('cid')['id']` が同じ
  - `test_credential_id_unique`: 同じ `credential_id` の2回目は `sqlite3.IntegrityError`
  - `test_record_use_updates_count_and_time`: `record_use(id, 5)` → `sign_count == 5`、`last_used_at` が入る
  - `test_rename_and_delete`、`test_count`
  - `test_registration_token_single_use`: `t = issue_registration_token()` → `check(t)` 真 → `consume(t)` 真 → `consume(t)` 偽
  - `test_registration_token_wrong_value`: `consume('x')` 偽
  - `test_registration_token_expired`: `issue_registration_token(ttl_minutes=-1)` → `check` 偽
  - `test_registration_token_reissue_invalidates_old`: 2回発行すると1つ目は偽
- [ ] **Step 3: 失敗を確かめる** — `uv run python -m pytest tests/test_passkey_model.py -v` → `ModuleNotFoundError: app.models.passkey`
- [ ] **Step 4: マイグレーションとモデルを書く**（時刻は `app.utils.timezone.get_jst_now`）
- [ ] **Step 5: 通ることを確かめる** — 同じコマンドで全件 PASS。`uv run python -m pytest tests/test_fresh_db_schema.py -v` も PASS
- [ ] **Step 6: `app/models/CLAUDE.md` のテーブル一覧に `passkeys` を足し、`app_settings` の使用キーに2つを足す（`AppSettings` の docstring も）**
- [ ] **Step 7: コミット** — `パスキーの表とモデルを追加`

---

### Task 2: ログインの判定・既定で拒否・CSRF

**Files:**
- Create: `app/auth.py`, `app/static/js/csrf.js`, `tests/test_auth_gate.py`, `tests/test_auth_csrf.py`
- Modify: `app/__init__.py`, `app/config.py`, `app/templates/base.html`, `tests/conftest.py`

**Interfaces:**
- Consumes: `Passkey.get_by_id`
- Produces（`app/auth.py`）:
  - セッションのキー: `SESSION_PASSKEY_KEY = 'owner_passkey_id'`、`SESSION_CSRF_KEY = 'csrf_token'`
  - `current_passkey() -> dict | None`（セッションのパスキー ID が DB に残っていればその行。無ければセッションから消して `None`。結果は `g` にリクエストごとにキャッシュ）
  - `is_owner() -> bool`
  - `login_owner(passkey_id: int) -> None`（`session.clear()` してから ID を入れ、`session.permanent = True`。新しい CSRF トークンも作る）
  - `logout_owner() -> None`（`session.clear()`）
  - `csrf_token() -> str`（無ければ `secrets.token_urlsafe(32)` を作ってセッションに入れる）
  - `OWNER_ONLY_GET_ENDPOINTS: frozenset[str]` = `{'crops.new','crops.edit','varieties.new','varieties.edit','locations.new','locations.edit','locations.canvas','plantings.plant_new','plantings.new','plantings.bulk_new','plantings.edit','plantings.planting_edit','plantings.planting_edit_ended','plantings.place','harvests.new','harvests.edit','harvests.bulk_new','cooking.new','cooking.edit','diary.new','diary.edit','tasks.new','tasks.edit','advices.edit','photo_pool.use','photo_sort.index'}`
  - `ANONYMOUS_POST_ENDPOINTS: frozenset[str]` = `{'auth.login_options','auth.login_verify','auth.register_options','auth.register_verify'}`（Task 3 で作る。CSRF の照合は受ける）
  - `init_auth(app) -> None`: `PERMANENT_SESSION_LIFETIME = timedelta(days=180)`、`SESSION_COOKIE_HTTPONLY = True`、`SESSION_COOKIE_SAMESITE = 'Lax'` を設定。`before_request` を登録。Jinja グローバル `is_owner`・`csrf_token`・`owner_base_url`（`app.config['OWNER_BASE_URL']`）を登録
- `before_request` の振る舞い（`request.endpoint` が `None`・`static` は素通り）:
  1. メソッドが GET/HEAD/OPTIONS で、エンドポイントが `OWNER_ONLY_GET_ENDPOINTS` に無い → 素通り
  2. ログインしていない、かつエンドポイントが `ANONYMOUS_POST_ENDPOINTS` に無い → 拒否。JSON を期待する要求（`request.is_json`、または `Accept` が `application/json` を優先）なら `401` と `{"ok": false, "error": "ログインが必要です", "login_url": <ログイン画面の URL>}`。それ以外は `auth.login` へ 302（`next` に元の URL のパス。GET のときだけ）
  3. メソッドが GET 等以外 → CSRF を照合（ヘッダー `X-CSRFToken`、無ければフォームの `csrf_token`。`hmac.compare_digest`）。合わなければ `400`（JSON を期待するなら `{"ok": false, "error": "画面を開き直してから、もう一度操作してください"}`、それ以外は同じ文言の素の応答）
- `csrf.js`: `<meta name="csrf-token" content="...">` から読む。① `DOMContentLoaded` で `form[method=post]`（大文字小文字を問わず）すべてに `<input type="hidden" name="csrf_token">` を入れる、② `submit` イベント（キャプチャ）でも入っていなければ入れる（後から作られたフォーム用）、③ `window.fetch` を包み、同じオリジン宛ての GET/HEAD 以外のときに `X-CSRFToken` ヘッダーを足す（既存の `headers` を保つ。`Headers` / プレーンなオブジェクトの両方）
- `base.html`: `<head>` に `<meta name="csrf-token" content="{{ csrf_token() }}">`。`csrf.js` は他の JS より前に読み込む
- `tests/conftest.py`:
  - `client`（既定）: ログイン済み。DB に `Passkey.create('test-cred', 'test-pk', 0, 'テスト')` を作り、`session_transaction` で `owner_passkey_id` と `csrf_token` を入れる。`app.test_client_class` に、GET 以外の要求で `X-CSRFToken` を自動で付ける `FlaskClient` の派生クラスを使う（既存のテストを書き換えずに通すため）
  - `anon_client`: ログインしていない素の `app.test_client()`

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_auth_gate.py`）
  - `test_every_post_endpoint_rejects_anonymous`: `app.url_map` の GET 以外を受けるすべてのルール（`ANONYMOUS_POST_ENDPOINTS` を除く）に、変換子に `1` を入れた URL で `anon_client.post` → ステータスが `401` か、`302` で `Location` が `/auth/login` を含む
  - `test_owner_only_get_redirects_anonymous`: `OWNER_ONLY_GET_ENDPOINTS` の各 URL を `anon_client.get` → `302`、`/auth/login` へ
  - `test_get_endpoints_are_classified`: GET だけのルールのエンドポイントが、`OWNER_ONLY_GET_ENDPOINTS` か、テスト内に書いた閲覧用の一覧（`index`、`*.list`、`*.detail`、`calendar.index`、`conversations.*`、`locations.canvas_history`、`locations.canvas_history_range`、`locations.get_canvas_data`、`photo_pool.index`、`plantings.index`、`plantings.record_detail`、`settings.index`、`advices.list`、`advices.detail`、`auth.login`、`auth.register_page`）のどちらかに必ず入っている（新しいルートの分類漏れを防ぐ）
  - `test_view_pages_ok_for_anonymous`: `/`、`/crops/`、`/settings/`、`/calendar/` が `anon_client.get` で 200
  - `test_view_pages_ok_with_secure_cookie_over_http`: `SESSION_COOKIE_SECURE=True` にしたアプリで、`anon_client.get('/crops/')` が 200（HTTP の入口の再現）
  - `test_json_rejection_shape`: `anon_client.post('/settings/ai/notes-draft', json={})` → `401`、`json['ok'] is False`、`'login_url' in json`
  - `test_deleted_passkey_logs_out`: `client` でログイン済み → そのパスキーを `Passkey.delete` → `client.get('/crops/new')` が `302`
  - `test_owner_can_open_edit_pages`: `client.get('/crops/new')` が 200
  - `test_api_app_unaffected`: `tests/api` の既存のフィクスチャの作り方にならって `create_api_app` を作り、トークン付きの POST が今までどおり通る（CSRF も拒否もかからない）
- [ ] **Step 2: 失敗するテストを書く**（`tests/test_auth_csrf.py`）
  - `test_post_without_token_rejected_for_owner`: ログイン済みでも、ヘッダーもフォームの値も無い POST（素の `FlaskClient` で `session_transaction` だけ入れる）→ `400`
  - `test_post_with_form_token_ok`: フォームの `csrf_token` が正しければ通る（`/settings/` の POST で 302）
  - `test_post_with_wrong_header_rejected` → `400`
  - `test_base_template_has_meta_and_script`: `client.get('/')` の HTML に `name="csrf-token"` と `js/csrf.js` が含まれ、`csrf.js` が `main.js` より前にある
- [ ] **Step 3: 失敗を確かめる** — `uv run python -m pytest tests/test_auth_gate.py tests/test_auth_csrf.py -v` → `app.auth` が無い・401 にならない等で FAIL（`auth.*` のエンドポイントは Task 3 までは存在しないので、分類のテストは一覧に存在しないものを無視する書き方にする）
- [ ] **Step 4: `app/auth.py`・設定・`init_auth` の呼び出し（`create_app` の Blueprint 登録の前）・`base.html`・`csrf.js`・`conftest.py` を実装する**
- [ ] **Step 5: 通ることを確かめる** — 上の2ファイルと、**全テスト** `uv run python -m pytest` が PASS（既存のテストが既定の `client` で通ること）
- [ ] **Step 6: 手動確認**（コピー DB で `run.py` 相当を起動。`docs/dev-workflow-tips.md` の「実データ DB を汚さないブラウザ確認」）: ログインしていない状態で `/crops/new` がログイン画面へ回ること（Task 3 前は 404 でよい）。CSRF は Task 3 のログイン後にまとめて確かめる
- [ ] **Step 7: コミット** — `ログインしていない人の編集を拒否し、CSRF 対策を入れる`

---

### Task 3: パスキーのログイン・登録・管理と非常口

**Files:**
- Create: `app/routes/auth_routes.py`, `app/templates/auth/login.html`, `app/templates/auth/register.html`, `app/static/js/passkey.js`, `tests/test_auth_routes.py`
- Modify: `app/__init__.py`（Blueprint 登録、CLI）, `app/templates/settings/index.html`, `app/templates/base.html`（ナビ）

**Interfaces:**
- Consumes: `Passkey.*`、`login_owner`、`logout_owner`、`is_owner`、`current_passkey`
- Produces（Blueprint `auth`、`url_prefix='/auth'`）:
  - `GET /auth/login` → `auth.login`（ログイン画面。`next` を受ける。ログイン済みなら `next` か `/` へ。`request.host_url` が `OWNER_BASE_URL` と違えば「編集は `{{ owner_base_url }}` で」とリンクを出し、ボタンは出さない）
  - `POST /auth/login/options` → `auth.login_options`（JSON。`generate_authentication_options(rp_id=…, user_verification=REQUIRED)`、`allow_credentials` なし。チャレンジを `session['webauthn_challenge']` に）
  - `POST /auth/login/verify` → `auth.login_verify`（JSON。`credential_id` で `Passkey` を探し、`verify_authentication_response(..., require_user_verification=True)`、`record_use`、`login_owner`。成功で `{"ok": true, "redirect": next か "/"}`、失敗で `400` と `{"ok": false, "error": ...}`。チャレンジは使ったら消す）
  - `POST /auth/logout` → `auth.logout`（ログイン中だけ。`/` へ 302）
  - `GET /auth/register/<token>` → `auth.register_page`（`check_registration_token` が真ならトークンを `session['registration_token']` に入れて登録画面、偽なら 404 相当の案内）
  - `POST /auth/passkeys/register/options` → `auth.register_options`（ログイン中か、セッションのトークンが `check` で真のときだけ。`generate_registration_options(resident_key=REQUIRED, user_verification=REQUIRED, attestation=none, user_id=b'garden-owner', user_name='owner', exclude_credentials=既存全部)`）
  - `POST /auth/passkeys/register/verify` → `auth.register_verify`（JSON の本文に `credential` と `name`（端末名。空なら「パスキー N」））。`verify_registration_response(..., require_user_verification=True)` → `Passkey.create`。ログインしていない（非常口）ときは、このときに `consume_registration_token` し、`login_owner` する
  - `POST /auth/passkeys/<int:passkey_id>/rename` → `auth.rename_passkey`、`POST /auth/passkeys/<int:passkey_id>/delete` → `auth.delete_passkey`（フォーム、設定画面へ 302、`flash`）
  - RP の設定は `current_app.config['PASSKEY_RP_ID']` / `['PASSKEY_ORIGIN']`、`rp_name='家庭菜園'`
- CLI（`app/__init__.py`、既存の `relink-conversations` の隣）: `flask --app app passkey-register-link [--base-url URL]` → `Passkey.issue_registration_token()` して `{base_url}/auth/register/{token}` と「15分以内に1回だけ使えます」を表示。`--base-url` の既定は `OWNER_BASE_URL`
- `passkey.js`: 試作（設計書の「試作で確かめたこと」）と同じ方法で、`ArrayBuffer` ↔ base64url を変換して `navigator.credentials.create/get` を呼び、JSON で送る。`data-passkey-action="login|register"` のボタンに付く。`window.isSecureContext` と `window.PublicKeyCredential` が無ければボタンを無効にして理由を出す。エラーは画面の `alert` 要素に表示（`alert()` は使わない）
- 設定画面の「パスキー」の欄: ログイン中は一覧（名前・登録日・最後に使った日・名前の変更・削除）と「この端末のパスキーを追加」（端末名の入力つき）。最後の1つの削除は `confirm` 付き。ログインしていない人には一覧の件数だけ
- ナビ（`base.html`）: 右端に、ログインしていなければ「ログイン」（`owner_base_url` の `/auth/login`）、ログイン中なら「ログアウト」（POST のフォーム）

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_auth_routes.py`。`monkeypatch.setattr('app.routes.auth_routes.verify_authentication_response', fake)` などで差し替える。差し替える関数の引数名は `inspect.signature` で実物と一致させる）
  - `test_login_flow`: `anon_client` で `/auth/login` を GET（CSRF トークン取得）→ `login/options` → 偽の検証が `new_sign_count=3` を返す → `login/verify` に登録済みの `credential_id` → `ok` と `redirect`、以後 `/crops/new` が 200、`record_use` で `sign_count == 3`
  - `test_login_unknown_credential`: 未登録の `credential_id` → `400`
  - `test_login_verify_failure`: 偽の検証が例外 → `400`、ログインしていないまま
  - `test_login_challenge_single_use`: 同じチャレンジで2回目の `verify` → `400`
  - `test_register_requires_login_or_token`: ログインもトークンも無い `register/options` → `401`/`302`
  - `test_emergency_link_registers_and_logs_in`: `Passkey.issue_registration_token()` → `/auth/register/<t>` が 200 → `register/options` → 偽の検証 → `register/verify` → `Passkey.count() == 1`、ログイン済み、トークンは使用済み（もう一度 `/auth/register/<t>` が 200 でない）
  - `test_emergency_link_expired`: `ttl_minutes=-1` のトークンの登録画面は 200 でない
  - `test_owner_adds_passkey`: ログイン済みで登録 → 件数が増え、`name` が保存される
  - `test_rename_and_delete_passkey`: 設定画面からの POST で名前が変わる・消える
  - `test_logout`: ログアウト後 `/crops/new` が `302`
  - `test_login_page_on_other_origin_shows_link`: `OWNER_BASE_URL='https://example.local'` のアプリで `/auth/login` を GET → HTML に `https://example.local/auth/login` が含まれ、ボタン（`data-passkey-action="login"`）が無い
  - `test_cli_register_link`: `app.test_cli_runner().invoke(args=['passkey-register-link', '--base-url', 'https://x.local'])` の出力に `https://x.local/auth/register/` が含まれ、そのトークンで `check_registration_token` が真
- [ ] **Step 2: 失敗を確かめる** — `uv run python -m pytest tests/test_auth_routes.py -v` → 404 などで FAIL
- [ ] **Step 3: ルート・テンプレート・`passkey.js`・CLI・設定画面・ナビを実装する**
- [ ] **Step 4: 通ることを確かめる** — `tests/test_auth_routes.py` と全テストが PASS（Task 2 の分類のテストで `auth.*` も分類済みになる）
- [ ] **Step 5: 手動確認**（コピー DB、`http://localhost:5000`、RP ID `localhost`。PC の Windows Hello で）: CLI で URL を出す → 開いて登録 → ログアウト → ログイン → 編集画面が開ける → 作物を1件保存できる（CSRF がフォームで通る）→ AI 下書き以外の `fetch`（見取り図の保存）が通る → 設定画面でパスキーの名前の変更・削除 → 削除後はログインしていない。ブラウザのコンソールにエラーが無いこと。顔認証はユーザーに頼む
- [ ] **Step 6: コミット** — `パスキーでのログイン・登録・管理と非常口のコマンドを追加`

---

### Task 4: ログインしていない人には編集の入口を出さない

**Files:**
- Modify: 編集・削除・登録のボタンやフォームがあるテンプレート（`grep -rlE "url_for\('[a-z_]+\.(new|edit|delete|create|update|bulk_new|plant_new|place|canvas)" app/templates` と `grep -rliE 'method="post"' app/templates` の和。`_photo_pool_picker_modal.html`・`_ai_notes_button.html`・`_supplements_section.html` などの共通部品も含む）
- Create: `tests/test_auth_ui.py`

**Interfaces:**
- Consumes: Jinja グローバル `is_owner()`

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_auth_ui.py`。作物・品種・場所・植え付け・栽培記録・収穫・料理・日記・タスク・アドバイス・補足情報（テキスト1件）・写真プール（1件）を、既存のテストのデータの作り方にならって用意する）
  - `test_anonymous_sees_no_edit_controls`: 各一覧・各詳細・設定・写真プール・ダッシュボードを `anon_client.get` → HTML に `method="post"`（大文字小文字を問わず。ただしナビの「ログイン」以外）と、`OWNER_ONLY_GET_ENDPOINTS` の各エンドポイントへの `href` が無い
  - `test_owner_sees_edit_controls`: 同じ画面を `client.get` → 詳細画面に編集のリンクがある（代表として作物の詳細に `/crops/<id>/edit`）
- [ ] **Step 2: 失敗を確かめる** — `uv run python -m pytest tests/test_auth_ui.py -v` → FAIL
- [ ] **Step 3: テンプレートを `{% if is_owner() %}` で囲む**（ボタンの並びが崩れないよう、囲むのはボタン・フォーム・モーダルの単位。閲覧用のボタン（スライドショー、フルスクリーン、前後の移動）は残す）
- [ ] **Step 4: 通ることを確かめる** — `tests/test_auth_ui.py` と全テスト
- [ ] **Step 5: 手動確認**（コピー DB）: ログインしていない状態とログイン中で、ダッシュボード・各一覧・各詳細・写真プール・設定を見比べ、閲覧用の操作は残り、編集の入口だけ消えていること。スマホ幅（375px）でも崩れないこと
- [ ] **Step 6: コミット** — `ログインしていない人には編集の入口を出さない`

---

### Task 5: 文書とサーバーの手順

**Files:**
- Modify: `CLAUDE.md`（「認証なし」の記述 → 閲覧は誰でも・編集はパスキーでログインした自分だけ。主な機能に「ログイン（パスキー）」、`.env` の新しい値）、`app/routes/CLAUDE.md`（URL 設計表に `auth`、新しいルートの規約: GET 以外は自動で拒否・編集用の GET は `OWNER_ONLY_GET_ENDPOINTS` に足す・分類のテストが落ちたら分類する・JS の送信は `csrf.js` が自動で付ける）、`app/templates/CLAUDE.md` か該当の `docs/frontend/*.md`（`is_owner()` で編集の入口を囲む規約）、`README.md`、`docs/api/migration-to-ubuntu.md`（新しい節: avahi（導入済みの設定）、Caddy のサイト、ufw の 443 番の許可、Hermes の 443 番の拒否（`-o lo` 付き）、`.env`（`PASSKEY_RP_ID`・`PASSKEY_ORIGIN`・`OWNER_BASE_URL`・`WEB_BASE_URL` を HTTPS に・`SECRET_KEY` の確認）、sudo の確認（`sudo -l`、`/etc/sudoers.d/`）、非常口のコマンド（`sudo -u garden -H bash -c 'cd /opt/garden-app && ~/.local/bin/uv run flask --app app passkey-register-link'`）、確認のコマンドと成功時の出力）、`docs/api/hermes-local-chat.md`（Caddy に Web アプリのサイトが増えたこと、`.local` の名前）
- 実環境の値は記号で書く

- [ ] **Step 1: 上の文書を更新する**
- [ ] **Step 2: 固有値の混入を確かめる** — `git diff main --stat` と、`git diff main | grep -E "192\.168|<実際のホスト名>"` が空（実際のホスト名は `../garden-app-private/local-env.md` で確かめ、コマンドにだけ使う）
- [ ] **Step 3: コミット** — `パスキーでのログインの文書とサーバーの手順を追加`

---

### Task 6: 本番での確認（メインのセッションがユーザーと行う。サブエージェントには渡さない）

- [ ] PR を作る（`codex review --base main` も任意で）
- [ ] サーバー: 読み取りの確認（`sudo -l`、`/etc/sudoers.d/`、`.env` の `SECRET_KEY` の有無）→ バックアップ → PR のブランチに切り替え → `uv sync` → `.env` に値を足す → Caddy のサイトと ufw（443 番の許可、Hermes の拒否）→ 再起動
- [ ] 非常口の URL で PC のパスキーを登録 → iPhone（この端末のパスキーを追加）→ iPad（5G、iCloud で同期されたパスキーでログイン）
- [ ] 家族の閲覧（`http://<サーバーのIP>:5000`）が今までどおりで、編集の入口が無く、POST が拒否されること
- [ ] Hermes の実行ユーザーで `curl -k https://127.0.0.1/` と `curl https://<サーバーのホスト名>.local/` が拒否され、`curl -sI https://example.com` は通ること。Element X で Hermes に1件依頼し、返事のリンクが HTTPS で開けること。Hermes の記憶（`~/.hermes/memories/MEMORY.md`）に古い URL が無いか `grep`
- [ ] マージはユーザー → サーバーを main に戻して再起動
