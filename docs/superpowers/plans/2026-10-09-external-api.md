# 外部登録・更新API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** エージェント（Hermes）が Bearer トークンで作物・品種・場所・植え付け・栽培記録・収穫・料理・日記・タスク・写真プールを参照・作成・部分更新できる JSON API を、既存Web画面とは別ポートで提供する。

**Architecture:** `app/api/` パッケージに Blueprint `api`（`/api/v1`）を置き、API Blueprint だけを持つ別アプリ `create_api_app()` を作る。`server.py` は waitress 1プロセスで 5000（Web）と `API_PORT`（API）を待ち受け、`PortDispatcher` が `SERVER_PORT` でアプリを振り分ける。各リソースは共通基底 `Resource`（一覧・詳細・作成・部分更新・追加画像）に項目定義とフックを宣言するだけにし、既存モデルの `create`/`update` を再利用する（モデル層は `Planting.end_cultivation` の追加以外は変更しない）。

**Tech Stack:** Python 3.12, Flask 3.1, SQLite, Pillow 12, waitress 3, pytest（uv 管理）

**Spec:** `docs/superpowers/specs/2026-10-09-external-api-design.md`

## Global Constraints

- 新しい依存パッケージは追加しない（Flask / Pillow / waitress / python-dotenv の範囲で書く）
- `instance/garden.db`（実データ）には一切触れない。テストは tmp_path の DB、手動確認はコピー DB
- テスト実行は `uv run python -m pytest`（Smart App Control で `pytest.exe` がブロックされるため）
- CRLF のまま登録されているファイル（`server.py`, `app/models/location.py`, `app/routes/planting_routes.py` など）は編集後も CRLF を保つ。Edit ツールを使い、編集後に `git diff --stat` で差分行数を確認する
- API のメッセージ（`message` / `reason`）は日本語。項目名はフィールド名そのまま（`planted_date` など）
- API の項目名は DB カラム名を基本とし、`location_crop_id` だけは `planting_id` と呼ぶ
- DELETE / PUT は定義しない（405）。植え付けの `status` は API から直接変更しない（終了は `/end`）
- `API_TOKEN` は32文字以上必須。未設定・短い場合 `create_api_app()` は `RuntimeError`、`server.py` は Web のみで起動する
- 既定値: `API_HOST=127.0.0.1`, `API_PORT=5001`, `API_MAX_IMAGE_MB=20`, `WEB_BASE_URL=http://localhost:5000`、API の `MAX_CONTENT_LENGTH`=100MB、1リクエストの画像は20枚まで、画素数上限 50,000,000
- 一覧の `limit` は既定50・最大200
- コミットメッセージは日本語、末尾に `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 作業ブランチは `feature/external-api`（作成済み）

## Review Focus

1. **拡張子が無い・実形式と違う写真**（Telegram の `file_123`、`IMG_0001.JPG` の中身が PNG など）→ 中身で判定して受け付け、実形式の拡張子で保存する（Task 4 のテスト）
2. **数値を文字列で送る / 単位付きで送る**（`"quantity": "300"` は受理、`"300g"` は「数値で指定してください」の 422）（Task 3 のテスト）
3. **桁あふれする巨大な ID**（本文の `crop_id: 99999999999999999999`、パスの `/crops/99999999999999999999`）→ 500 ではなく 422 / 404（Task 3・Task 5 のテスト）
4. **品種の名前だけを PATCH** → 継承中の `icon_path` / `image_color` / `image_path` が NULL のまま残り、親作物の値がコピーされない（Task 6 のテスト）
5. **検索語に `%` や `_` を含む** → ワイルドカードではなく文字として扱う（Task 6 の `/lookup` と一覧 `q` のテスト）

---

## File Structure

| ファイル | 責務 |
|---|---|
| `app/config.py`（変更） | `DATABASE` の環境変数上書き、`API_TOKEN` / `API_MAX_IMAGE_MB` / `WEB_BASE_URL` |
| `app/__init__.py`（変更） | `create_api_app()` を追加 |
| `app/port_dispatch.py`（新規） | `PortDispatcher`：待受ポートで WSGI アプリを振り分け |
| `server.py`（変更、CRLF） | Web と API を1つの waitress で2ポート起動 |
| `app/api/__init__.py` | Blueprint `bp`、`init_app()`（エラーハンドラー・認証・監査ログ・ルート読み込み） |
| `app/api/errors.py` | `ApiError`、`detail()`、`validation_error()`、`ok()`、エラーハンドラー登録 |
| `app/api/auth.py` | トークン検証 |
| `app/api/validation.py` | `Field` / `Ref`、`check_value()`、`check_ref_id()`、`validate_payload()` |
| `app/api/payload.py` | JSON / multipart 本文の読み取り `parse_request()` |
| `app/api/images.py` | 画像検証 `check_image()`、`ImageInputs`、`SavedFiles`、本体画像・追加画像の保存 |
| `app/api/serialize.py` | 日付等の JSON 化、`web_url()` / `image_url()`、`planting_label()` |
| `app/api/choices.py` | 選択肢（ステータス・天気・アイコン一覧・既存値の DISTINCT・関連キー） |
| `app/api/resource.py` | `Resource` 基底クラス、`register()`、一覧・詳細・作成・部分更新・追加画像の共通処理、`page_arg()`、`like_pattern()` |
| `app/api/relations.py` | 日記・料理・タスクの関連の読み書き、`RelationsMixin` |
| `app/api/meta.py` | `/health`、`/meta`、`/lookup` |
| `app/api/crops.py` ほか | 各リソースの定義（crops, varieties, locations, plantings, planting_records, harvests, cooking_records, diary_entries, tasks, photos） |
| `app/models/planting.py`（変更） | `Planting.end_cultivation()` を追加（画面と API で共用） |
| `app/routes/planting_routes.py`（変更、CRLF） | `end_cultivation` ルートを `Planting.end_cultivation()` 呼び出しに置き換え |
| `tests/api/helpers.py`, `tests/api/conftest.py` | API テスト用のトークン・フィクスチャ・画像生成 |
| `tests/api/test_api_*.py` | 段階ごとのテスト |
| `docs/api/README.md`, `docs/api/curl-examples.md`, `docs/api/firewall-windows.md`, `docs/api/migration-to-ubuntu.md`, `docs/api/hermes-skill/SKILL.md` | ドキュメント |

---

### Task 1: API アプリの土台（設定・認証・エラー形式・/health）

**Files:**
- Modify: `app/config.py`
- Modify: `app/__init__.py`（末尾に `create_api_app` を追加）
- Create: `app/api/__init__.py`, `app/api/errors.py`, `app/api/auth.py`, `app/api/meta.py`
- Create: `tests/api/helpers.py`, `tests/api/conftest.py`, `tests/api/test_api_app.py`
- Create: `docs/api/curl-examples.md`

**Interfaces:**
- Produces:
  - `create_api_app(config_name='default') -> Flask`（`app/__init__.py`）
  - `app.api.bp`（Blueprint、`url_prefix='/api/v1'`）、`app.api.init_app(app)`
  - `ApiError(status:int, code:str, message:str, details:list|None=None)`
  - `detail(field:str, reason:str, value=None) -> dict`
  - `validation_error(details:list) -> ApiError`（422）
  - `ok(data, status=200, meta=None) -> (Response, int)`
  - `token_is_valid(token) -> bool`、`MIN_TOKEN_LENGTH = 32`
  - 監査ログ: `g.api_target_id` に対象 ID を入れると `app.api` ロガーに出る
  - テスト: `TOKEN`, フィクスチャ `api_app`, `api`（認証付き）, `anon`（認証なし）, `sql`

- [ ] **Step 1: テストヘルパーとフィクスチャを書く**

`tests/api/helpers.py`:

```python
import io
import json

from PIL import Image

TOKEN = 'test-token-' + 'x' * 32


def image_bytes(fmt='PNG', size=(8, 8)):
    """テスト用の小さな画像（バイト列）"""
    buf = io.BytesIO()
    Image.new('RGB', size, (200, 50, 50)).save(buf, fmt)
    return buf.getvalue()


def file_part(data, filename):
    """test_client の multipart 用ファイル指定"""
    return (io.BytesIO(data), filename)


def multipart(payload=None, **files):
    """{'data': JSON文字列, <ファイル名>: (stream, filename) or [...]} を作る"""
    form = dict(files)
    if payload is not None:
        form['data'] = json.dumps(payload, ensure_ascii=False)
    return form
```

`tests/api/conftest.py`:

```python
import pytest

from app import create_api_app
from app.config import config, TestingConfig
from app.database import get_db
from tests.api.helpers import TOKEN


@pytest.fixture
def api_app(tmp_path, monkeypatch):
    """tmp_path 上の使い捨て DB で API アプリを生成する（instance/garden.db には触れない）"""
    class ApiTestConfig(TestingConfig):
        DATABASE = str(tmp_path / 'test.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        API_TOKEN = TOKEN
        API_MAX_IMAGE_MB = 1
        WEB_BASE_URL = 'http://garden.test:5000'

    assert 'garden.db' not in ApiTestConfig.DATABASE
    monkeypatch.setitem(config, 'api_pytest', ApiTestConfig)
    return create_api_app('api_pytest')


@pytest.fixture
def api(api_app):
    client = api_app.test_client()
    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {TOKEN}'
    return client


@pytest.fixture
def anon(api_app):
    return api_app.test_client()


@pytest.fixture
def sql(api_app):
    """SQL を1文実行する。SELECT は dict のリスト、それ以外は lastrowid を返す"""
    def run(query, params=()):
        with api_app.app_context():
            db = get_db()
            cur = db.execute(query, params)
            db.commit()
            if query.lstrip().upper().startswith('SELECT'):
                return [dict(r) for r in cur.fetchall()]
            return cur.lastrowid
    return run
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/api/test_api_app.py`:

```python
import os
import subprocess
import sys

import pytest

from app import create_api_app
from app.config import config, TestingConfig


def test_health_requires_token(anon):
    res = anon.get('/api/v1/health')
    assert res.status_code == 401
    body = res.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'unauthorized'
    assert '認証'.encode() in res.data  # 日本語がエスケープされない


def test_health_rejects_wrong_token(anon):
    res = anon.get('/api/v1/health', headers={'Authorization': 'Bearer wrong-token'})
    assert res.status_code == 401


def test_health_ok(api):
    res = api.get('/api/v1/health')
    assert res.status_code == 200
    assert res.get_json() == {'ok': True, 'data': {'status': 'ok'}}


def test_unknown_path_is_json_404(api):
    res = api.get('/api/v1/nothing-here')
    assert res.status_code == 404
    assert res.get_json()['error']['code'] == 'not_found'


@pytest.mark.parametrize('path', ['/', '/crops/', '/static/css/custom.css'])
def test_web_routes_are_not_served(api, path):
    res = api.get(path)
    assert res.status_code == 404
    assert res.is_json


def test_delete_is_not_allowed(api):
    res = api.delete('/api/v1/health')
    assert res.status_code == 405
    assert res.get_json()['error']['code'] == 'method_not_allowed'


def test_internal_error_hides_details(api_app, api):
    def boom():
        raise ZeroDivisionError('secret detail')
    api_app.add_url_rule('/api/v1/_boom', 'boom', boom)
    res = api.get('/api/v1/_boom')
    assert res.status_code == 500
    assert res.get_json()['error']['code'] == 'internal_error'
    assert b'secret detail' not in res.data


@pytest.mark.parametrize('token', [None, '', 'short-token'])
def test_create_api_app_requires_long_token(tmp_path, monkeypatch, token):
    class NoTokenConfig(TestingConfig):
        DATABASE = str(tmp_path / 'test.db')
        API_TOKEN = token

    monkeypatch.setitem(config, 'api_no_token', NoTokenConfig)
    with pytest.raises(RuntimeError):
        create_api_app('api_no_token')


def test_database_path_can_be_overridden_by_env(tmp_path):
    target = str(tmp_path / 'elsewhere.db')
    env = {**os.environ, 'DATABASE': target}
    out = subprocess.run(
        [sys.executable, '-c', 'from app.config import Config; print(Config.DATABASE)'],
        env=env, capture_output=True, text=True, check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )
    assert out.stdout.strip() == target
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `uv run python -m pytest tests/api/test_api_app.py -v`
Expected: FAIL（`ImportError: cannot import name 'create_api_app'`）

- [ ] **Step 4: 設定を追加する**

`app/config.py` の `Config` を次のように変更（`DATABASE` 行の置き換えと末尾への追加）:

```python
class Config:
    """基本設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # 起動ディレクトリに依存しないよう、絶対パスで上書きできる（Ubuntu 移設時の systemd 用）
    DATABASE = os.environ.get('DATABASE') or os.path.join(os.getcwd(), 'instance', 'garden.db')

    # アップロード設定
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 256 * 1024 * 1024  # 256MB（写真プールの一括アップロード対応）
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # 外部API（app/api/）。API_TOKEN が無い・32文字未満なら API アプリは起動しない
    API_TOKEN = os.environ.get('API_TOKEN')
    API_MAX_IMAGE_MB = int(os.environ.get('API_MAX_IMAGE_MB') or 20)
    # レスポンスの web_url / image_url の基準（スマホから開ける Web 画面の URL）
    WEB_BASE_URL = os.environ.get('WEB_BASE_URL') or 'http://localhost:5000'
```

- [ ] **Step 5: エラー形式・認証・Blueprint を書く**

`app/api/errors.py`:

```python
"""API の共通レスポンス形式とエラーハンドラー"""
from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """API のエラー。エラーハンドラーが {"ok": false, "error": {...}} に変換する"""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def detail(field, reason, value=None):
    """エラー詳細1件。value は長い文字列なら切り詰める"""
    item = {'field': field, 'reason': reason}
    if value is not None:
        if isinstance(value, str) and len(value) > 100:
            value = value[:100] + '…'
        item['value'] = value
    return item


def validation_error(details):
    return ApiError(422, 'validation_error', f'入力内容に誤りがあります（{len(details)}件）', details)


def ok(data, status=200, meta=None):
    body = {'ok': True, 'data': data}
    if meta is not None:
        body['meta'] = meta
    return jsonify(body), status


def error_response(status, code, message, details=None):
    error = {'code': code, 'message': message}
    if details:
        error['details'] = details
    return jsonify({'ok': False, 'error': error}), status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(e):
        return error_response(e.status, e.code, e.message, e.details)

    @app.errorhandler(404)
    def _not_found(e):
        return error_response(404, 'not_found',
                              '指定された URL はありません。使えるリソースは GET /api/v1/meta で確認してください')

    @app.errorhandler(405)
    def _method_not_allowed(e):
        return error_response(405, 'method_not_allowed',
                              'この URL では使えないメソッドです（API からの削除はできません）')

    @app.errorhandler(413)
    def _too_large(e):
        return error_response(413, 'too_large', 'リクエストが大きすぎます（1回のリクエストは合計100MBまで）')

    @app.errorhandler(Exception)
    def _unexpected(e):
        if isinstance(e, HTTPException):
            code = 'bad_request' if e.code == 400 else 'http_error'
            return error_response(e.code or 500, code, e.description or e.name)
        current_app.logger.exception('API で想定外のエラー')
        return error_response(500, 'internal_error', 'サーバー内部でエラーが発生しました')
```

`app/api/auth.py`:

```python
"""Bearer トークン認証"""
import hmac

from flask import current_app, request

from app.api.errors import ApiError

MIN_TOKEN_LENGTH = 32


def token_is_valid(token):
    return bool(token) and len(token) >= MIN_TOKEN_LENGTH


def require_token():
    """before_request: Authorization: Bearer <API_TOKEN> を必須にする"""
    expected = current_app.config.get('API_TOKEN') or ''
    scheme, _, given = request.headers.get('Authorization', '').partition(' ')
    given = given.strip()
    if (scheme.lower() != 'bearer' or not given or not expected
            or not hmac.compare_digest(given.encode(), expected.encode())):
        raise ApiError(401, 'unauthorized', '認証に失敗しました。Authorization: Bearer <トークン> を付けてください')
```

`app/api/meta.py`:

```python
"""疎通確認・選択肢一覧・名前検索"""
from app.api import bp
from app.api.errors import ok


@bp.get('/health')
def health():
    return ok({'status': 'ok'})
```

`app/api/__init__.py`:

```python
"""外部API（エージェント連携用）。create_api_app() からのみ登録する

既存の Web 画面（認証なし）とは別アプリ・別ポートで動かし、
エージェントからは /api/v1/* にしか到達できないようにする。
"""
import logging

from flask import Blueprint, g, request

bp = Blueprint('api', __name__, url_prefix='/api/v1')
audit_logger = logging.getLogger('app.api')


def init_app(app):
    from app.api import auth, errors
    # 各モジュールは import 時に bp へルートを登録する（Blueprint 登録より前に読み込む）
    from app.api import meta  # noqa: F401

    errors.register_error_handlers(app)
    app.before_request(auth.require_token)
    app.after_request(_audit_log)
    app.register_blueprint(bp)


def _audit_log(response):
    """書き込み系リクエストを記録する（トークン・本文は出さない）"""
    if request.method in ('POST', 'PATCH'):
        audit_logger.info('%s %s %s -> %s id=%s', request.remote_addr, request.method,
                          request.path, response.status_code, g.get('api_target_id', '-'))
    return response
```

- [ ] **Step 6: `create_api_app` を追加する**

`app/__init__.py` の末尾（`create_app` の後）に追加:

```python
def create_api_app(config_name='default'):
    """外部API専用アプリ（/api/v1/* のみ。画面ルート・static 配信は持たない）

    server.py が Web アプリとは別ポートで起動する。
    API_TOKEN が未設定・32文字未満なら RuntimeError（API を無認証で公開しないため）。
    """
    from app.api import init_app as init_api
    from app.api.auth import token_is_valid

    app = Flask(__name__, static_folder=None)
    app.config.from_object(config[config_name])
    if not token_is_valid(app.config.get('API_TOKEN')):
        raise RuntimeError('API_TOKEN が未設定か32文字未満のため、API を起動できません')
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    init_db(app)
    init_api(app)

    # 監査ログ（app.api）を Flask の 'app' ロガーのハンドラーへ伝播させる
    app.logger  # 既定ハンドラーを生成
    logging.getLogger('app.api').setLevel(logging.INFO)
    return app
```

- [ ] **Step 7: テストが通ることを確認**

Run: `uv run python -m pytest tests/api/test_api_app.py -v`
Expected: PASS（全件）。続けて `uv run python -m pytest` で既存テストも PASS。

- [ ] **Step 8: curl 例のファイルを作る**

`docs/api/curl-examples.md`:

````markdown
# API の curl 例

段階ごとの動作確認用。エージェント PC（Ubuntu）またはメイン PC の Git Bash で実行する。

```bash
# Windows 暫定期（移設後は http://127.0.0.1:5001/api/v1）
export GARDEN_API_URL=http://192.168.11.24:5001/api/v1
export GARDEN_API_TOKEN='（.env の API_TOKEN）'
gapi() { curl -sS -H "Authorization: Bearer $GARDEN_API_TOKEN" "$@"; echo; }
```

## 疎通確認

```bash
gapi "$GARDEN_API_URL/health"
# → {"ok": true, "data": {"status": "ok"}}
curl -sS "$GARDEN_API_URL/health"   # トークンなし → 401
```
````

- [ ] **Step 9: コミット**

```bash
git add app/config.py app/__init__.py app/api tests/api docs/api/curl-examples.md
git commit -m "外部API: API専用アプリの土台（認証・エラー形式・/health）を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 2ポート起動（PortDispatcher と server.py）

**Files:**
- Create: `app/port_dispatch.py`
- Modify: `server.py`（CRLF を保つ）
- Test: `tests/test_port_dispatch.py`

**Interfaces:**
- Consumes: `create_app`, `create_api_app`（Task 1）
- Produces: `PortDispatcher(default_app, port_apps: dict[int, wsgi_app])`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_port_dispatch.py`:

```python
import threading
import urllib.request

from waitress import create_server

from app.port_dispatch import PortDispatcher


def _app(body):
    def wsgi(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [body]
    return wsgi


def test_dispatches_by_server_port():
    d = PortDispatcher(_app(b'web'), {5001: _app(b'api')})
    calls = []
    sr = lambda status, headers: calls.append(status)  # noqa: E731
    assert d({'SERVER_PORT': '5001'}, sr) == [b'api']
    assert d({'SERVER_PORT': '5000'}, sr) == [b'web']
    assert d({}, sr) == [b'web']


def test_waitress_listening_port_selects_app():
    """実際の waitress で、待受ポートごとに別アプリが応答することを確かめる（安全性の要）"""
    holder = {}
    server = create_server(lambda e, s: holder['app'](e, s),
                           listen='127.0.0.1:0 127.0.0.1:0', threads=2)
    (_, web_port), (_, api_port) = server.effective_listen
    holder['app'] = PortDispatcher(_app(b'web'), {api_port: _app(b'api')})
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        assert urllib.request.urlopen(f'http://127.0.0.1:{api_port}/', timeout=5).read() == b'api'
        assert urllib.request.urlopen(f'http://127.0.0.1:{web_port}/', timeout=5).read() == b'web'
    finally:
        server.close()
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/test_port_dispatch.py -v`
Expected: FAIL（`ModuleNotFoundError: app.port_dispatch`）

- [ ] **Step 3: 実装**

`app/port_dispatch.py`:

```python
"""1つの waitress で複数ポートを待ち受け、ポートごとに WSGI アプリを振り分ける

waitress は environ['SERVER_PORT'] に「接続を受けた待受ソケットのポート」を入れる
（Host ヘッダーではない）ため、クライアントが偽装できない。
"""


class PortDispatcher:
    def __init__(self, default_app, port_apps):
        self.default_app = default_app
        self.port_apps = {str(port): app for port, app in port_apps.items()}

    def __call__(self, environ, start_response):
        app = self.port_apps.get(str(environ.get('SERVER_PORT')), self.default_app)
        return app(environ, start_response)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run python -m pytest tests/test_port_dispatch.py -v`
Expected: PASS

- [ ] **Step 5: server.py を書き換える（CRLF を保つ）**

`server.py` 全体を次の内容にする（Edit ツールで置き換え、改行は CRLF のまま）:

```python
import logging
import os

from dotenv import load_dotenv
from waitress import serve

# app/config.py は import 時に環境変数を読むため、app より先に .env を読み込む
load_dotenv()

from app import create_app, create_api_app  # noqa: E402
from app.port_dispatch import PortDispatcher  # noqa: E402

config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)


def build_api_app():
    """API_TOKEN が正しく設定されていれば API アプリを返す。無ければ None（Web 画面のみで起動）"""
    try:
        return create_api_app(config_name)
    except RuntimeError as e:
        logging.getLogger(__name__).warning('%s（Web 画面のみ起動します）', e)
        return None


if __name__ == "__main__":
    # 既定はこのPCのみ。スマホ等 LAN 内の端末から使う場合は .env に HOST=0.0.0.0 を書く
    host = os.environ.get('HOST', '127.0.0.1')
    api_app = build_api_app()
    if api_app is None:
        serve(app, host=host, port=5000, threads=10)
    else:
        # API は別ポート。Ubuntu 移設後は API_HOST=127.0.0.1（同じPCのエージェントだけが使う）
        api_host = os.environ.get('API_HOST', '127.0.0.1')
        api_port = int(os.environ.get('API_PORT', '5001'))
        serve(PortDispatcher(app, {api_port: api_app}),
              listen=f'{host}:5000 {api_host}:{api_port}', threads=10)
```

確認: `grep -c $'\r' server.py` が行数と同じ（CRLF）、`git diff --stat server.py` が妥当な行数。

- [ ] **Step 6: 起動確認（コピー DB）**

スクラッチ領域で `instance/garden.db` をコピーし、`DATABASE` を向けて起動する（実データ DB は使わない）:

```bash
cp instance/garden.db "$SCRATCH/garden_copy.db"
DATABASE="$SCRATCH/garden_copy.db" API_TOKEN="$(uv run python -c 'import secrets;print(secrets.token_urlsafe(32))')" \
  API_PORT=5061 uv run python server.py   # run_in_background で起動
```

（ポート 5000 が既存サーバーで埋まっている場合は先に `netstat -ano | grep LISTEN | grep :5000` で確認し、使用中なら確認を後回しにして Task 13 でまとめて行う）

期待: `curl -sS http://127.0.0.1:5061/api/v1/health -H "Authorization: Bearer <token>"` が `{"ok": true, ...}`、`curl -sS http://127.0.0.1:5061/` が JSON の 401、`http://127.0.0.1:5000/` が HTML。確認後にサーバーを止める。

- [ ] **Step 7: コミット**

```bash
git add app/port_dispatch.py server.py tests/test_port_dispatch.py
git commit -m "外部API: waitress 1プロセスで Web と API を別ポート起動する

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 入力検証（validation.py）

**Files:**
- Create: `app/api/validation.py`
- Test: `tests/api/test_api_validation.py`

**Interfaces:**
- Consumes: `detail()`（Task 1）
- Produces:
  - `Ref(table, label, hint)`、定数 `REF_CROP`, `REF_VARIETY`, `REF_LOCATION`, `REF_PLANTING`, `REF_HARVEST`, `REF_PHOTO`
  - `Field(kind, required=False, max_len=None, min_value=None, choices=None, ref=None, column=None)`、kind は `'str' | 'int' | 'decimal' | 'date' | 'enum' | 'color' | 'ref'`
  - `SQLITE_MAX_INT = 2**63 - 1`
  - `check_value(field, value) -> (converted, reason|None)`
  - `check_ref_id(ref, value) -> (id|None, reason|None)`
  - `validate_payload(fields, payload, *, creating, reserved=(), read_only=()) -> (cleaned: dict, errors: list)`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_validation.py`:

```python
import pytest

from app.api.validation import (
    REF_CROP, Field, check_ref_id, check_value, validate_payload,
)


@pytest.mark.parametrize('field, value, expected', [
    (Field('str', max_len=5), 'トマト', 'トマト'),
    (Field('int'), 3, 3),
    (Field('int'), '3', 3),            # 文字列の数字も受け付ける
    (Field('int'), 3.0, 3),
    (Field('decimal'), '300', 300.0),
    (Field('decimal'), 1.5, 1.5),
    (Field('date'), '2026-10-09', '2026-10-09'),
    (Field('enum', choices=['a', 'b']), 'b', 'b'),
    (Field('color'), '#4caf50', '#4caf50'),
    (Field('str'), '', None),          # 空文字は「値を消す」
    (Field('str'), None, None),
])
def test_check_value_accepts(field, value, expected):
    assert check_value(field, value) == (expected, None)


@pytest.mark.parametrize('field, value, reason_part', [
    (Field('str', max_len=3), 'ミニトマト', '3文字以内'),
    (Field('str'), 123, '文字列'),
    (Field('int'), True, '整数'),
    (Field('int'), '3株', '整数'),
    (Field('int'), 10**30, '大きすぎ'),
    (Field('decimal'), '300g', '数値'),        # 単位付きは不可
    (Field('decimal'), float('nan'), '数値'),
    (Field('decimal', min_value=0), -1, '0 以上'),
    (Field('date'), '2026/10/09', 'YYYY-MM-DD'),
    (Field('date'), '2026-02-30', 'YYYY-MM-DD'),  # 実在しない日付
    (Field('enum', choices=['active', 'harvested']), 'done', 'active, harvested'),
    (Field('enum', choices=[f'icon_{i}.png' for i in range(30)]), 'x.png', 'GET /api/v1/meta'),
    (Field('color'), 'green', '#RRGGBB'),
    (Field('str', required=True), None, '必須'),
    (Field('str', required=True), '  ', '必須'),
])
def test_check_value_rejects(field, value, reason_part):
    converted, reason = check_value(field, value)
    assert converted is None
    assert reason_part in reason


def test_check_ref_id(api_app, sql):
    crop_id = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    with api_app.app_context():
        assert check_ref_id(REF_CROP, crop_id) == (crop_id, None)
        assert check_ref_id(REF_CROP, str(crop_id)) == (crop_id, None)
        _, reason = check_ref_id(REF_CROP, 999)
        assert 'ID 999 の作物は存在しません' in reason
        assert '/api/v1/lookup' in reason
        _, reason = check_ref_id(REF_CROP, 99999999999999999999)  # 桁あふれでも 500 にしない
        assert '存在しません' in reason
        _, reason = check_ref_id(REF_CROP, 'トマト')
        assert '整数の ID' in reason


FIELDS = {
    'name': Field('str', required=True, max_len=100),
    'notes': Field('str'),
}


def test_validate_payload_create_reports_all_errors():
    cleaned, errors = validate_payload(FIELDS, {'notes': 1, 'nmae': 'x', 'id': 3},
                                       creating=True, reserved=('photo_pool_id',),
                                       read_only=('id',))
    by_field = {e['field']: e['reason'] for e in errors}
    assert '文字列' in by_field['notes']
    assert '未知の項目' in by_field['nmae']
    assert 'name, notes, photo_pool_id' in by_field['nmae']
    assert '読み取り専用' in by_field['id']
    assert by_field['name'] == '必須項目です'
    assert cleaned == {}


def test_validate_payload_patch_only_checks_sent_fields():
    cleaned, errors = validate_payload(FIELDS, {'notes': '花が咲いた'}, creating=False)
    assert errors == []
    assert cleaned == {'notes': '花が咲いた'}


def test_validate_payload_skips_reserved_keys():
    cleaned, errors = validate_payload(FIELDS, {'name': 'a', 'relations': {}},
                                       creating=True, reserved=('relations',))
    assert errors == []
    assert cleaned == {'name': 'a'}


def test_validate_payload_includes_bad_value():
    _, errors = validate_payload({'d': Field('date')}, {'d': '10/9'}, creating=False)
    assert errors == [{'field': 'd', 'reason': errors[0]['reason'], 'value': '10/9'}]
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_validation.py -v`
Expected: FAIL（`ModuleNotFoundError: app.api.validation`）

- [ ] **Step 3: 実装**

`app/api/validation.py`:

```python
"""API 入力の検証。項目定義（Field）に沿って型変換し、誤りを details 形式で集める"""
import math
import re
from dataclasses import dataclass
from datetime import date

from app.api.errors import detail
from app.database import get_db

SQLITE_MAX_INT = 2**63 - 1
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
_INT_RE = re.compile(r'^-?\d+$')
_LONG_CHOICES = 10  # 選択肢がこれより多ければメッセージに列挙せず /meta へ案内する


@dataclass(frozen=True)
class Ref:
    """参照先（存在チェック用）"""
    table: str
    label: str
    hint: str  # 見つからないときの案内


REF_CROP = Ref('crops', '作物', 'GET /api/v1/lookup?q=名前 で検索してください')
REF_VARIETY = Ref('varieties', '品種', 'GET /api/v1/lookup?q=名前 で検索してください')
REF_LOCATION = Ref('locations', '場所', 'GET /api/v1/lookup?q=名前 で検索してください')
REF_PLANTING = Ref('plantings', '植え付け', 'GET /api/v1/plantings?q=作物名 で検索してください')
REF_HARVEST = Ref('harvests', '収穫', 'GET /api/v1/harvests?planting_id=... で検索してください')
REF_PHOTO = Ref('photo_pool', '写真プールの写真', 'GET /api/v1/photos で一覧を確認してください')


@dataclass(frozen=True)
class Field:
    """書き込める項目の定義"""
    kind: str                  # 'str' | 'int' | 'decimal' | 'date' | 'enum' | 'color' | 'ref'
    required: bool = False
    max_len: int | None = None
    min_value: float | None = None
    choices: object = None     # enum の選択肢（list か、list を返す関数）
    ref: Ref | None = None     # ref の参照先
    column: str | None = None  # DB カラム名が API の項目名と違うとき


def _to_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and _INT_RE.match(value.strip()):
        return int(value.strip())
    return None


def _to_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _ref_exists(ref, obj_id):
    if obj_id < 1 or obj_id > SQLITE_MAX_INT:
        return False
    return get_db().execute(f'SELECT 1 FROM {ref.table} WHERE id = ?', (obj_id,)).fetchone() is not None


def check_ref_id(ref, value):
    """参照 ID を検証して (id, None) か (None, 理由) を返す"""
    obj_id = _to_int(value)
    if obj_id is None:
        return None, '整数の ID で指定してください'
    if not _ref_exists(ref, obj_id):
        return None, f'ID {obj_id} の{ref.label}は存在しません。{ref.hint}'
    return obj_id, None


def check_value(field, value):
    """(変換後の値, 誤りの理由 or None) を返す。空文字・null は None（必須なら誤り）"""
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None, ('必須項目です' if field.required else None)

    kind = field.kind
    if kind == 'str':
        if not isinstance(value, str):
            return None, '文字列で指定してください'
        if field.max_len and len(value) > field.max_len:
            return None, f'{field.max_len}文字以内で指定してください（現在 {len(value)} 文字）'
        return value, None

    if kind in ('int', 'decimal'):
        number = _to_int(value) if kind == 'int' else _to_number(value)
        if number is None:
            return None, '整数で指定してください' if kind == 'int' else '数値で指定してください（単位は付けない）'
        if abs(number) > SQLITE_MAX_INT:
            return None, '値が大きすぎます'
        if field.min_value is not None and number < field.min_value:
            return None, f'{field.min_value:g} 以上で指定してください'
        return number, None

    if kind == 'date':
        if isinstance(value, str) and _DATE_RE.match(value):
            try:
                date.fromisoformat(value)
                return value, None
            except ValueError:
                pass
        return None, 'YYYY-MM-DD 形式の実在する日付で指定してください（例: 2026-10-09）'

    if kind == 'enum':
        choices = field.choices() if callable(field.choices) else field.choices
        if value in choices:
            return value, None
        if len(choices) > _LONG_CHOICES:
            return None, '使える値ではありません。GET /api/v1/meta で一覧を確認してください'
        return None, f'次のいずれかで指定してください: {", ".join(choices)}'

    if kind == 'color':
        if isinstance(value, str) and _COLOR_RE.match(value):
            return value, None
        return None, '#RRGGBB 形式で指定してください（例: #4CAF50）'

    if kind == 'ref':
        return check_ref_id(field.ref, value)

    raise ValueError(f'unknown field kind: {kind}')


def _scalar(value):
    return value if isinstance(value, (str, int, float, bool)) else None


def validate_payload(fields, payload, *, creating, reserved=(), read_only=()):
    """payload を検証して (cleaned, errors) を返す

    - creating=True なら必須項目の欠落も誤りにする（PATCH では送られた項目だけ検証）
    - reserved は画像・関連など、呼び出し側が別に検証するキー
    - 誤りは最初の1件で止めず、すべて errors に積む
    """
    cleaned, errors = {}, []
    usable = [*fields, *reserved]
    for key, value in payload.items():
        if key in reserved:
            continue
        if key in read_only:
            errors.append(detail(key, '読み取り専用の項目のため変更できません'))
            continue
        field = fields.get(key)
        if field is None:
            errors.append(detail(key, f'未知の項目です。使える項目: {", ".join(usable)}'))
            continue
        converted, reason = check_value(field, value)
        if reason:
            errors.append(detail(key, reason, _scalar(value)))
        else:
            cleaned[key] = converted
    if creating:
        for key, field in fields.items():
            if field.required and key not in payload:
                errors.append(detail(key, '必須項目です'))
    return cleaned, errors
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run python -m pytest tests/api/test_api_validation.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/api/validation.py tests/api/test_api_validation.py
git commit -m "外部API: 項目定義に沿った入力検証を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: リクエスト本文の読み取りと画像チェック

**Files:**
- Create: `app/api/payload.py`, `app/api/images.py`
- Test: `tests/api/test_api_payload_images.py`

**Interfaces:**
- Consumes: `ApiError`, `detail`, `validation_error`（Task 1）、`REF_PHOTO`, `check_ref_id`（Task 3）
- Produces:
  - `parse_request(file_fields=()) -> (payload: dict, files: dict[str, list[FileStorage]])`
  - `IMAGE_KEYS = ('photo_pool_id', 'remove_image', 'extra_photo_pool_ids')`
  - `MAX_FILES_PER_REQUEST = 20`, `MAX_PIXELS = 50_000_000`（テストで monkeypatch する）
  - `CheckedFile(file, ext, original_name)`
  - `check_image(file, field_name) -> CheckedFile`（413 / 415 の `ApiError`）
  - `ImageInputs(main_file, main_pool_photo, remove, extra_files, extra_pool_photos)`
  - `collect_image_inputs(payload, files, errors, res) -> ImageInputs`（`res` は `image_folder` / `supplement_type` / `label` / `extra_images_hint` 属性を持つオブジェクト）
  - `check_files(inputs) -> None`（FileStorage を CheckedFile に置き換える）
  - `SavedFiles`（with 文。`save_upload(checked, folder)`, `copy_pool(photo, folder, field_name)`, `keep(path)`, `keep_all()`）
  - `apply_main_image(inputs, saved, folder, current_path) -> str|None`
  - `finish_main_image(inputs, usage_type, entity_id, new_path, old_path)`
  - `add_extra_images(inputs, saved, entity_type, entity_id) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_payload_images.py`:

```python
import io
import json
import os
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from app.api import images as img
from app.api.errors import ApiError
from app.api.payload import parse_request
from tests.api.helpers import image_bytes


def _fs(data, name):
    return FileStorage(stream=io.BytesIO(data), filename=name)


# --- parse_request ---

def test_parse_json(api_app):
    with api_app.test_request_context('/x', method='POST', json={'name': 'トマト'}):
        assert parse_request() == ({'name': 'トマト'}, {})


def test_parse_multipart(api_app):
    data = {'data': json.dumps({'name': 'トマト'}),
            'image': (io.BytesIO(image_bytes()), 'a.png')}
    with api_app.test_request_context('/x', method='POST', data=data,
                                      content_type='multipart/form-data'):
        payload, files = parse_request(('image', 'extra_images'))
    assert payload == {'name': 'トマト'}
    assert len(files['image']) == 1
    assert files['extra_images'] == []


def test_parse_multipart_rejects_unknown_part(api_app):
    data = {'name': 'トマト'}  # data パーツに入れ忘れ
    with api_app.test_request_context('/x', method='POST', data=data,
                                      content_type='multipart/form-data'):
        with pytest.raises(ApiError) as e:
            parse_request(('image',))
    assert e.value.status == 422
    assert e.value.details[0]['field'] == 'name'
    assert 'data, image' in e.value.details[0]['reason']


@pytest.mark.parametrize('body, content_type', [
    ('{broken', 'application/json'),
    ('[1, 2]', 'application/json'),
    ('name=x', 'text/plain'),
])
def test_parse_rejects_bad_body(api_app, body, content_type):
    with api_app.test_request_context('/x', method='POST', data=body, content_type=content_type):
        with pytest.raises(ApiError) as e:
            parse_request()
    assert e.value.status == 400


def test_parse_empty_body(api_app):
    with api_app.test_request_context('/x', method='POST'):
        assert parse_request() == ({}, {})


# --- check_image ---

@pytest.mark.parametrize('fmt, name, ext', [
    ('PNG', 'a.png', 'png'),
    ('JPEG', 'IMG_0001.JPG', 'jpg'),
    ('PNG', 'photo.jpg', 'png'),      # 拡張子と中身が違えば中身に合わせる
    ('JPEG', 'file_123', 'jpg'),      # 拡張子なし（Telegram のファイル送信）
    ('WEBP', 'a.webp', 'webp'),
    ('GIF', 'a.gif', 'gif'),
])
def test_check_image_detects_real_format(api_app, fmt, name, ext):
    with api_app.app_context():
        checked = img.check_image(_fs(image_bytes(fmt), name), 'image')
    assert checked.ext == ext
    assert checked.original_name == name


def test_check_image_rejects_non_image(api_app):
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(b'hello, not an image', 'a.jpg'), 'image')
    assert e.value.status == 415


def test_check_image_rejects_heic(api_app):
    heic = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(heic, 'IMG.HEIC'), 'image')
    assert e.value.status == 415
    assert 'HEIC' in e.value.message


def test_check_image_rejects_large_file(api_app):
    big = image_bytes() + b'\0' * (1024 * 1024)  # テスト設定の上限は 1MB
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(big, 'a.png'), 'image')
    assert e.value.status == 413


def test_check_image_rejects_too_many_pixels(api_app, monkeypatch):
    monkeypatch.setattr(img, 'MAX_PIXELS', 10)
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(image_bytes(size=(8, 8)), 'a.png'), 'image')
    assert e.value.status == 413


# --- collect_image_inputs ---

RES_WITH_IMAGE = SimpleNamespace(image_folder='crops', supplement_type='crop',
                                 label='作物', extra_images_hint='')
RES_RECORD = SimpleNamespace(image_folder='growth_records', supplement_type=None,
                             label='栽培記録', extra_images_hint='。複数枚の写真は栽培記録を複数件作成してください')
RES_TASK = SimpleNamespace(image_folder=None, supplement_type='task',
                           label='タスク', extra_images_hint='')


def _collect(api_app, res, payload, files=None):
    errors = []
    with api_app.app_context():
        inputs = img.collect_image_inputs(payload, files or {}, errors, res)
    return inputs, errors


def test_collect_rejects_two_main_images(api_app):
    files = {'image': [_fs(image_bytes(), 'a.png'), _fs(image_bytes(), 'b.png')]}
    _, errors = _collect(api_app, RES_WITH_IMAGE, {}, files)
    assert 'extra_images' in errors[0]['reason']


def test_collect_rejects_remove_with_new_image(api_app):
    files = {'image': [_fs(image_bytes(), 'a.png')]}
    _, errors = _collect(api_app, RES_WITH_IMAGE, {'remove_image': True}, files)
    assert errors[0]['field'] == 'remove_image'


def test_collect_rejects_unknown_photo_pool_id(api_app):
    _, errors = _collect(api_app, RES_WITH_IMAGE, {'photo_pool_id': 99})
    assert errors[0]['field'] == 'photo_pool_id'
    assert '存在しません' in errors[0]['reason']


def test_collect_rejects_extras_for_planting_record(api_app):
    files = {'extra_images': [_fs(image_bytes(), 'a.png')]}
    _, errors = _collect(api_app, RES_RECORD, {}, files)
    assert '複数件作成' in errors[0]['reason']


def test_collect_rejects_main_image_for_task(api_app):
    files = {'image': [_fs(image_bytes(), 'a.png')]}
    _, errors = _collect(api_app, RES_TASK, {}, files)
    assert errors[0]['field'] == 'image'
    assert 'extra_images' in errors[0]['reason']


def test_collect_limits_file_count(api_app, monkeypatch):
    monkeypatch.setattr(img, 'MAX_FILES_PER_REQUEST', 2)
    files = {'extra_images': [_fs(image_bytes(), f'{i}.png') for i in range(3)]}
    _, errors = _collect(api_app, RES_WITH_IMAGE, {}, files)
    assert '2枚まで' in errors[0]['reason']


# --- SavedFiles ---

def test_saved_files_removes_pending_on_error(api_app):
    with api_app.app_context():
        checked = img.check_image(_fs(image_bytes(), 'a.png'), 'image')
        with pytest.raises(RuntimeError):
            with img.SavedFiles() as saved:
                path = saved.save_upload(checked, 'crops')
                full = os.path.join(api_app.config['UPLOAD_FOLDER'], path)
                assert os.path.exists(full)
                raise RuntimeError('DB 書き込み失敗')
        assert not os.path.exists(full)


def test_saved_files_keeps_committed_files(api_app):
    with api_app.app_context():
        checked = img.check_image(_fs(image_bytes(), 'a.png'), 'image')
        with pytest.raises(RuntimeError):
            with img.SavedFiles() as saved:
                path = saved.save_upload(checked, 'crops')
                saved.keep(path)
                raise RuntimeError('後続の処理で失敗')
        assert os.path.exists(os.path.join(api_app.config['UPLOAD_FOLDER'], path))
        assert path.endswith('.png')
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_payload_images.py -v`
Expected: FAIL（`ModuleNotFoundError: app.api.payload`）

- [ ] **Step 3: payload.py を実装**

`app/api/payload.py`:

```python
"""リクエスト本文（JSON / multipart）の読み取り"""
import json

from flask import request

from app.api.errors import ApiError, detail, validation_error


def parse_request(file_fields=()):
    """(payload, files) を返す

    - JSON: Content-Type: application/json の本文
    - multipart: `data` パーツを JSON として読み、file_fields に挙げた名前のファイルを受け付ける
    - files は {名前: [FileStorage, ...]}（空のファイル指定は除く）
    """
    files = {name: [] for name in file_fields}
    if request.mimetype == 'multipart/form-data':
        unknown = [k for k in request.form if k != 'data'] + [k for k in request.files if k not in files]
        if unknown:
            usable = ', '.join(['data', *file_fields])
            raise validation_error([detail(k, f'未知のパーツです。使えるパーツ: {usable}') for k in unknown])
        raw = request.form.get('data', '')
        payload = _load_json(raw, 'data パーツ') if raw.strip() else {}
        for name in file_fields:
            files[name] = [f for f in request.files.getlist(name) if f and f.filename]
    elif request.mimetype == 'application/json':
        payload = _load_json(request.get_data(as_text=True), '本文')
    elif not request.get_data():
        payload = {}
    else:
        raise ApiError(400, 'bad_request', 'Content-Type は application/json か multipart/form-data にしてください')
    if not isinstance(payload, dict):
        raise ApiError(400, 'bad_request', 'JSON はオブジェクト（{...}）で送ってください')
    return payload, files


def _load_json(text, where):
    try:
        return json.loads(text)
    except ValueError as e:
        raise ApiError(400, 'bad_request', f'{where}の JSON を読み取れません: {e}')
```

- [ ] **Step 4: images.py を実装**

`app/api/images.py`:

```python
"""画像アップロードの検証・保存（本体画像・追加画像・写真プール）

拡張子は信用せず Pillow で開いて実形式を判定し、保存する拡張子も実形式に合わせる。
"""
import os
import warnings
from dataclasses import dataclass, field

from flask import current_app
from PIL import Image

from app.api.errors import ApiError, detail
from app.api.validation import REF_PHOTO, check_ref_id
from app.models.photo_pool import PhotoPool
from app.models.supplement import Supplement
from app.utils.upload import copy_image, delete_image, save_image

ALLOWED_FORMATS = {'JPEG': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp'}
MAX_PIXELS = 50_000_000
MAX_FILES_PER_REQUEST = 20
IMAGE_KEYS = ('photo_pool_id', 'remove_image', 'extra_photo_pool_ids')
_HEIF_BRANDS = {b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis', b'mif1', b'msf1'}


@dataclass
class CheckedFile:
    file: object         # werkzeug FileStorage
    ext: str             # 実形式の拡張子（jpg / png / gif / webp）
    original_name: str


@dataclass
class ImageInputs:
    main_file: object = None               # FileStorage → check_files 後は CheckedFile
    main_pool_photo: dict | None = None
    remove: bool = False
    extra_files: list = field(default_factory=list)
    extra_pool_photos: list = field(default_factory=list)


def _too_many_pixels(field_name, name):
    return ApiError(413, 'too_large', f'画像の画素数が多すぎます（{MAX_PIXELS:,} 画素まで）',
                    [detail(field_name, f'{name}: 画素数超過')])


def check_image(file, field_name):
    """アップロード画像を検証して CheckedFile を返す（413 / 415 の ApiError）"""
    name = file.filename
    max_mb = current_app.config['API_MAX_IMAGE_MB']
    stream = file.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size > max_mb * 1024 * 1024:
        raise ApiError(413, 'too_large', f'画像が大きすぎます（1枚 {max_mb}MB まで）',
                       [detail(field_name, f'{name}: {size / 1024 / 1024:.1f}MB')])
    head = stream.read(12)
    stream.seek(0)
    if head[4:8] == b'ftyp' and head[8:12] in _HEIF_BRANDS:
        raise ApiError(415, 'unsupported_image',
                       'HEIC/HEIF 形式は未対応です。JPEG で送ってください（Telegram では「写真」として送ると JPEG になります）',
                       [detail(field_name, f'{name}: HEIC')])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(stream) as image:
                fmt = image.format
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise _too_many_pixels(field_name, name)
                image.verify()
    except ApiError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _too_many_pixels(field_name, name)
    except Exception:
        raise ApiError(415, 'unsupported_image', '画像として読み込めないファイルです（JPEG / PNG / GIF / WebP のみ対応）',
                       [detail(field_name, f'{name}: 読み込み失敗')])
    finally:
        stream.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ApiError(415, 'unsupported_image', f'{fmt} 形式は未対応です（JPEG / PNG / GIF / WebP のみ対応）',
                       [detail(field_name, f'{name}: {fmt}')])
    return CheckedFile(file=file, ext=ALLOWED_FORMATS[fmt], original_name=name)


def _pool_photo(raw, field_name, errors):
    """写真プール ID を検証して写真の dict を返す（ファイルが消えていれば誤り）"""
    photo_id, reason = check_ref_id(REF_PHOTO, raw)
    if reason:
        errors.append(detail(field_name, reason, raw if isinstance(raw, (int, str)) else None))
        return None
    photo = PhotoPool.get_by_id(photo_id)
    full = os.path.join(current_app.config['UPLOAD_FOLDER'], photo['image_path'])
    if not os.path.exists(full):
        errors.append(detail(field_name, f'写真プール ID {photo_id} の画像ファイルが見つかりません'))
        return None
    return photo


def collect_image_inputs(payload, files, errors, res):
    """画像関連の入力を検証して ImageInputs を返す（誤りは errors に積む）"""
    inputs = ImageInputs()
    images = files.get('image', [])
    extras = files.get('extra_images', [])
    pool_id = payload.get('photo_pool_id')
    remove = payload.get('remove_image', False)
    extra_ids = payload.get('extra_photo_pool_ids')

    if not res.image_folder:
        reason = (f'{res.label}は本体画像を持ちません。追加画像（extra_images / extra_photo_pool_ids）を使ってください'
                  if res.supplement_type else f'{res.label}は画像を持ちません')
        for key, present in (('image', images), ('photo_pool_id', pool_id is not None),
                             ('remove_image', 'remove_image' in payload)):
            if present:
                errors.append(detail(key, reason))
    else:
        if len(images) > 1:
            errors.append(detail('image', 'image は1枚だけです。2枚目以降は extra_images で送ってください'))
        if not isinstance(remove, bool):
            errors.append(detail('remove_image', 'true か false で指定してください',
                                 remove if isinstance(remove, (int, str)) else None))
            remove = False
        if images and pool_id is not None:
            errors.append(detail('photo_pool_id', 'image と photo_pool_id は同時に指定できません'))
        if remove and (images or pool_id is not None):
            errors.append(detail('remove_image', '新しい画像の指定と remove_image: true は同時に使えません'))
        if pool_id is not None:
            inputs.main_pool_photo = _pool_photo(pool_id, 'photo_pool_id', errors)
        inputs.main_file = images[0] if images else None
        inputs.remove = remove

    if not res.supplement_type:
        if extras or extra_ids is not None:
            key = 'extra_images' if extras else 'extra_photo_pool_ids'
            errors.append(detail(key, f'{res.label}には追加画像を付けられません{res.extra_images_hint}'))
    else:
        inputs.extra_files = list(extras)
        if extra_ids is not None:
            if not isinstance(extra_ids, list):
                errors.append(detail('extra_photo_pool_ids', 'ID の配列で指定してください（例: [12, 13]）'))
            else:
                for i, raw in enumerate(extra_ids):
                    photo = _pool_photo(raw, f'extra_photo_pool_ids[{i}]', errors)
                    if photo:
                        inputs.extra_pool_photos.append(photo)

    total = len(images) + len(extras)
    if total > MAX_FILES_PER_REQUEST:
        errors.append(detail('extra_images', f'画像は1回のリクエストで{MAX_FILES_PER_REQUEST}枚までです（{total}枚）'))
    return inputs


def check_files(inputs):
    """ファイルの中身を検証する（項目の検証が通った後に呼ぶ）"""
    if inputs.main_file is not None:
        inputs.main_file = check_image(inputs.main_file, 'image')
    inputs.extra_files = [check_image(f, 'extra_images') for f in inputs.extra_files]


class SavedFiles:
    """このリクエストで保存した画像を記録し、DB に書き込む前に失敗したら消す

    DB に書き込んで参照されたファイルは keep() で外す（以降の失敗では消さない）。
    """

    def __init__(self):
        self.pending = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            for path in self.pending:
                delete_image(path)
        return False

    def save_upload(self, checked, folder):
        checked.file.filename = f'upload.{checked.ext}'
        path = save_image(checked.file, folder)
        if not path:
            raise ApiError(500, 'internal_error', '画像の保存に失敗しました')
        self.pending.append(path)
        return path

    def copy_pool(self, photo, folder, field_name):
        path = copy_image(photo['image_path'], folder)
        if not path:
            raise ApiError(422, 'validation_error', '入力内容に誤りがあります（1件）',
                           [detail(field_name, f'写真プール ID {photo["id"]} の画像ファイルが見つかりません')])
        self.pending.append(path)
        return path

    def keep(self, path):
        if path in self.pending:
            self.pending.remove(path)

    def keep_all(self):
        self.pending.clear()


def apply_main_image(inputs, saved, folder, current_path):
    """本体画像の新しい相対パスを返す（変更しないなら current_path）"""
    if inputs.main_file is not None:
        return saved.save_upload(inputs.main_file, folder)
    if inputs.main_pool_photo is not None:
        return saved.copy_pool(inputs.main_pool_photo, folder, 'photo_pool_id')
    if inputs.remove:
        return None
    return current_path


def finish_main_image(inputs, usage_type, entity_id, new_path, old_path):
    """DB 更新後: 写真プールの使用記録と、置き換わった旧ファイルの削除（既存画面と同じ挙動）"""
    if inputs.main_pool_photo is not None and new_path:
        PhotoPool.record_usage(inputs.main_pool_photo['id'], usage_type, entity_id, new_path)
    if old_path and old_path != new_path:
        delete_image(old_path)


def add_extra_images(inputs, saved, entity_type, entity_id):
    """追加画像を補足情報（image 型）として添付する"""
    for checked in inputs.extra_files:
        path = saved.save_upload(checked, 'supplements')
        Supplement.create({'entity_type': entity_type, 'entity_id': entity_id,
                           'supplement_type': 'image', 'title': None, 'content': path})
        saved.keep(path)
    for photo in inputs.extra_pool_photos:
        path = saved.copy_pool(photo, 'supplements', 'extra_photo_pool_ids')
        supplement_id = Supplement.create({'entity_type': entity_type, 'entity_id': entity_id,
                                           'supplement_type': 'image', 'title': None, 'content': path})
        saved.keep(path)
        PhotoPool.record_usage(photo['id'], 'supplement', supplement_id, path)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run python -m pytest tests/api/test_api_payload_images.py -v`
Expected: PASS

- [ ] **Step 6: コミット**

```bash
git add app/api/payload.py app/api/images.py tests/api/test_api_payload_images.py
git commit -m "外部API: 本文の読み取りと画像の検証・保存処理を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: リソース共通処理と作物 API

**Files:**
- Create: `app/api/serialize.py`, `app/api/choices.py`, `app/api/resource.py`, `app/api/crops.py`
- Modify: `app/api/__init__.py`（`init_app` の import 行）
- Test: `tests/api/test_api_crops.py`

**Interfaces:**
- Consumes: Task 1〜4 のすべて
- Produces:
  - `serialize.plain(value)`, `serialize.web_url(path)`, `serialize.image_url(image_path)`, `serialize.display_name(crop_name, variety)`, `serialize.planting_label(row)`
  - `choices.PLANTING_STATUSES`, `TASK_STATUSES`, `SUN_EXPOSURES`, `WEATHERS`, `DIARY_RELATION_KEYS`, `COOKING_RELATION_KEYS`, `TASK_RELATION_KEYS`, `crop_icons()`, `bg_images()`, `distinct_values(table, column)`
  - `resource.Resource`（クラス属性: `name, label, model, fields, read_only, web_path, image_folder, usage_type, supplement_type, extra_images_hint, reserved_keys, list_from, list_id, list_order, search_columns, date_column, filters, extra_list_args`。フック: `fetch(obj_id)`, `to_api(row)`, `to_model(values)`, `insert(model_data)`, `save(obj_id, model_data, row)`, `check(values, merged, row, errors)`, `parse_reserved(payload, row, errors)`, `after_write(obj_id, reserved)`, `describe(row)`, `list_where(args, where, params, errors)`, `serialize(row)`）
  - `resource.register(bp, res)`, `resource.load_or_404(res, obj_id)`, `resource.page_arg(args, key, default, low, high, errors)`, `resource.like_pattern(q)`, `resource.LIKE_ESCAPE`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_crops.py`:

```python
import logging
import os

from app.api.choices import crop_icons
from tests.api.helpers import TOKEN, file_part, image_bytes, multipart


def _create(api, **payload):
    payload = {'name': 'トマト', 'crop_type': 'ナス科', **payload}
    res = api.post('/api/v1/crops', json=payload)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_minimal(api):
    data = _create(api)
    assert data['name'] == 'トマト'
    assert data['image_color'] == '#4CAF50'
    assert data['image_url'] is None
    assert data['extra_images'] == []
    assert data['varieties'] == []
    assert data['web_url'] == f'http://garden.test:5000/crops/{data["id"]}'


def test_create_reports_missing_and_unknown_fields(api):
    res = api.post('/api/v1/crops', json={'nmae': 'トマト'})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'nmae', 'name', 'crop_type'}


def test_create_rejects_unknown_icon(api):
    res = api.post('/api/v1/crops', json={'name': 'a', 'crop_type': 'b', 'icon_path': 'nope.png'})
    assert res.status_code == 422
    assert '/api/v1/meta' in res.get_json()['error']['details'][0]['reason']


def test_create_accepts_existing_icon(api):
    icon = crop_icons()[0]
    assert _create(api, icon_path=icon)['icon_path'] == icon


def test_create_with_image_and_extra_images(api, api_app):
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'},
                     image=file_part(image_bytes('JPEG'), 'main.jpg'),
                     extra_images=[file_part(image_bytes(), 'a.png'), file_part(image_bytes(), 'b.png')])
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['image_url'].startswith('http://garden.test:5000/static/uploads/crops/')
    assert len(data['extra_images']) == 2
    uploads = api_app.config['UPLOAD_FOLDER']
    rel = data['image_url'].split('/static/uploads/')[1]
    assert os.path.exists(os.path.join(uploads, rel))
    assert os.path.isdir(os.path.join(uploads, 'crops', 'thumbs'))


def test_invalid_image_creates_nothing(api, api_app, sql):
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'},
                     image=file_part(b'not an image', 'main.jpg'))
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 415
    assert sql('SELECT COUNT(*) AS n FROM crops')[0]['n'] == 0
    assert not os.path.exists(os.path.join(api_app.config['UPLOAD_FOLDER'], 'crops'))


def test_db_failure_removes_saved_image(api, api_app, monkeypatch):
    from app.models.crop import Crop

    def fail(data):
        raise RuntimeError('db down')
    monkeypatch.setattr(Crop, 'create', staticmethod(fail))
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'},
                     image=file_part(image_bytes(), 'main.png'))
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 500
    folder = os.path.join(api_app.config['UPLOAD_FOLDER'], 'crops')
    leftover = [f for f in os.listdir(folder) if f != 'thumbs'] if os.path.isdir(folder) else []
    assert leftover == []


def test_patch_changes_only_sent_fields(api):
    crop = _create(api, notes='旧メモ', image_color='#123456')
    res = api.patch(f'/api/v1/crops/{crop["id"]}', json={'notes': '新メモ'})
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['notes'] == '新メモ'
    assert data['name'] == 'トマト'
    assert data['image_color'] == '#123456'


def test_patch_null_on_required_field_is_rejected(api):
    crop = _create(api)
    res = api.patch(f'/api/v1/crops/{crop["id"]}', json={'name': None})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0] == {'field': 'name', 'reason': '必須項目です'}


def test_patch_replaces_and_removes_image(api, api_app):
    uploads = api_app.config['UPLOAD_FOLDER']
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'}, image=file_part(image_bytes(), 'a.png'))
    crop = api.post('/api/v1/crops', data=form, content_type='multipart/form-data').get_json()['data']
    old = os.path.join(uploads, crop['image_url'].split('/static/uploads/')[1])

    form = multipart(None, image=file_part(image_bytes('JPEG'), 'b.jpg'))
    data = api.patch(f'/api/v1/crops/{crop["id"]}', data=form,
                     content_type='multipart/form-data').get_json()['data']
    new = os.path.join(uploads, data['image_url'].split('/static/uploads/')[1])
    assert not os.path.exists(old)
    assert os.path.exists(new)

    data = api.patch(f'/api/v1/crops/{crop["id"]}', json={'remove_image': True}).get_json()['data']
    assert data['image_url'] is None
    assert not os.path.exists(new)


def test_get_and_404(api):
    crop = _create(api)
    assert api.get(f'/api/v1/crops/{crop["id"]}').get_json()['data']['id'] == crop['id']
    res = api.get('/api/v1/crops/999')
    assert res.status_code == 404
    assert '作物' in res.get_json()['error']['message']
    assert api.get('/api/v1/crops/99999999999999999999').status_code == 404
    assert api.patch('/api/v1/crops/999', json={'notes': 'x'}).status_code == 404


def test_list_search_filter_and_paging(api):
    _create(api, name='ミニトマト')
    _create(api, name='なす', crop_type='ナス科')
    _create(api, name='きゅうり', crop_type='ウリ科')
    body = api.get('/api/v1/crops?q=トマト').get_json()
    assert [c['name'] for c in body['data']] == ['ミニトマト']
    assert body['meta'] == {'total': 1, 'limit': 50, 'offset': 0}
    body = api.get('/api/v1/crops?crop_type=ウリ科').get_json()
    assert [c['name'] for c in body['data']] == ['きゅうり']
    body = api.get('/api/v1/crops?limit=1&offset=1').get_json()
    assert len(body['data']) == 1
    assert body['meta']['total'] == 3


def test_list_rejects_bad_args(api):
    res = api.get('/api/v1/crops?limit=500&type=x')
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'limit', 'type'}


def test_add_extra_images(api):
    crop = _create(api)
    form = {'extra_images': [file_part(image_bytes(), 'a.png')]}
    res = api.post(f'/api/v1/crops/{crop["id"]}/images', data=form, content_type='multipart/form-data')
    assert res.status_code == 201
    assert len(res.get_json()['data']['extra_images']) == 1
    res = api.post(f'/api/v1/crops/{crop["id"]}/images', json={})
    assert res.status_code == 422


def test_audit_log_records_write_without_token(api, caplog):
    with caplog.at_level(logging.INFO, logger='app.api'):
        crop = _create(api)
    messages = [r.getMessage() for r in caplog.records if r.name == 'app.api']
    assert any(f'POST /api/v1/crops -> 201 id={crop["id"]}' in m for m in messages)
    assert not any(TOKEN in m for m in messages)
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_crops.py -v`
Expected: FAIL（`ModuleNotFoundError: app.api.choices`）

- [ ] **Step 3: serialize.py と choices.py を書く**

`app/api/serialize.py`:

```python
"""API レスポンス用の値変換と URL 生成"""
from datetime import date, datetime
from decimal import Decimal

from flask import current_app

from app import _crop_display_name as display_name  # noqa: F401（作物名表記ルールを画面と共用）


def plain(value):
    """DB の値を JSON にできる形へ（日付は ISO 形式の文字列）"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def web_url(path):
    """既存 Web 画面の URL（スマホで開ける）"""
    return current_app.config['WEB_BASE_URL'].rstrip('/') + path


def image_url(image_path):
    return web_url('/static/uploads/' + image_path) if image_path else None


def planting_label(row):
    """植え付けの表示名。row は crop_name, variety, location_name, planted_date を持つ"""
    label = f'{display_name(row["crop_name"], row.get("variety"))} / {row["location_name"]}'
    if row.get('planted_date'):
        label += f'（{plain(row["planted_date"])} 植え付け）'
    return label
```

`app/api/choices.py`:

```python
"""選択肢の一覧（/meta と検証で共用）"""
import os

from app.database import get_db

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')

PLANTING_STATUSES = ['active', 'harvested', 'removed']
TASK_STATUSES = ['pending', 'in_progress', 'completed']
SUN_EXPOSURES = ['全日', '半日', '日陰']                       # locations/form.html と同じ
WEATHERS = ['晴れ', '曇り', '雨', '雪', '晴れ時々曇り', '曇り時々雨']  # diary/form.html と同じ

# 日記・料理・タスクで使える関連のキー（各テーブルの列に合わせる）
DIARY_RELATION_KEYS = ('crop_ids', 'variety_ids', 'location_ids', 'planting_ids', 'harvest_ids')
COOKING_RELATION_KEYS = ('crop_ids', 'variety_ids', 'planting_ids', 'harvest_ids')
TASK_RELATION_KEYS = ('crop_ids', 'variety_ids', 'location_ids', 'planting_ids')


def crop_icons():
    """作物アイコンのファイル名一覧（crop_routes._get_crop_icon_list と同じ）"""
    path = os.path.join(_STATIC_DIR, 'images', 'crop_icons')
    return sorted(os.listdir(path)) if os.path.isdir(path) else []


def bg_images():
    """見取り図背景画像のファイル名一覧（Location.get_bg_images と同じ条件）"""
    path = os.path.join(_STATIC_DIR, 'images', 'location_bg_images')
    if not os.path.isdir(path):
        return []
    return sorted(f for f in os.listdir(path)
                  if os.path.splitext(f)[1].lower() in {'.png', '.jpg', '.jpeg', '.webp'})


def distinct_values(table, column):
    """既存データに入っている値の一覧（自由入力の項目の候補）"""
    rows = get_db().execute(
        f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
    ).fetchall()
    return [r[0] for r in rows]
```

- [ ] **Step 4: resource.py を書く**

`app/api/resource.py`:

```python
"""リソース共通の一覧・詳細・作成・部分更新・追加画像の処理

各リソースは Resource を継承してクラス属性（項目定義・一覧の SQL 断片）と
必要なフックだけを上書きし、register(bp, res) でルートを登録する。
"""
from flask import g, request

from app.api import images as img
from app.api.errors import ApiError, detail, ok, validation_error
from app.api.payload import parse_request
from app.api.serialize import image_url, plain, web_url
from app.api.validation import SQLITE_MAX_INT, Field, check_value, validate_payload
from app.database import get_db
from app.models.supplement import Supplement

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
LIKE_ESCAPE = "ESCAPE '\\'"


def like_pattern(q):
    """部分一致用パターン。% と _ は文字として扱う（LIKE_ESCAPE と組で使う）"""
    escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def page_arg(args, key, default, low, high, errors):
    """limit / offset などの整数クエリを読む"""
    if key not in args:
        return default
    value, reason = check_value(Field('int', min_value=low), args[key])
    if reason:
        errors.append(detail(key, reason, args[key]))
        return default
    if value is None:
        return default
    if high is not None and value > high:
        errors.append(detail(key, f'{high} 以下で指定してください', args[key]))
        return default
    return value


class Resource:
    """API リソースの定義。サブクラスでクラス属性とフックを上書きする"""
    name = ''               # URL のリソース名（例: 'crops'）
    label = ''              # 日本語名（例: '作物'）
    model = None            # get_by_id / create / update を持つモデルクラス
    fields = {}             # 書き込める項目 {API 項目名: Field}
    read_only = ()          # 送られたら 422 にする項目（COMMON_READ_ONLY に追加）
    web_path = ''           # 既存画面のパス（例: '/crops/{id}'）
    image_folder = None     # 本体画像の保存先（uploads 配下）。None なら本体画像なし
    usage_type = None       # 写真プール使用履歴の entity_type
    supplement_type = None  # 追加画像（補足情報）の entity_type。None なら追加画像なし
    extra_images_hint = ''  # 追加画像を持てないときの案内
    reserved_keys = ()      # parse_reserved で扱う追加キー（relations など）

    # 一覧
    list_from = ''          # FROM 句（エイリアス付き、JOIN 可）
    list_id = ''            # 主キー列（例: 'c.id'）
    list_order = ''         # ORDER BY 句
    search_columns = ()     # q で部分一致させる列
    date_column = None      # date_from / date_to の対象列
    filters = {}            # {クエリ名: (WHERE 断片, Field)}
    extra_list_args = ()    # list_where で扱うクエリ名

    COMMON_READ_ONLY = ('id', 'created_at', 'updated_at', 'image_path')

    # --- フック ---
    def fetch(self, obj_id):
        """DB 行（dict）か None"""
        return self.model.get_by_id(obj_id)

    def to_api(self, row):
        """DB 行 → API 項目名の dict（書き込める項目のみ）"""
        return {name: plain(row.get(f.column or name)) for name, f in self.fields.items()}

    def to_model(self, values):
        """API 項目名の dict → モデルの create / update に渡す dict"""
        return {(f.column or name): values.get(name) for name, f in self.fields.items()}

    def insert(self, model_data):
        return self.model.create(model_data)

    def save(self, obj_id, model_data, row):
        self.model.update(obj_id, model_data)

    def check(self, values, merged, row, errors):
        """項目をまたぐ検証。values=送られた項目、merged=既存値と合成後（変更可）、row=既存行（作成時 None）"""

    def parse_reserved(self, payload, row, errors):
        """reserved_keys の値を検証し、after_write に渡す値を返す"""
        return None

    def after_write(self, obj_id, reserved):
        """本体の保存後に呼ばれる（関連の保存など）"""

    def describe(self, row):
        """詳細に追加する項目（関連先の名前など）"""
        return {}

    def list_where(self, args, where, params, errors):
        """filters で表せない絞り込み（extra_list_args 用）"""

    # --- 共通 ---
    def serialize(self, row):
        data = {'id': row['id'], **self.to_api(row)}
        if self.image_folder:
            data['image_url'] = image_url(row.get('image_path'))
        data.update(self.describe(row))
        if self.supplement_type:
            data['extra_images'] = [
                {'supplement_id': s['id'], 'image_url': image_url(s['content'])}
                for s in Supplement.get_by_entity(self.supplement_type, row['id'])
                if s['supplement_type'] == 'image'
            ]
        data['created_at'] = plain(row.get('created_at'))
        data['updated_at'] = plain(row.get('updated_at'))
        data['web_url'] = web_url(self.web_path.format(id=row['id']))
        return data


def load_or_404(res, obj_id):
    row = res.fetch(obj_id) if 0 < obj_id <= SQLITE_MAX_INT else None
    if row is None:
        raise ApiError(404, 'not_found',
                       f'ID {obj_id} の{res.label}は存在しません。GET /api/v1/{res.name} で一覧を確認してください')
    return row


def _validate_body(res, payload, files, row):
    """本文を検証して (values, inputs, reserved) を返す。誤りがあれば 422"""
    values, errors = validate_payload(
        res.fields, payload, creating=row is None,
        reserved=(*img.IMAGE_KEYS, *res.reserved_keys),
        read_only=(*res.COMMON_READ_ONLY, *res.read_only))
    inputs = img.collect_image_inputs(payload, files, errors, res)
    reserved = res.parse_reserved(payload, row, errors)
    merged = {**(res.to_api(row) if row else {}), **values}
    if not errors:
        res.check(values, merged, row, errors)
    if errors:
        raise validation_error(errors)
    img.check_files(inputs)
    return merged, inputs, reserved


def list_items(res):
    args = request.args
    errors = []
    allowed = {'q', 'limit', 'offset', *res.filters, *res.extra_list_args}
    if res.date_column:
        allowed |= {'date_from', 'date_to'}
    for key in args:
        if key not in allowed:
            errors.append(detail(key, f'未知の検索条件です。使える条件: {", ".join(sorted(allowed))}'))
    limit = page_arg(args, 'limit', DEFAULT_LIMIT, 1, MAX_LIMIT, errors)
    offset = page_arg(args, 'offset', 0, 0, None, errors)

    where, params = [], []
    q = args.get('q', '').strip()
    if q and res.search_columns:
        where.append('(' + ' OR '.join(f'{c} LIKE ? {LIKE_ESCAPE}' for c in res.search_columns) + ')')
        params += [like_pattern(q)] * len(res.search_columns)
    for key, (clause, field) in res.filters.items():
        if key in args:
            value, reason = check_value(field, args[key])
            if reason:
                errors.append(detail(key, reason, args[key]))
            elif value is not None:
                where.append(clause)
                params.append(value)
    if res.date_column:
        for key, op in (('date_from', '>='), ('date_to', '<=')):
            if key in args:
                value, reason = check_value(Field('date'), args[key])
                if reason:
                    errors.append(detail(key, reason, args[key]))
                elif value is not None:
                    where.append(f'DATE({res.date_column}) {op} ?')
                    params.append(value)
    res.list_where(args, where, params, errors)
    if errors:
        raise validation_error(errors)

    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    db = get_db()
    total = db.execute(f'SELECT COUNT(*) FROM {res.list_from}{where_sql}', params).fetchone()[0]
    ids = [r[0] for r in db.execute(
        f'SELECT {res.list_id} FROM {res.list_from}{where_sql} ORDER BY {res.list_order} LIMIT ? OFFSET ?',
        [*params, limit, offset])]
    items = [res.serialize(res.fetch(i)) for i in ids]
    return ok(items, meta={'total': total, 'limit': limit, 'offset': offset})


def get_item(res, obj_id):
    return ok(res.serialize(load_or_404(res, obj_id)))


def create_item(res):
    payload, files = parse_request(('image', 'extra_images'))
    values, inputs, reserved = _validate_body(res, payload, files, None)
    with img.SavedFiles() as saved:
        model_data = res.to_model(values)
        if res.image_folder:
            model_data['image_path'] = img.apply_main_image(inputs, saved, res.image_folder, None)
        obj_id = res.insert(model_data)
        saved.keep_all()
        g.api_target_id = obj_id
        res.after_write(obj_id, reserved)
        if res.image_folder:
            img.finish_main_image(inputs, res.usage_type, obj_id, model_data['image_path'], None)
        img.add_extra_images(inputs, saved, res.supplement_type, obj_id)
    return ok(res.serialize(res.fetch(obj_id)), 201)


def patch_item(res, obj_id):
    row = load_or_404(res, obj_id)
    g.api_target_id = obj_id
    payload, files = parse_request(('image', 'extra_images'))
    merged, inputs, reserved = _validate_body(res, payload, files, row)
    with img.SavedFiles() as saved:
        model_data = res.to_model(merged)
        old_path = row.get('image_path') if res.image_folder else None
        if res.image_folder:
            model_data['image_path'] = img.apply_main_image(inputs, saved, res.image_folder, old_path)
        res.save(obj_id, model_data, row)
        saved.keep_all()
        res.after_write(obj_id, reserved)
        if res.image_folder:
            img.finish_main_image(inputs, res.usage_type, obj_id, model_data['image_path'], old_path)
        img.add_extra_images(inputs, saved, res.supplement_type, obj_id)
    return ok(res.serialize(res.fetch(obj_id)))


def add_images(res, obj_id):
    """POST /{res}/{id}/images: 追加画像（補足情報）を添付する"""
    load_or_404(res, obj_id)
    g.api_target_id = obj_id
    payload, files = parse_request(('extra_images',))
    errors = [detail(k, '未知の項目です。使える項目: extra_photo_pool_ids')
              for k in payload if k != 'extra_photo_pool_ids']
    inputs = img.collect_image_inputs(
        {k: v for k, v in payload.items() if k == 'extra_photo_pool_ids'}, files, errors, res)
    if not errors and not inputs.extra_files and not inputs.extra_pool_photos:
        errors.append(detail('extra_images', 'extra_images（ファイル）か extra_photo_pool_ids で画像を1枚以上指定してください'))
    if errors:
        raise validation_error(errors)
    img.check_files(inputs)
    with img.SavedFiles() as saved:
        img.add_extra_images(inputs, saved, res.supplement_type, obj_id)
    return ok(res.serialize(res.fetch(obj_id)), 201)


def register(bp, res):
    """リソースの共通ルートを登録する"""
    base = f'/{res.name}'
    bp.add_url_rule(base, f'{res.name}_list', lambda: list_items(res), methods=['GET'])
    bp.add_url_rule(base, f'{res.name}_create', lambda: create_item(res), methods=['POST'])
    bp.add_url_rule(f'{base}/<int:obj_id>', f'{res.name}_get',
                    lambda obj_id: get_item(res, obj_id), methods=['GET'])
    bp.add_url_rule(f'{base}/<int:obj_id>', f'{res.name}_patch',
                    lambda obj_id: patch_item(res, obj_id), methods=['PATCH'])
    if res.supplement_type:
        bp.add_url_rule(f'{base}/<int:obj_id>/images', f'{res.name}_images',
                        lambda obj_id: add_images(res, obj_id), methods=['POST'])
```

- [ ] **Step 5: 作物リソースを書いて登録する**

`app/api/crops.py`:

```python
"""作物 API（/api/v1/crops）"""
from app.api import bp
from app.api.choices import crop_icons
from app.api.resource import Resource, register
from app.api.validation import Field
from app.database import get_db
from app.models.crop import Crop


class CropResource(Resource):
    name = 'crops'
    label = '作物'
    model = Crop
    web_path = '/crops/{id}'
    image_folder = 'crops'
    usage_type = 'crop'
    supplement_type = 'crop'
    fields = {
        'name': Field('str', required=True, max_len=100),
        'crop_type': Field('str', required=True, max_len=50),
        'notes': Field('str'),
        'icon_path': Field('enum', choices=crop_icons),
        'image_color': Field('color'),
    }
    list_from = 'crops c'
    list_id = 'c.id'
    list_order = 'c.name, c.id'
    search_columns = ('c.name',)
    filters = {'crop_type': ('c.crop_type = ?', Field('str'))}

    def to_model(self, values):
        data = super().to_model(values)
        data['image_color'] = data['image_color'] or '#4CAF50'  # 画面と同じ既定色
        return data

    def describe(self, row):
        rows = get_db().execute(
            'SELECT id, name FROM varieties WHERE crop_id = ? ORDER BY name, id', (row['id'],)
        ).fetchall()
        return {'varieties': [{'id': r['id'], 'name': r['name']} for r in rows]}


register(bp, CropResource())
```

`app/api/__init__.py` の `init_app` 内の import 行を次に変更:

```python
    from app.api import meta, crops  # noqa: F401
```

- [ ] **Step 6: テストが通ることを確認**

Run: `uv run python -m pytest tests/api -v`
Expected: PASS

- [ ] **Step 7: curl 例を追記してコミット**

`docs/api/curl-examples.md` の末尾に追記:

````markdown
## 作物（/crops）

```bash
gapi "$GARDEN_API_URL/crops?q=トマト"                                   # 一覧・検索
gapi "$GARDEN_API_URL/crops/1"                                           # 詳細
gapi -X POST "$GARDEN_API_URL/crops" -H 'Content-Type: application/json' \
     -d '{"name":"ミニトマト","crop_type":"ナス科"}'                      # 作成
gapi -X POST "$GARDEN_API_URL/crops" \
     -F 'data={"name":"なす","crop_type":"ナス科"}' -F image=@nasu.jpg   # 画像付きで作成
gapi -X PATCH "$GARDEN_API_URL/crops/1" -H 'Content-Type: application/json' \
     -d '{"notes":"脇芽はこまめに摘む"}'                                  # 部分更新
gapi -X POST "$GARDEN_API_URL/crops/1/images" -F extra_images=@a.jpg -F extra_images=@b.jpg  # 追加画像
gapi -X POST "$GARDEN_API_URL/crops" -H 'Content-Type: application/json' -d '{"nmae":"x"}'   # → 422 の例
```
````

```bash
git add app/api tests/api/test_api_crops.py docs/api/curl-examples.md
git commit -m "外部API: リソース共通処理と作物APIを追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 品種 API・/lookup・/meta

**Files:**
- Create: `app/api/varieties.py`
- Modify: `app/api/meta.py`, `app/api/__init__.py`
- Test: `tests/api/test_api_varieties_lookup.py`

**Interfaces:**
- Consumes: `Resource`, `register`, `page_arg`, `like_pattern`, `LIKE_ESCAPE`（Task 5）、`choices.*`、`serialize.display_name`, `web_url`, `image_url`、`REF_CROP`
- Produces: `GET /api/v1/varieties...`、`GET /api/v1/lookup`、`GET /api/v1/meta`、`meta.RESOURCE_NAMES`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_varieties_lookup.py`:

```python
import pytest


@pytest.fixture
def tomato(api):
    return api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科',
                                           'image_color': '#FF0000'}).get_json()['data']


def _variety(api, crop_id, name='アイコ', **extra):
    res = api.post('/api/v1/varieties', json={'crop_id': crop_id, 'name': name, **extra})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_variety_inherits_appearance(api, tomato):
    data = _variety(api, tomato['id'])
    assert data['crop'] == {'id': tomato['id'], 'name': 'トマト'}
    assert data['display_name'] == 'アイコ（トマト）'
    assert data['image_color'] is None
    assert data['effective_image_color'] == '#FF0000'
    assert data['web_url'].endswith(f'/varieties/{data["id"]}')


def test_create_variety_with_unknown_crop(api):
    res = api.post('/api/v1/varieties', json={'crop_id': 999, 'name': 'アイコ'})
    assert res.status_code == 422
    reason = res.get_json()['error']['details'][0]['reason']
    assert 'ID 999 の作物は存在しません' in reason
    assert '/api/v1/lookup' in reason


def test_patch_name_keeps_inherited_fields_null(api, tomato, sql):
    variety = _variety(api, tomato['id'])
    res = api.patch(f'/api/v1/varieties/{variety["id"]}', json={'name': 'アイコ2'})
    assert res.status_code == 200
    row = sql('SELECT icon_path, image_color, image_path FROM varieties WHERE id = ?', (variety['id'],))[0]
    assert row == {'icon_path': None, 'image_color': None, 'image_path': None}


def test_patch_variety_parent(api, tomato):
    other = api.post('/api/v1/crops', json={'name': 'ミニトマト', 'crop_type': 'ナス科'}).get_json()['data']
    variety = _variety(api, tomato['id'])
    data = api.patch(f'/api/v1/varieties/{variety["id"]}', json={'crop_id': other['id']}).get_json()['data']
    assert data['crop']['name'] == 'ミニトマト'


def test_list_varieties_by_crop(api, tomato):
    other = api.post('/api/v1/crops', json={'name': 'なす', 'crop_type': 'ナス科'}).get_json()['data']
    _variety(api, tomato['id'], 'アイコ')
    _variety(api, other['id'], '千両二号')
    names = [v['name'] for v in api.get(f'/api/v1/varieties?crop_id={tomato["id"]}').get_json()['data']]
    assert names == ['アイコ']
    names = [v['name'] for v in api.get('/api/v1/varieties?q=なす').get_json()['data']]
    assert names == ['千両二号']  # 作物名でも検索できる


def test_lookup_ranks_exact_then_prefix_then_partial(api, tomato):
    api.post('/api/v1/crops', json={'name': 'ミニトマト', 'crop_type': 'ナス科'})
    _variety(api, tomato['id'], 'トマトベリー')
    body = api.get('/api/v1/lookup?q=トマト').get_json()
    assert [(i['type'], i['name']) for i in body['data']] == [
        ('crop', 'トマト'), ('variety', 'トマトベリー'), ('crop', 'ミニトマト')]
    berry = body['data'][1]
    assert berry['display_name'] == 'トマトベリー（トマト）'
    assert berry['crop_id'] == tomato['id']


def test_lookup_filters_types_and_validates(api, tomato, sql):
    sql("INSERT INTO locations (name, location_type) VALUES ('トマト棚', 'プランター')")
    body = api.get('/api/v1/lookup?q=トマト&types=location').get_json()
    assert [(i['type'], i['name']) for i in body['data']] == [('location', 'トマト棚')]
    res = api.get('/api/v1/lookup?types=plant')
    assert res.status_code == 422
    assert {d['field'] for d in res.get_json()['error']['details']} == {'q', 'types'}


@pytest.mark.parametrize('q', ['%', '_'])
def test_wildcards_are_literal(api, tomato, q):
    assert api.get(f'/api/v1/lookup?q={q}').get_json()['data'] == []
    assert api.get(f'/api/v1/crops?q={q}').get_json()['data'] == []


def test_meta(api, tomato):
    data = api.get('/api/v1/meta').get_json()['data']
    assert data['crop_types'] == ['ナス科']
    assert data['task_statuses'] == ['pending', 'in_progress', 'completed']
    assert data['planting_statuses'] == ['active', 'harvested', 'removed']
    assert data['sun_exposures'] == ['全日', '半日', '日陰']
    assert len(data['crop_icons']) > 0
    assert data['relation_keys']['cooking_records'] == ['crop_ids', 'variety_ids', 'planting_ids', 'harvest_ids']
    assert 'crops' in data['resources']
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_varieties_lookup.py -v`
Expected: FAIL（404 など）

- [ ] **Step 3: 品種リソースを書く**

`app/api/varieties.py`:

```python
"""品種 API（/api/v1/varieties）"""
from app.api import bp
from app.api.choices import crop_icons
from app.api.resource import Resource, register
from app.api.serialize import display_name, image_url
from app.api.validation import REF_CROP, Field
from app.models.variety import Variety


class VarietyResource(Resource):
    name = 'varieties'
    label = '品種'
    model = Variety
    web_path = '/varieties/{id}'
    image_folder = 'varieties'
    usage_type = 'variety'
    supplement_type = 'variety'
    fields = {
        'crop_id': Field('ref', required=True, ref=REF_CROP),
        'name': Field('str', required=True, max_len=100),
        'notes': Field('str'),
        # 外観3項目は未設定なら親作物から継承（NULL のまま保存する）
        'icon_path': Field('enum', choices=crop_icons),
        'image_color': Field('color'),
    }
    list_from = 'varieties v JOIN crops c ON v.crop_id = c.id'
    list_id = 'v.id'
    list_order = 'c.name, v.name, v.id'
    search_columns = ('v.name', 'c.name')
    filters = {'crop_id': ('v.crop_id = ?', Field('int', min_value=1))}

    def describe(self, row):
        effective = Variety.apply_inheritance(dict(row))
        return {
            'crop': {'id': row['crop_id'], 'name': row['crop_name']},
            'display_name': display_name(row['crop_name'], row['name']),
            'effective_icon_path': effective['effective_icon_path'],
            'effective_image_color': effective['effective_image_color'],
            'effective_image_url': image_url(effective['effective_image_path']),
        }


register(bp, VarietyResource())
```

- [ ] **Step 4: /meta と /lookup を書く**

`app/api/meta.py` 全体:

```python
"""疎通確認・選択肢一覧・名前検索"""
from flask import current_app, request

from app.api import bp
from app.api.choices import (
    COOKING_RELATION_KEYS, DIARY_RELATION_KEYS, PLANTING_STATUSES, SUN_EXPOSURES,
    TASK_RELATION_KEYS, TASK_STATUSES, WEATHERS, bg_images, crop_icons, distinct_values,
)
from app.api.errors import detail, ok, validation_error
from app.api.resource import LIKE_ESCAPE, like_pattern, page_arg
from app.api.serialize import display_name, web_url
from app.database import get_db

RESOURCE_NAMES = ['crops', 'varieties', 'locations', 'plantings', 'planting_records', 'harvests',
                  'cooking_records', 'diary_entries', 'tasks', 'photos']
LOOKUP_TYPES = ('crop', 'variety', 'location')


@bp.get('/health')
def health():
    return ok({'status': 'ok'})


@bp.get('/meta')
def meta():
    """エージェントが最初に読む選択肢の一覧"""
    return ok({
        'resources': RESOURCE_NAMES,
        'date_format': 'YYYY-MM-DD',
        'planting_statuses': PLANTING_STATUSES,
        'task_statuses': TASK_STATUSES,
        'sun_exposures': SUN_EXPOSURES,
        'weathers': WEATHERS,
        'crop_types': distinct_values('crops', 'crop_type'),
        'location_types': distinct_values('locations', 'location_type'),
        'harvest_units': distinct_values('harvests', 'unit'),
        'cooking_categories': distinct_values('cooking', 'category'),
        'crop_icons': crop_icons(),
        'bg_images': bg_images(),
        'relation_keys': {
            'diary_entries': list(DIARY_RELATION_KEYS),
            'cooking_records': list(COOKING_RELATION_KEYS),
            'tasks': list(TASK_RELATION_KEYS),
        },
        'image_formats': ['jpeg', 'png', 'gif', 'webp'],
        'max_image_mb': current_app.config['API_MAX_IMAGE_MB'],
    })


def _rank(name, q):
    n, k = name.casefold(), q.casefold()
    return 0 if n == k else 1 if n.startswith(k) else 2


@bp.get('/lookup')
def lookup():
    """作物・品種・場所を名前で横断検索（完全一致 → 前方一致 → 部分一致）"""
    args = request.args
    errors = [detail(k, '未知の検索条件です。使える条件: q, types, limit')
              for k in args if k not in ('q', 'types', 'limit')]
    q = args.get('q', '').strip()
    if not q:
        errors.append(detail('q', '検索する名前を指定してください（例: q=ミニトマト）'))
    types_raw = args.get('types')
    types = [t.strip() for t in types_raw.split(',')] if types_raw else list(LOOKUP_TYPES)
    if any(t not in LOOKUP_TYPES for t in types):
        errors.append(detail('types', 'crop, variety, location をカンマ区切りで指定してください', types_raw))
    limit = page_arg(args, 'limit', 20, 1, 100, errors)
    if errors:
        raise validation_error(errors)

    db = get_db()
    pattern = like_pattern(q)
    items = []
    if 'crop' in types:
        for r in db.execute(f'SELECT id, name, crop_type FROM crops WHERE name LIKE ? {LIKE_ESCAPE}', (pattern,)):
            items.append({'type': 'crop', 'id': r['id'], 'name': r['name'], 'display_name': r['name'],
                          'crop_type': r['crop_type'], 'web_url': web_url(f'/crops/{r["id"]}')})
    if 'variety' in types:
        for r in db.execute(
                f'''SELECT v.id, v.name, v.crop_id, c.name AS crop_name
                    FROM varieties v JOIN crops c ON v.crop_id = c.id
                    WHERE v.name LIKE ? {LIKE_ESCAPE}''', (pattern,)):
            items.append({'type': 'variety', 'id': r['id'], 'name': r['name'],
                          'display_name': display_name(r['crop_name'], r['name']),
                          'crop_id': r['crop_id'], 'web_url': web_url(f'/varieties/{r["id"]}')})
    if 'location' in types:
        for r in db.execute(f'SELECT id, name, location_type FROM locations WHERE name LIKE ? {LIKE_ESCAPE}',
                            (pattern,)):
            items.append({'type': 'location', 'id': r['id'], 'name': r['name'], 'display_name': r['name'],
                          'location_type': r['location_type'], 'web_url': web_url(f'/locations/{r["id"]}')})

    order = {t: i for i, t in enumerate(LOOKUP_TYPES)}
    items.sort(key=lambda it: (_rank(it['name'], q), order[it['type']], it['name']))
    return ok(items[:limit], meta={'total': len(items), 'limit': limit})
```

`app/api/__init__.py` の import 行:

```python
    from app.api import meta, crops, varieties  # noqa: F401
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run python -m pytest tests/api -v`
Expected: PASS

- [ ] **Step 6: curl 例を追記してコミット**

`docs/api/curl-examples.md` に追記:

````markdown
## 選択肢・名前検索

```bash
gapi "$GARDEN_API_URL/meta"                                   # 選択肢の一覧（最初に読む）
gapi -G "$GARDEN_API_URL/lookup" --data-urlencode 'q=ミニトマト'  # 名前 → ID
gapi -G "$GARDEN_API_URL/lookup" --data-urlencode 'q=南' -d types=location
```

## 品種（/varieties）

```bash
gapi "$GARDEN_API_URL/varieties?crop_id=1"
gapi -X POST "$GARDEN_API_URL/varieties" -H 'Content-Type: application/json' \
     -d '{"crop_id":1,"name":"アイコ"}'
gapi -X PATCH "$GARDEN_API_URL/varieties/3" -H 'Content-Type: application/json' -d '{"notes":"甘い"}'
```
````

```bash
git add app/api tests/api/test_api_varieties_lookup.py docs/api/curl-examples.md
git commit -m "外部API: 品種API・名前検索（/lookup）・選択肢一覧（/meta）を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 場所 API

**Files:**
- Create: `app/api/locations.py`
- Modify: `app/api/__init__.py`
- Test: `tests/api/test_api_locations.py`

**Interfaces:**
- Consumes: `Resource`, `register`（Task 5）、`SUN_EXPOSURES`, `bg_images`、`serialize.planting_label`、`_CV_JOIN`（`app.models.planting`）
- Produces: `/api/v1/locations...`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_locations.py`:

```python
import json


def _create(api, **payload):
    res = api.post('/api/v1/locations', json={'name': '南の畑', 'location_type': '畑', **payload})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_location(api):
    data = _create(api, area_size='12.5', sun_exposure='全日')
    assert data['area_size'] == 12.5
    assert data['sun_exposure'] == '全日'
    assert data['active_plantings'] == []
    assert 'canvas_data' not in data


def test_create_location_validation(api):
    res = api.post('/api/v1/locations', json={
        'name': '畑', 'location_type': '畑', 'area_size': -1, 'sun_exposure': '晴れ',
        'bg_image': 'nope.webp', 'canvas_data': '{}'})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'area_size', 'sun_exposure', 'bg_image', 'canvas_data'}


def test_patch_keeps_canvas_data(api, sql):
    location = _create(api)
    canvas = json.dumps({'version': '2.0', 'placements': []})
    sql('UPDATE locations SET canvas_data = ? WHERE id = ?', (canvas, location['id']))
    res = api.patch(f'/api/v1/locations/{location["id"]}', json={'name': '北の畑'})
    assert res.get_json()['data']['name'] == '北の畑'
    assert sql('SELECT canvas_data FROM locations WHERE id = ?', (location['id'],))[0]['canvas_data'] == canvas


def test_location_lists_active_plantings(api, sql):
    location = _create(api)
    crop_id = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    planting_id = sql("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                      (location['id'], crop_id))
    sql("INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'harvested')",
        (location['id'], crop_id))
    data = api.get(f'/api/v1/locations/{location["id"]}').get_json()['data']
    assert data['active_plantings'] == [
        {'id': planting_id, 'display_name': 'トマト / 南の畑（2026-05-01 植え付け）'}]


def test_list_locations(api):
    _create(api, name='南の畑')
    _create(api, name='ベランダ', location_type='プランター')
    names = [l['name'] for l in api.get('/api/v1/locations?location_type=プランター').get_json()['data']]
    assert names == ['ベランダ']
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_locations.py -v`
Expected: FAIL

- [ ] **Step 3: 実装**

`app/api/locations.py`:

```python
"""場所 API（/api/v1/locations）"""
from app.api import bp
from app.api.choices import SUN_EXPOSURES, bg_images
from app.api.resource import Resource, register
from app.api.serialize import planting_label
from app.api.validation import Field
from app.database import get_db
from app.models.location import Location
from app.models.planting import _CV_JOIN


class LocationResource(Resource):
    name = 'locations'
    label = '場所'
    model = Location
    web_path = '/locations/{id}'
    image_folder = 'locations'
    usage_type = 'location'
    supplement_type = 'location'
    fields = {
        'name': Field('str', required=True, max_len=100),
        'location_type': Field('str', required=True, max_len=50),
        'area_size': Field('decimal', min_value=0),
        'sun_exposure': Field('enum', choices=SUN_EXPOSURES),
        'notes': Field('str'),
        'bg_image': Field('enum', choices=bg_images),
    }
    read_only = ('canvas_data',)  # 見取り図は画面専用
    list_from = 'locations l'
    list_id = 'l.id'
    list_order = 'l.name, l.id'
    search_columns = ('l.name',)
    filters = {'location_type': ('l.location_type = ?', Field('str'))}

    def describe(self, row):
        rows = get_db().execute(
            f'''SELECT lc.id, lc.planted_date, cv.crop_name, cv.variety, l.name AS location_name
                FROM plantings lc {_CV_JOIN} JOIN locations l ON lc.location_id = l.id
                WHERE lc.location_id = ? AND lc.status = 'active'
                ORDER BY lc.planted_date, lc.id''', (row['id'],)
        ).fetchall()
        return {'active_plantings': [{'id': r['id'], 'display_name': planting_label(dict(r))} for r in rows]}


register(bp, LocationResource())
```

`app/api/__init__.py` の import 行:

```python
    from app.api import meta, crops, varieties, locations  # noqa: F401
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run python -m pytest tests/api -v`
Expected: PASS

- [ ] **Step 5: curl 例を追記してコミット**

````markdown
## 場所（/locations）

```bash
gapi "$GARDEN_API_URL/locations"
gapi -X POST "$GARDEN_API_URL/locations" -F 'data={"name":"ベランダ","location_type":"プランター","sun_exposure":"半日"}' -F image=@veranda.jpg
gapi -X PATCH "$GARDEN_API_URL/locations/2" -H 'Content-Type: application/json' -d '{"area_size":3.5}'
```
````

```bash
git add app/api tests/api/test_api_locations.py docs/api/curl-examples.md
git commit -m "外部API: 場所APIを追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: 植え付け API と栽培終了

**Files:**
- Modify: `app/models/planting.py`（`Planting.end_cultivation` を追加）
- Modify: `app/routes/planting_routes.py:96-126`（CRLF を保つ）
- Create: `app/api/plantings.py`
- Modify: `app/api/__init__.py`
- Test: `tests/api/test_api_plantings.py`, `tests/test_planting_end.py`

**Interfaces:**
- Consumes: `Resource`, `register`, `load_or_404`（Task 5）、`parse_request`, `validate_payload`, `detail`, `validation_error`, `ok`、`PLANTING_STATUSES`、`REF_LOCATION`, `REF_CROP`, `REF_VARIETY`
- Produces:
  - `Planting.end_cultivation(location_crop_id, location_id, end_date=None)`
  - `/api/v1/plantings...`、`POST /api/v1/plantings/<id>/end`
  - `app.api.plantings.PLANTINGS`（リソースのインスタンス）

- [ ] **Step 1: 画面側の回帰テストを書く**

`tests/test_planting_end.py`:

```python
"""栽培終了（画面）: 見取り図のスナップショット保存と配置解除"""
import json

from app.database import get_db


def test_end_cultivation_route_snapshots_and_unplaces(app, client):
    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        planting_id = db.execute('INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
                                 (location_id, crop_id)).lastrowid
        canvas = {'version': '2.0', 'placements': [{'locationCropId': planting_id, 'x': 1, 'y': 2}]}
        db.execute('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), location_id))
        db.commit()

    res = client.post(f'/plantings/{planting_id}/end', data={'end_date': '2026-10-01'})
    assert res.status_code == 302

    with app.app_context():
        db = get_db()
        p = db.execute('SELECT status, end_date, canvas_snapshot FROM plantings WHERE id = ?',
                       (planting_id,)).fetchone()
        assert p['status'] == 'harvested'
        assert str(p['end_date']) == '2026-10-01'
        assert json.loads(p['canvas_snapshot'])['placements'][0]['locationCropId'] == planting_id
        loc = db.execute('SELECT canvas_data FROM locations WHERE id = ?', (location_id,)).fetchone()
        assert json.loads(loc['canvas_data'])['placements'] == []
```

- [ ] **Step 2: 回帰テストが現状で通ることを確認（リファクタ前の基準）**

Run: `uv run python -m pytest tests/test_planting_end.py -v`
Expected: PASS（既存ルートの挙動を固定する）

- [ ] **Step 3: モデルに `end_cultivation` を追加し、ルートを置き換える**

`app/models/planting.py` の `harvest()` の直後に追加:

```python
    @staticmethod
    def end_cultivation(location_crop_id, location_id, end_date=None):
        """栽培終了: 見取り図に配置されていればスナップショットを残し、配置を外す（画面と API で共用）"""
        from app.models.location import Location

        canvas_data = Location.get_canvas_data(location_id)
        snapshot = None
        if canvas_data and 'placements' in canvas_data:
            if any(p.get('locationCropId') == location_crop_id for p in canvas_data['placements']):
                snapshot = canvas_data
        Planting.harvest(location_crop_id, end_date=end_date, canvas_snapshot=snapshot)
        Location.remove_from_canvas(location_id, location_crop_id)
```

`app/routes/planting_routes.py` の `end_cultivation` 内の `try:` ブロックを次に置き換える（CRLF を保つ）:

```python
    try:
        end_date = request.form.get('end_date') or None
        Planting.end_cultivation(location_crop_id, location_crop['location_id'], end_date)
        flash('栽培を終了しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
```

置き換え後、`planting_routes.py` で `Location` がほかに使われていなければ import も削除する（`grep -n "Location\." app/routes/planting_routes.py` で確認）。`git diff --stat` で差分行数が妥当か確認。

Run: `uv run python -m pytest tests/test_planting_end.py -v`
Expected: PASS

- [ ] **Step 4: API の失敗するテストを書く**

`tests/api/test_api_plantings.py`:

```python
import json

import pytest


@pytest.fixture
def base(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    eggplant = sql("INSERT INTO crops (name, crop_type) VALUES ('なす', 'ナス科')")
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    return {'crop': crop, 'variety': variety, 'eggplant': eggplant, 'location': location}


def _plant(api, **payload):
    res = api.post('/api/v1/plantings', json=payload)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_by_crop(api, base):
    data = _plant(api, location_id=base['location'], crop_id=base['crop'],
                  planted_date='2026-05-01', quantity='3')
    assert data['crop'] == {'id': base['crop'], 'name': 'トマト'}
    assert data['variety'] is None
    assert data['display_name'] == 'トマト'
    assert data['location'] == {'id': base['location'], 'name': '南の畑'}
    assert data['status'] == 'active'
    assert data['quantity'] == 3
    assert data['web_url'].endswith(f'/plantings/{data["id"]}')


def test_create_by_variety(api, base):
    data = _plant(api, location_id=base['location'], variety_id=base['variety'])
    assert data['crop_id'] is None
    assert data['variety'] == {'id': base['variety'], 'name': 'アイコ'}
    assert data['crop'] == {'id': base['crop'], 'name': 'トマト'}
    assert data['display_name'] == 'アイコ（トマト）'


@pytest.mark.parametrize('payload, field', [
    ({'crop_id': 'C', 'variety_id': 'V'}, 'variety_id'),   # 両方
    ({}, 'crop_id'),                                       # どちらも無し
])
def test_create_requires_exactly_one_of_crop_or_variety(api, base, payload, field):
    payload = {k: base['crop'] if v == 'C' else base['variety'] for k, v in payload.items()}
    res = api.post('/api/v1/plantings', json={'location_id': base['location'], **payload})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == field


def test_create_rejects_status_and_end_date(api, base):
    res = api.post('/api/v1/plantings', json={'location_id': base['location'], 'crop_id': base['crop'],
                                              'status': 'harvested'})
    assert res.status_code == 422
    res = api.post('/api/v1/plantings', json={'location_id': base['location'], 'crop_id': base['crop'],
                                              'end_date': '2026-10-01'})
    assert res.status_code == 422
    assert '/end' in res.get_json()['error']['details'][0]['reason']


def test_patch_switch_crop_to_variety(api, base):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'], notes='メモ')
    data = api.patch(f'/api/v1/plantings/{planting["id"]}',
                     json={'variety_id': base['variety']}).get_json()['data']
    assert data['crop_id'] is None
    assert data['variety_id'] == base['variety']
    assert data['notes'] == 'メモ'


def test_end_planting(api, base, sql):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'])
    canvas = {'version': '2.0', 'placements': [{'locationCropId': planting['id']}]}
    sql('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), base['location']))
    res = api.post(f'/api/v1/plantings/{planting["id"]}/end', json={'end_date': '2026-10-01'})
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['status'] == 'harvested'
    assert data['end_date'] == '2026-10-01'
    canvas_now = json.loads(sql('SELECT canvas_data FROM locations WHERE id = ?', (base['location'],))[0]['canvas_data'])
    assert canvas_now['placements'] == []
    # 2回目は 422（active ではない）
    res = api.post(f'/api/v1/plantings/{planting["id"]}/end', json={})
    assert res.status_code == 422


def test_end_planting_defaults_to_today(api, base):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'])
    data = api.post(f'/api/v1/plantings/{planting["id"]}/end').get_json()['data']
    assert data['end_date'] is not None


def test_patch_end_date_only_when_harvested(api, base):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'])
    res = api.patch(f'/api/v1/plantings/{planting["id"]}', json={'end_date': '2026-10-02'})
    assert res.status_code == 422
    api.post(f'/api/v1/plantings/{planting["id"]}/end', json={'end_date': '2026-10-01'})
    data = api.patch(f'/api/v1/plantings/{planting["id"]}',
                     json={'end_date': '2026-10-02', 'notes': '終了'}).get_json()['data']
    assert data['end_date'] == '2026-10-02'
    assert data['notes'] == '終了'


def test_list_plantings(api, base):
    a = _plant(api, location_id=base['location'], crop_id=base['crop'], planted_date='2026-05-01')
    b = _plant(api, location_id=base['location'], variety_id=base['variety'], planted_date='2026-05-02')
    c = _plant(api, location_id=base['location'], crop_id=base['eggplant'], planted_date='2026-05-03')
    api.post(f'/api/v1/plantings/{c["id"]}/end')

    ids = lambda url: [p['id'] for p in api.get(url).get_json()['data']]  # noqa: E731
    assert ids('/api/v1/plantings') == [b['id'], a['id']]                        # 既定は active
    assert ids('/api/v1/plantings?status=all') == [c['id'], b['id'], a['id']]
    assert ids(f'/api/v1/plantings?crop_id={base["crop"]}') == [b['id'], a['id']]  # 品種経由も含む
    assert ids('/api/v1/plantings?q=アイコ') == [b['id']]
    assert ids('/api/v1/plantings?status=all&q=南の畑') == [c['id'], b['id'], a['id']]
    assert api.get('/api/v1/plantings?status=done').status_code == 422
```

- [ ] **Step 5: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_plantings.py -v`
Expected: FAIL

- [ ] **Step 6: 実装**

`app/api/plantings.py`:

```python
"""植え付け API（/api/v1/plantings）

作物で植えた場合は crop_id のみ、品種で植えた場合は variety_id のみを持つ（DB の CHECK 制約）。
status は直接変更させず、栽培終了は POST /plantings/{id}/end で見取り図の処理も含めて行う。
"""
from flask import g

from app.api import bp
from app.api.choices import PLANTING_STATUSES
from app.api.errors import detail, ok, validation_error
from app.api.payload import parse_request
from app.api.resource import Resource, load_or_404, register
from app.api.serialize import display_name
from app.api.validation import REF_CROP, REF_LOCATION, REF_VARIETY, Field, validate_payload
from app.models.planting import _CV_JOIN, Planting


class PlantingResource(Resource):
    name = 'plantings'
    label = '植え付け'
    model = Planting
    web_path = '/plantings/{id}'
    fields = {
        'location_id': Field('ref', required=True, ref=REF_LOCATION),
        'crop_id': Field('ref', ref=REF_CROP),
        'variety_id': Field('ref', ref=REF_VARIETY),
        'planted_date': Field('date'),
        'quantity': Field('int', min_value=0),
        'notes': Field('str'),
        'end_date': Field('date'),
    }
    read_only = ('status', 'position_x', 'position_y', 'canvas_snapshot')
    list_from = f'plantings lc {_CV_JOIN} JOIN locations l ON lc.location_id = l.id'
    list_id = 'lc.id'
    list_order = 'lc.planted_date IS NULL, lc.planted_date DESC, lc.id DESC'
    search_columns = ('cv.crop_name', 'cv.variety', 'l.name')
    filters = {
        'crop_id': ('cv.effective_crop_id = ?', Field('int', min_value=1)),
        'variety_id': ('lc.variety_id = ?', Field('int', min_value=1)),
        'location_id': ('lc.location_id = ?', Field('int', min_value=1)),
    }
    extra_list_args = ('status',)

    def insert(self, model_data):
        return Planting.plant(model_data)

    def save(self, obj_id, model_data, row):
        Planting.update_all(obj_id, model_data)
        if row['status'] == 'harvested':
            Planting.update_end_date_notes(obj_id, model_data['end_date'], model_data['notes'])

    def check(self, values, merged, row, errors):
        if values.get('crop_id') and values.get('variety_id'):
            errors.append(detail('variety_id', '作物で植えた場合は crop_id のみ、品種で植えた場合は variety_id のみを'
                                               '指定してください（両方は指定できません）'))
            return
        if values.get('variety_id'):
            merged['crop_id'] = None
        elif values.get('crop_id'):
            merged['variety_id'] = None
        if not merged.get('crop_id') and not merged.get('variety_id'):
            errors.append(detail('crop_id', 'crop_id（作物）か variety_id（品種）のどちらか一方を指定してください'))
        if 'end_date' in values:
            if row is None:
                errors.append(detail('end_date', '作成時は指定できません。栽培終了は POST /api/v1/plantings/{id}/end で行ってください'))
            elif row['status'] != 'harvested':
                errors.append(detail('end_date', '栽培中の植え付けの終了日は変更できません。'
                                                 '栽培終了は POST /api/v1/plantings/{id}/end で行ってください'))

    def list_where(self, args, where, params, errors):
        status = args.get('status', 'active')
        if status == 'all':
            return
        if status not in PLANTING_STATUSES:
            errors.append(detail('status', f'次のいずれかで指定してください: {", ".join([*PLANTING_STATUSES, "all"])}', status))
            return
        where.append('lc.status = ?')
        params.append(status)

    def describe(self, row):
        return {
            'status': row['status'],
            'display_name': display_name(row['crop_name'], row['variety']),
            'crop': {'id': row['effective_crop_id'], 'name': row['crop_name']},
            'variety': {'id': row['variety_id'], 'name': row['variety']} if row['variety_id'] else None,
            'location': {'id': row['location_id'], 'name': row['location_name']},
            'days_from_planting': row.get('days_from_planting'),
        }


PLANTINGS = PlantingResource()
register(bp, PLANTINGS)


@bp.post('/plantings/<int:obj_id>/end')
def end_planting(obj_id):
    """栽培終了（見取り図のスナップショット保存・配置解除を含む）"""
    row = load_or_404(PLANTINGS, obj_id)
    g.api_target_id = obj_id
    payload, _ = parse_request()
    values, errors = validate_payload({'end_date': Field('date')}, payload, creating=False)
    if row['status'] != 'active':
        errors.append(detail('status', f'栽培中（active）の植え付けだけ終了できます（現在: {row["status"]}）'))
    if errors:
        raise validation_error(errors)
    Planting.end_cultivation(obj_id, row['location_id'], values.get('end_date'))
    return ok(PLANTINGS.serialize(PLANTINGS.fetch(obj_id)))
```

`app/api/__init__.py` の import 行:

```python
    from app.api import meta, crops, varieties, locations, plantings  # noqa: F401
```

- [ ] **Step 7: テストが通ることを確認**

Run: `uv run python -m pytest -v`
Expected: PASS（既存テスト・画面の回帰テストを含む全件）

- [ ] **Step 8: curl 例を追記してコミット**

````markdown
## 植え付け（/plantings）

```bash
gapi -G "$GARDEN_API_URL/plantings" --data-urlencode 'q=アイコ'          # 栽培中（既定 status=active）
gapi "$GARDEN_API_URL/plantings?status=all&location_id=1"
gapi -X POST "$GARDEN_API_URL/plantings" -H 'Content-Type: application/json' \
     -d '{"location_id":1,"variety_id":3,"planted_date":"2026-05-01","quantity":2}'
gapi -X PATCH "$GARDEN_API_URL/plantings/5" -H 'Content-Type: application/json' -d '{"quantity":3}'
gapi -X POST "$GARDEN_API_URL/plantings/5/end" -H 'Content-Type: application/json' -d '{"end_date":"2026-10-09"}'
```
````

```bash
git add app/models/planting.py app/routes/planting_routes.py app/api tests/api/test_api_plantings.py tests/test_planting_end.py docs/api/curl-examples.md
git commit -m "外部API: 植え付けAPIと栽培終了を追加（栽培終了処理をモデルへ移して画面と共用）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 栽培記録・収穫 API

**Files:**
- Create: `app/api/planting_records.py`, `app/api/harvests.py`
- Modify: `app/api/__init__.py`
- Test: `tests/api/test_api_records_harvests.py`

**Interfaces:**
- Consumes: `Resource`, `register`（Task 5）、`REF_PLANTING`、`serialize.planting_label`、`_CV_JOIN`
- Produces: `/api/v1/planting_records...`, `/api/v1/harvests...`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_records_harvests.py`:

```python
import pytest

from tests.api.helpers import file_part, image_bytes, multipart


@pytest.fixture
def plantings(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    by_crop = sql("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                  (location, crop))
    by_variety = sql("INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-02')",
                     (location, variety))
    return {'crop': crop, 'by_crop': by_crop, 'by_variety': by_variety}


def test_create_record_with_image(api, plantings):
    form = multipart({'planting_id': plantings['by_variety'], 'recorded_at': '2026-06-01', 'notes': '花が咲いた'},
                     image=file_part(image_bytes('JPEG'), 'flower.jpg'))
    res = api.post('/api/v1/planting_records', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['planting'] == {'id': plantings['by_variety'],
                                'display_name': 'アイコ（トマト） / 南の畑（2026-05-02 植え付け）'}
    assert data['days_from_planting'] == 30
    assert '/static/uploads/growth_records/' in data['image_url']
    assert data['web_url'].endswith(f'/plantings/record/{data["id"]}')
    assert 'extra_images' not in data


def test_record_rejects_extra_images(api, plantings):
    form = multipart({'planting_id': plantings['by_crop'], 'recorded_at': '2026-06-01'},
                     extra_images=file_part(image_bytes(), 'a.png'))
    res = api.post('/api/v1/planting_records', data=form, content_type='multipart/form-data')
    assert res.status_code == 422
    assert '複数件作成' in res.get_json()['error']['details'][0]['reason']


def test_record_planting_cannot_change(api, plantings):
    rec = api.post('/api/v1/planting_records', json={'planting_id': plantings['by_crop'],
                                                     'recorded_at': '2026-06-01'}).get_json()['data']
    res = api.patch(f'/api/v1/planting_records/{rec["id"]}', json={'planting_id': plantings['by_variety']})
    assert res.status_code == 422
    res = api.patch(f'/api/v1/planting_records/{rec["id"]}', json={'notes': '実がついた'})
    assert res.get_json()['data']['notes'] == '実がついた'


def test_list_records(api, plantings):
    for pid, day in ((plantings['by_crop'], '2026-06-01'), (plantings['by_variety'], '2026-06-10')):
        api.post('/api/v1/planting_records', json={'planting_id': pid, 'recorded_at': day})
    ids = lambda url: [r['recorded_at'] for r in api.get(url).get_json()['data']]  # noqa: E731
    assert ids(f'/api/v1/planting_records?planting_id={plantings["by_crop"]}') == ['2026-06-01']
    assert ids(f'/api/v1/planting_records?crop_id={plantings["crop"]}') == ['2026-06-10', '2026-06-01']
    assert ids('/api/v1/planting_records?date_from=2026-06-05') == ['2026-06-10']


def test_create_harvest(api, plantings):
    res = api.post('/api/v1/harvests', json={'planting_id': plantings['by_variety'], 'harvest_date': '2026-07-01',
                                             'quantity': '300', 'unit': 'g'})
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['quantity'] == 300
    assert data['unit'] == 'g'
    assert data['planting']['id'] == plantings['by_variety']
    assert data['extra_images'] == []


def test_harvest_validation(api, plantings):
    res = api.post('/api/v1/harvests', json={'planting_id': 999, 'harvest_date': '7/1', 'quantity': '300g'})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'planting_id', 'harvest_date', 'quantity'}


def test_list_harvests_by_crop(api, plantings):
    api.post('/api/v1/harvests', json={'planting_id': plantings['by_crop'], 'harvest_date': '2026-07-01'})
    api.post('/api/v1/harvests', json={'planting_id': plantings['by_variety'], 'harvest_date': '2026-07-02'})
    data = api.get(f'/api/v1/harvests?crop_id={plantings["crop"]}').get_json()['data']
    assert [h['harvest_date'] for h in data] == ['2026-07-02', '2026-07-01']
    data = api.get('/api/v1/harvests?q=アイコ').get_json()['data']
    assert [h['harvest_date'] for h in data] == ['2026-07-02']
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_records_harvests.py -v`
Expected: FAIL

- [ ] **Step 3: 実装**

`app/api/planting_records.py`:

```python
"""栽培記録 API（/api/v1/planting_records）"""
from app.api import bp
from app.api.errors import detail
from app.api.resource import Resource, register
from app.api.serialize import planting_label
from app.api.validation import REF_PLANTING, Field
from app.models.planting import _CV_JOIN
from app.models.planting_record import PlantingRecord


def planting_ref(row):
    """記録・収穫の行（location_crop_id と植え付けの表示情報を持つ）→ 植え付けの要約"""
    return {'id': row['location_crop_id'], 'display_name': planting_label(row)}


def check_planting_unchanged(values, row, label, errors):
    """既存モデルの update は植え付けを変更しないため、変更要求は誤りにする"""
    if row is not None and 'planting_id' in values and values['planting_id'] != row['location_crop_id']:
        errors.append(detail('planting_id', f'{label}の植え付けは変更できません。'
                                            f'別の植え付けの{label}は新しく作成してください'))


class PlantingRecordResource(Resource):
    name = 'planting_records'
    label = '栽培記録'
    model = PlantingRecord
    web_path = '/plantings/record/{id}'
    image_folder = 'growth_records'
    usage_type = 'planting_record'
    extra_images_hint = '。複数枚の写真は栽培記録を複数件作成してください'
    fields = {
        'planting_id': Field('ref', required=True, ref=REF_PLANTING, column='location_crop_id'),
        'recorded_at': Field('date', required=True),
        'notes': Field('str'),
    }
    list_from = f'planting_records pr JOIN plantings lc ON pr.location_crop_id = lc.id {_CV_JOIN}'
    list_id = 'pr.id'
    list_order = 'pr.recorded_at DESC, pr.id DESC'
    search_columns = ('pr.notes', 'cv.crop_name', 'cv.variety')
    date_column = 'pr.recorded_at'
    filters = {
        'planting_id': ('pr.location_crop_id = ?', Field('int', min_value=1)),
        'crop_id': ('cv.effective_crop_id = ?', Field('int', min_value=1)),
    }

    def check(self, values, merged, row, errors):
        check_planting_unchanged(values, row, self.label, errors)

    def describe(self, row):
        return {'planting': planting_ref(row), 'days_from_planting': row.get('days_from_planting')}


register(bp, PlantingRecordResource())
```

`app/api/harvests.py`:

```python
"""収穫 API（/api/v1/harvests）"""
from app.api import bp
from app.api.planting_records import check_planting_unchanged, planting_ref
from app.api.resource import Resource, register
from app.api.validation import REF_PLANTING, Field
from app.models.harvest import Harvest
from app.models.planting import _CV_JOIN


class HarvestResource(Resource):
    name = 'harvests'
    label = '収穫'
    model = Harvest
    web_path = '/harvests/{id}'
    image_folder = 'harvests'
    usage_type = 'harvest'
    supplement_type = 'harvest'
    fields = {
        'planting_id': Field('ref', required=True, ref=REF_PLANTING, column='location_crop_id'),
        'harvest_date': Field('date', required=True),
        'quantity': Field('decimal', min_value=0),
        'unit': Field('str', max_len=20),
        'notes': Field('str'),
    }
    list_from = f'harvests h JOIN plantings lc ON h.location_crop_id = lc.id {_CV_JOIN}'
    list_id = 'h.id'
    list_order = 'h.harvest_date DESC, h.id DESC'
    search_columns = ('h.notes', 'cv.crop_name', 'cv.variety')
    date_column = 'h.harvest_date'
    filters = {
        'planting_id': ('h.location_crop_id = ?', Field('int', min_value=1)),
        'crop_id': ('cv.effective_crop_id = ?', Field('int', min_value=1)),
    }

    def check(self, values, merged, row, errors):
        check_planting_unchanged(values, row, self.label, errors)

    def describe(self, row):
        return {'planting': planting_ref(row), 'days_from_planting': row.get('days_from_planting')}


register(bp, HarvestResource())
```

`app/api/__init__.py` の import 行:

```python
    from app.api import (  # noqa: F401
        meta, crops, varieties, locations, plantings, planting_records, harvests,
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run python -m pytest tests/api -v`
Expected: PASS（`days_from_planting` の値が合わない場合は `PlantingRecord._calculate_days` の定義（植え付け日を1日目とするか）を確認し、テストの期待値をモデルの定義に合わせる）

- [ ] **Step 5: curl 例を追記してコミット**

````markdown
## 栽培記録（/planting_records）

```bash
gapi "$GARDEN_API_URL/planting_records?planting_id=5"
gapi -X POST "$GARDEN_API_URL/planting_records" \
     -F 'data={"planting_id":5,"recorded_at":"2026-10-09","notes":"花が咲いた"}' -F image=@flower.jpg
```

## 収穫（/harvests）

```bash
gapi "$GARDEN_API_URL/harvests?crop_id=1&date_from=2026-07-01"
gapi -X POST "$GARDEN_API_URL/harvests" \
     -F 'data={"planting_id":5,"harvest_date":"2026-10-09","quantity":300,"unit":"g"}' \
     -F image=@harvest.jpg -F extra_images=@harvest2.jpg
```
````

```bash
git add app/api tests/api/test_api_records_harvests.py docs/api/curl-examples.md
git commit -m "外部API: 栽培記録・収穫APIを追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: 日記・料理・タスク API（関連の部分置き換え）

**Files:**
- Create: `app/api/relations.py`, `app/api/diary_entries.py`, `app/api/cooking_records.py`, `app/api/tasks.py`
- Modify: `app/api/__init__.py`
- Test: `tests/api/test_api_relations.py`

**Interfaces:**
- Consumes: `Resource`, `register`（Task 5）、`REF_*`, `check_ref_id`（Task 3）、`choices.*_RELATION_KEYS`, `TASK_STATUSES`、`serialize.display_name`, `planting_label`, `plain`
- Produces:
  - `relations.RELATION_SPECS`, `read_relations(table, owner_column, owner_id, keys)`, `parse_relations(value, keys, errors)`, `relation_items(relations)`, `RelationsMixin`（クラス属性 `relation_table`, `relation_owner`, `relation_keys`）
  - `/api/v1/diary_entries...`, `/api/v1/cooking_records...`, `/api/v1/tasks...`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_relations.py`:

```python
import pytest

from tests.api.helpers import file_part, image_bytes, multipart


@pytest.fixture
def ids(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    planting = sql("INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')",
                   (location, variety))
    harvest = sql("INSERT INTO harvests (location_crop_id, harvest_date, quantity, unit) "
                  "VALUES (?, '2026-07-01', 300, 'g')", (planting,))
    return {'crop': crop, 'variety': variety, 'location': location, 'planting': planting, 'harvest': harvest}


def test_create_diary_with_relations(api, ids):
    res = api.post('/api/v1/diary_entries', json={
        'title': '初収穫', 'entry_date': '2026-07-01', 'weather': '晴れ',
        'relations': {'crop_ids': [ids['crop']], 'variety_ids': [ids['variety']],
                      'location_ids': [ids['location']], 'planting_ids': [ids['planting']],
                      'harvest_ids': [ids['harvest'], ids['harvest']]}})
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['status'] == 'published'
    assert data['relations'] == {'crop_ids': [ids['crop']], 'variety_ids': [ids['variety']],
                                 'location_ids': [ids['location']], 'planting_ids': [ids['planting']],
                                 'harvest_ids': [ids['harvest']]}  # 重複は1件にまとめる
    names = {(i['type'], i['display_name']) for i in data['relation_items']}
    assert ('variety', 'アイコ（トマト）') in names
    assert ('planting', 'アイコ（トマト） / 南の畑（2026-05-01 植え付け）') in names
    assert ('harvest', 'アイコ（トマト） 2026-07-01 300g') in names
    assert data['web_url'].endswith(f'/diary/{data["id"]}')


def test_patch_replaces_only_sent_relation_keys(api, ids):
    diary = api.post('/api/v1/diary_entries', json={
        'title': 'a', 'entry_date': '2026-07-01',
        'relations': {'crop_ids': [ids['crop']], 'harvest_ids': [ids['harvest']]}}).get_json()['data']
    data = api.patch(f'/api/v1/diary_entries/{diary["id"]}',
                     json={'relations': {'harvest_ids': []}}).get_json()['data']
    assert data['relations']['crop_ids'] == [ids['crop']]
    assert data['relations']['harvest_ids'] == []
    data = api.patch(f'/api/v1/diary_entries/{diary["id"]}', json={'title': 'b'}).get_json()['data']
    assert data['relations']['crop_ids'] == [ids['crop']]  # relations を送らなければ変わらない


def test_relation_validation(api, ids):
    res = api.post('/api/v1/diary_entries', json={
        'title': 'a', 'entry_date': '2026-07-01',
        'relations': {'crop_ids': [999], 'plant_ids': [1], 'variety_ids': 3}})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'relations.crop_ids[0]', 'relations.plant_ids', 'relations.variety_ids'}


def test_cooking_has_no_location_relation(api, ids):
    res = api.post('/api/v1/cooking_records', json={
        'title': 'トマトサラダ', 'cooked_date': '2026-07-02', 'relations': {'location_ids': [ids['location']]}})
    assert res.status_code == 422
    res = api.post('/api/v1/cooking_records', json={
        'title': 'トマトサラダ', 'cooked_date': '2026-07-02', 'category': 'サラダ',
        'relations': {'harvest_ids': [ids['harvest']]}})
    assert res.status_code == 201
    assert res.get_json()['data']['web_url'].endswith('/cooking/1')


def test_task_status_and_images(api, ids):
    task = api.post('/api/v1/tasks', json={'title': '追肥', 'due_date': '2026-10-10',
                                          'relations': {'planting_ids': [ids['planting']]}}).get_json()['data']
    assert task['status'] == 'pending'
    assert 'image_url' not in task
    res = api.patch(f'/api/v1/tasks/{task["id"]}', json={'status': 'done'})
    assert res.status_code == 422
    assert api.patch(f'/api/v1/tasks/{task["id"]}', json={'status': 'completed'}).get_json()['data']['status'] == 'completed'
    form = multipart({'title': '支柱立て'}, image=file_part(image_bytes(), 'a.png'))
    assert api.post('/api/v1/tasks', data=form, content_type='multipart/form-data').status_code == 422
    form = multipart({'title': '支柱立て'}, extra_images=file_part(image_bytes(), 'a.png'))
    res = api.post('/api/v1/tasks', data=form, content_type='multipart/form-data')
    assert res.status_code == 201
    assert len(res.get_json()['data']['extra_images']) == 1


def test_lists(api, ids):
    api.post('/api/v1/diary_entries', json={'title': '芽が出た', 'entry_date': '2026-05-10'})
    api.post('/api/v1/diary_entries', json={'title': '初収穫', 'entry_date': '2026-07-01', 'content': 'おいしい'})
    titles = lambda url: [d['title'] for d in api.get(url).get_json()['data']]  # noqa: E731
    assert titles('/api/v1/diary_entries') == ['初収穫', '芽が出た']
    assert titles('/api/v1/diary_entries?q=おいしい') == ['初収穫']
    assert titles('/api/v1/diary_entries?date_to=2026-06-01') == ['芽が出た']
    api.post('/api/v1/tasks', json={'title': '追肥', 'due_date': '2026-10-10'})
    api.post('/api/v1/tasks', json={'title': '水やり', 'status': 'completed'})
    assert titles('/api/v1/tasks?status=pending') == ['追肥']
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_relations.py -v`
Expected: FAIL

- [ ] **Step 3: relations.py を書く**

`app/api/relations.py`:

```python
"""日記・料理・タスクの関連（多対多）の読み書き

PATCH の relations は「送られたキーだけ置き換え、送られなかったキーは維持」。
保存は各モデルの既存 save_relations()（全削除→再登録）を使う。
"""
from app.api.errors import detail
from app.api.serialize import display_name, plain, planting_label
from app.api.validation import (
    REF_CROP, REF_HARVEST, REF_LOCATION, REF_PLANTING, REF_VARIETY, check_ref_id,
)
from app.database import get_db
from app.models.planting import _CV_JOIN

# API のキー → (relation_type, 関連テーブルの列, 参照先, save_relations のキー, relation_items の type)
RELATION_SPECS = {
    'crop_ids': ('crop', 'crop_id', REF_CROP, 'crop_ids', 'crop'),
    'variety_ids': ('variety', 'variety_id', REF_VARIETY, 'variety_ids', 'variety'),
    'location_ids': ('location', 'location_id', REF_LOCATION, 'location_ids', 'location'),
    'planting_ids': ('location_crop', 'location_crop_id', REF_PLANTING, 'location_crop_ids', 'planting'),
    'harvest_ids': ('harvest', 'harvest_id', REF_HARVEST, 'harvest_ids', 'harvest'),
}


def read_relations(table, owner_column, owner_id, keys):
    db = get_db()
    result = {}
    for key in keys:
        rel_type, column = RELATION_SPECS[key][:2]
        rows = db.execute(
            f'''SELECT {column} FROM {table}
                WHERE {owner_column} = ? AND relation_type = ? AND {column} IS NOT NULL ORDER BY id''',
            (owner_id, rel_type)).fetchall()
        result[key] = [r[0] for r in rows]
    return result


def parse_relations(value, keys, errors):
    """payload['relations'] を検証し、送られたキーだけの {key: [id, ...]} を返す"""
    if not isinstance(value, dict):
        errors.append(detail('relations', f'オブジェクトで指定してください（使えるキー: {", ".join(keys)}）'))
        return {}
    parsed = {}
    for key, ids in value.items():
        field = f'relations.{key}'
        if key not in keys:
            errors.append(detail(field, f'未知のキーです。使えるキー: {", ".join(keys)}'))
            continue
        if not isinstance(ids, list):
            errors.append(detail(field, 'ID の配列で指定してください（例: [1, 2]、全解除は []）'))
            continue
        clean = []
        for i, raw in enumerate(ids):
            obj_id, reason = check_ref_id(RELATION_SPECS[key][2], raw)
            if reason:
                errors.append(detail(f'{field}[{i}]', reason, raw if isinstance(raw, (int, str)) else None))
            elif obj_id not in clean:
                clean.append(obj_id)
        parsed[key] = clean
    return parsed


def _names(item_type, obj_id):
    db = get_db()
    if item_type == 'crop':
        r = db.execute('SELECT name FROM crops WHERE id = ?', (obj_id,)).fetchone()
        return r['name'] if r else None
    if item_type == 'variety':
        r = db.execute('SELECT v.name, c.name AS crop_name FROM varieties v JOIN crops c ON v.crop_id = c.id '
                       'WHERE v.id = ?', (obj_id,)).fetchone()
        return display_name(r['crop_name'], r['name']) if r else None
    if item_type == 'location':
        r = db.execute('SELECT name FROM locations WHERE id = ?', (obj_id,)).fetchone()
        return r['name'] if r else None
    if item_type == 'planting':
        r = db.execute(f'''SELECT lc.planted_date, cv.crop_name, cv.variety, l.name AS location_name
                           FROM plantings lc {_CV_JOIN} JOIN locations l ON lc.location_id = l.id
                           WHERE lc.id = ?''', (obj_id,)).fetchone()
        return planting_label(dict(r)) if r else None
    if item_type == 'harvest':
        r = db.execute(f'''SELECT h.harvest_date, h.quantity, h.unit, cv.crop_name, cv.variety
                           FROM harvests h JOIN plantings lc ON h.location_crop_id = lc.id {_CV_JOIN}
                           WHERE h.id = ?''', (obj_id,)).fetchone()
        if not r:
            return None
        amount = f' {plain(r["quantity"]):g}{r["unit"] or ""}' if r['quantity'] is not None else ''
        return f'{display_name(r["crop_name"], r["variety"])} {plain(r["harvest_date"])}{amount}'
    raise ValueError(item_type)


def relation_items(relations):
    items = []
    for key, ids in relations.items():
        item_type = RELATION_SPECS[key][4]
        for obj_id in ids:
            items.append({'type': item_type, 'id': obj_id, 'display_name': _names(item_type, obj_id)})
    return items


class RelationsMixin:
    """Resource と組み合わせて relations の検証・保存・表示を加える（Resource より先に継承する）"""
    relation_table = ''
    relation_owner = ''
    relation_keys = ()
    reserved_keys = ('relations',)

    def parse_reserved(self, payload, row, errors):
        if 'relations' not in payload:
            return None
        return parse_relations(payload['relations'], self.relation_keys, errors)

    def after_write(self, obj_id, reserved):
        if reserved is None:
            return  # relations が送られていない → 関連は変更しない
        current = read_relations(self.relation_table, self.relation_owner, obj_id, self.relation_keys)
        current.update(reserved)
        self.model.save_relations(obj_id, {RELATION_SPECS[k][3]: v for k, v in current.items()})

    def describe(self, row):
        relations = read_relations(self.relation_table, self.relation_owner, row['id'], self.relation_keys)
        return {**super().describe(row), 'relations': relations, 'relation_items': relation_items(relations)}
```

注: `harvest` の `amount` は `quantity` が `300.0` なら `300g` と表示する（`:g` 書式）。`quantity` が文字列で保存されている古い行で `:g` が失敗する場合は `str()` にフォールバックする try/except を加える。

- [ ] **Step 4: 3つのリソースを書く**

`app/api/diary_entries.py`:

```python
"""日記 API（/api/v1/diary_entries）"""
from app.api import bp
from app.api.choices import DIARY_RELATION_KEYS
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field
from app.models.diary import DiaryEntry


class DiaryEntryResource(RelationsMixin, Resource):
    name = 'diary_entries'
    label = '日記'
    model = DiaryEntry
    web_path = '/diary/{id}'
    image_folder = 'diary'
    usage_type = 'diary'
    supplement_type = 'diary'
    relation_table = 'diary_relations'
    relation_owner = 'diary_id'
    relation_keys = DIARY_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'entry_date': Field('date', required=True),
        'content': Field('str'),
        'weather': Field('str', max_len=50),
        'status': Field('str', max_len=20),
    }
    list_from = 'diary_entries d'
    list_id = 'd.id'
    list_order = 'd.entry_date DESC, d.id DESC'
    search_columns = ('d.title', 'd.content')
    date_column = 'd.entry_date'

    def to_model(self, values):
        data = super().to_model(values)
        data['status'] = data['status'] or 'published'
        return data


register(bp, DiaryEntryResource())
```

`app/api/cooking_records.py`:

```python
"""料理 API（/api/v1/cooking_records）"""
from app.api import bp
from app.api.choices import COOKING_RELATION_KEYS
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field
from app.models.cooking import Cooking


class CookingRecordResource(RelationsMixin, Resource):
    name = 'cooking_records'
    label = '料理'
    model = Cooking
    web_path = '/cooking/{id}'
    image_folder = 'cooking'
    usage_type = 'cooking'
    supplement_type = 'cooking'
    relation_table = 'cooking_relations'
    relation_owner = 'cooking_id'
    relation_keys = COOKING_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'cooked_date': Field('date', required=True),
        'category': Field('str', max_len=100),
        'notes': Field('str'),
    }
    list_from = 'cooking k'
    list_id = 'k.id'
    list_order = 'k.cooked_date DESC, k.id DESC'
    search_columns = ('k.title', 'k.notes')
    date_column = 'k.cooked_date'
    filters = {'category': ('k.category = ?', Field('str'))}


register(bp, CookingRecordResource())
```

`app/api/tasks.py`:

```python
"""タスク API（/api/v1/tasks）"""
from app.api import bp
from app.api.choices import TASK_RELATION_KEYS, TASK_STATUSES
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field
from app.models.task import Task


class TaskResource(RelationsMixin, Resource):
    name = 'tasks'
    label = 'タスク'
    model = Task
    web_path = '/tasks/{id}'
    supplement_type = 'task'  # 本体画像は無く、追加画像（補足情報）のみ
    relation_table = 'task_relations'
    relation_owner = 'task_id'
    relation_keys = TASK_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'description': Field('str'),
        'due_date': Field('date'),
        'status': Field('enum', choices=TASK_STATUSES),
    }
    list_from = 'tasks t'
    list_id = 't.id'
    list_order = 't.due_date IS NULL, t.due_date, t.id'
    search_columns = ('t.title', 't.description')
    date_column = 't.due_date'
    filters = {'status': ('t.status = ?', Field('enum', choices=TASK_STATUSES))}

    def to_model(self, values):
        data = super().to_model(values)
        data['status'] = data['status'] or Task.STATUS_PENDING
        return data


register(bp, TaskResource())
```

`app/api/__init__.py` の import 行:

```python
    from app.api import (  # noqa: F401
        meta, crops, varieties, locations, plantings, planting_records, harvests,
        diary_entries, cooking_records, tasks,
    )
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run python -m pytest tests/api -v`
Expected: PASS

- [ ] **Step 6: curl 例を追記してコミット**

````markdown
## 日記・料理・タスク（関連付き）

```bash
gapi -X POST "$GARDEN_API_URL/diary_entries" \
     -F 'data={"title":"初収穫","entry_date":"2026-10-09","weather":"晴れ","content":"甘かった","relations":{"planting_ids":[5],"harvest_ids":[12]}}' \
     -F image=@diary.jpg
# relations は送ったキーだけ置き換え（[] で全解除、送らないキーはそのまま）
gapi -X PATCH "$GARDEN_API_URL/diary_entries/8" -H 'Content-Type: application/json' -d '{"relations":{"harvest_ids":[]}}'
gapi -X POST "$GARDEN_API_URL/cooking_records" -H 'Content-Type: application/json' \
     -d '{"title":"トマトサラダ","cooked_date":"2026-10-09","category":"サラダ","relations":{"harvest_ids":[12]}}'
gapi -X POST "$GARDEN_API_URL/tasks" -H 'Content-Type: application/json' \
     -d '{"title":"追肥","due_date":"2026-10-10","relations":{"planting_ids":[5]}}'
gapi -X PATCH "$GARDEN_API_URL/tasks/3" -H 'Content-Type: application/json' -d '{"status":"completed"}'
```
````

```bash
git add app/api tests/api/test_api_relations.py docs/api/curl-examples.md
git commit -m "外部API: 日記・料理・タスクAPI（関連の部分置き換え）を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: 写真プール API と photo_pool_id の利用

**Files:**
- Create: `app/api/photos.py`
- Modify: `app/api/__init__.py`
- Test: `tests/api/test_api_photos.py`

**Interfaces:**
- Consumes: `parse_request`, `check_image`, `SavedFiles`, `MAX_FILES_PER_REQUEST`（Task 4）、`page_arg`（Task 5）、`_extract_taken_at`（`app.routes.photo_pool_routes`）、`PhotoPool`
- Produces: `GET/POST /api/v1/photos`, `GET /api/v1/photos/<id>`

- [ ] **Step 1: 失敗するテストを書く**

`tests/api/test_api_photos.py`:

```python
import os

from tests.api.helpers import file_part, image_bytes


def _upload(api, n=1, notes=None):
    form = {'files': [file_part(image_bytes('JPEG'), f'IMG_{i}.jpg') for i in range(n)]}
    if notes:
        form['data'] = '{"notes": "%s"}' % notes
    res = api.post('/api/v1/photos', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_upload_photos(api, api_app):
    photos = _upload(api, 2, notes='畑で撮影')
    assert len(photos) == 2
    assert photos[0]['original_filename'] == 'IMG_0.jpg'
    assert photos[0]['notes'] == '畑で撮影'
    assert photos[0]['usage_count'] == 0
    rel = photos[0]['image_url'].split('/static/uploads/')[1]
    assert rel.startswith('photo_pool/')
    assert os.path.exists(os.path.join(api_app.config['UPLOAD_FOLDER'], rel))


def test_upload_requires_files_and_rejects_heic(api):
    assert api.post('/api/v1/photos', data={}, content_type='multipart/form-data').status_code == 422
    heic = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32
    res = api.post('/api/v1/photos', data={'files': [file_part(heic, 'a.heic')]},
                   content_type='multipart/form-data')
    assert res.status_code == 415


def test_use_pool_photo_for_main_and_extra_images(api, sql):
    p1, p2 = _upload(api, 2)
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科',
                                          'photo_pool_id': p1['id'], 'extra_photo_pool_ids': [p2['id']]})
    assert res.status_code == 201, res.get_json()
    crop = res.get_json()['data']
    assert '/static/uploads/crops/' in crop['image_url']
    assert len(crop['extra_images']) == 1
    usages = sql('SELECT photo_pool_id, entity_type FROM photo_pool_usages ORDER BY id')
    assert usages == [{'photo_pool_id': p1['id'], 'entity_type': 'crop'},
                      {'photo_pool_id': p2['id'], 'entity_type': 'supplement'}]
    detail = api.get(f'/api/v1/photos/{p1["id"]}').get_json()['data']
    assert detail['usage_count'] == 1
    assert detail['usages'][0]['entity_type'] == 'crop'
    unused = api.get('/api/v1/photos?unused=true').get_json()['data']
    assert unused == []


def test_pool_photo_errors(api, api_app):
    (photo,) = _upload(api)
    form = {'data': '{"name":"a","crop_type":"b","photo_pool_id":%d}' % photo['id'],
            'image': file_part(image_bytes(), 'a.png')}
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 422  # image と photo_pool_id の同時指定
    res = api.post('/api/v1/crops', json={'name': 'a', 'crop_type': 'b', 'photo_pool_id': 999})
    assert res.status_code == 422
    rel = photo['image_url'].split('/static/uploads/')[1]
    os.remove(os.path.join(api_app.config['UPLOAD_FOLDER'], rel))
    res = api.post('/api/v1/crops', json={'name': 'a', 'crop_type': 'b', 'photo_pool_id': photo['id']})
    assert res.status_code == 422
    assert '見つかりません' in res.get_json()['error']['details'][0]['reason']


def test_list_photos_validates_args(api):
    _upload(api)
    body = api.get('/api/v1/photos').get_json()
    assert body['meta']['total'] == 1
    assert api.get('/api/v1/photos?unused=yes').status_code == 422
    assert api.get('/api/v1/photos/999').status_code == 404
```

- [ ] **Step 2: 失敗を確認**

Run: `uv run python -m pytest tests/api/test_api_photos.py -v`
Expected: FAIL

- [ ] **Step 3: 実装**

`app/api/photos.py`:

```python
"""写真プール API（/api/v1/photos）

写真を先にプールへ上げ、各リソースの作成・更新で photo_pool_id / extra_photo_pool_ids として使う。
登録に失敗しても写真はプールに残り、後で画面からも使える。
"""
import os

from flask import current_app, g, request

from app.api import bp
from app.api.errors import ApiError, detail, ok, validation_error
from app.api.images import MAX_FILES_PER_REQUEST, SavedFiles, check_image
from app.api.payload import parse_request
from app.api.resource import page_arg
from app.api.serialize import image_url, plain, web_url
from app.api.validation import SQLITE_MAX_INT, Field, validate_payload
from app.models.photo_pool import PhotoPool
from app.routes.photo_pool_routes import _extract_taken_at


def serialize_photo(photo, with_usages=False):
    data = {
        'id': photo['id'],
        'image_url': image_url(photo['image_path']),
        'original_filename': photo['original_filename'],
        'file_size': photo['file_size'],
        'taken_at': plain(photo['taken_at']),
        'notes': photo['notes'],
        'usage_count': photo['usage_count'],
        'created_at': plain(photo['created_at']),
        'web_url': web_url('/photo_pool/'),
    }
    if with_usages:
        data['usages'] = [{'entity_type': u['entity_type'], 'entity_id': u['entity_id'],
                           'created_at': plain(u['created_at'])} for u in PhotoPool.get_usages(photo['id'])]
    return data


@bp.get('/photos')
def list_photos():
    args = request.args
    errors = [detail(k, '未知の検索条件です。使える条件: unused, limit, offset')
              for k in args if k not in ('unused', 'limit', 'offset')]
    unused = args.get('unused', 'false')
    if unused not in ('true', 'false'):
        errors.append(detail('unused', 'true か false で指定してください', unused))
    limit = page_arg(args, 'limit', 50, 1, 200, errors)
    offset = page_arg(args, 'offset', 0, 0, None, errors)
    if errors:
        raise validation_error(errors)
    photos = PhotoPool.get_all()
    if unused == 'true':
        photos = [p for p in photos if p['usage_count'] == 0]
    items = [serialize_photo(p) for p in photos[offset:offset + limit]]
    return ok(items, meta={'total': len(photos), 'limit': limit, 'offset': offset})


@bp.get('/photos/<int:photo_id>')
def get_photo(photo_id):
    photo = PhotoPool.get_by_id(photo_id) if photo_id <= SQLITE_MAX_INT else None
    if not photo:
        raise ApiError(404, 'not_found', f'ID {photo_id} の写真プールの写真は存在しません。GET /api/v1/photos で一覧を確認してください')
    return ok(serialize_photo(photo, with_usages=True))


@bp.post('/photos')
def upload_photos():
    payload, files = parse_request(('files',))
    values, errors = validate_payload({'notes': Field('str')}, payload, creating=True)
    uploads = files['files']
    if not uploads:
        errors.append(detail('files', '画像を1枚以上 files パーツで送ってください'))
    if len(uploads) > MAX_FILES_PER_REQUEST:
        errors.append(detail('files', f'画像は1回のリクエストで{MAX_FILES_PER_REQUEST}枚までです（{len(uploads)}枚）'))
    if errors:
        raise validation_error(errors)
    checked = [check_image(f, 'files') for f in uploads]

    created = []
    upload_folder = current_app.config['UPLOAD_FOLDER']
    with SavedFiles() as saved:
        for c in checked:
            path = saved.save_upload(c, 'photo_pool')
            full = os.path.join(upload_folder, path)
            photo_id = PhotoPool.create(image_path=path, original_filename=c.original_name,
                                        file_size=os.path.getsize(full), taken_at=_extract_taken_at(full))
            saved.keep(path)
            if values.get('notes'):
                PhotoPool.update_notes(photo_id, values['notes'])
            created.append(photo_id)
    g.api_target_id = ','.join(map(str, created))
    return ok([serialize_photo(PhotoPool.get_by_id(i)) for i in created], 201)
```

`app/api/__init__.py` の import 行に `photos` を追加:

```python
    from app.api import (  # noqa: F401
        meta, crops, varieties, locations, plantings, planting_records, harvests,
        diary_entries, cooking_records, tasks, photos,
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run python -m pytest -v`
Expected: PASS（全件）

- [ ] **Step 5: curl 例を追記してコミット**

````markdown
## 写真プール（/photos）

```bash
gapi -X POST "$GARDEN_API_URL/photos" -F files=@IMG_1.jpg -F files=@IMG_2.jpg -F 'data={"notes":"10/9 畑"}'
gapi "$GARDEN_API_URL/photos?unused=true"
# プールの写真を本体画像・追加画像として使う
gapi -X POST "$GARDEN_API_URL/harvests" -H 'Content-Type: application/json' \
     -d '{"planting_id":5,"harvest_date":"2026-10-09","quantity":300,"unit":"g","photo_pool_id":21,"extra_photo_pool_ids":[22]}'
```
````

```bash
git add app/api tests/api/test_api_photos.py docs/api/curl-examples.md
git commit -m "外部API: 写真プールAPIと photo_pool_id による画像指定を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: ドキュメント（リファレンス・FW・移設手順・SKILL.md・CLAUDE.md）

**Files:**
- Create: `docs/api/README.md`, `docs/api/firewall-windows.md`, `docs/api/migration-to-ubuntu.md`, `docs/api/hermes-skill/SKILL.md`
- Modify: `CLAUDE.md`（主な機能・ディレクトリ別ガイド・プロジェクト構造）、`app/routes/CLAUDE.md`（API は `app/api/` にある旨）、`README.md`、`docs/dev-workflow-tips.md`（API の手動確認手順）

**Interfaces:**
- Consumes: Task 1〜11 で実装したエンドポイント・項目名（ドキュメントは実装に合わせる。書く前に `create_api_app` の `url_map` を出力して照合する）

- [ ] **Step 1: 実装済みエンドポイントを出力して照合用に控える**

```bash
uv run python -c "
from app import create_api_app
from app.config import config, TestingConfig
class C(TestingConfig):
    API_TOKEN = 'x' * 40
config['doc'] = C
app = create_api_app('doc')
for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    print(sorted(r.methods - {'HEAD', 'OPTIONS'}), r.rule)
"
```

（`TestingConfig` は `DATABASE=':memory:'` なので実データ DB に触れない）

- [ ] **Step 2: `docs/api/README.md`（API リファレンス）を書く**

構成（各節に実装どおりの内容を書く）:

1. 概要（目的、ベース URL、認証ヘッダー、JSON / multipart の送り方、`data` パーツ）
2. 設定（`.env` の `API_TOKEN` / `API_HOST` / `API_PORT` / `API_MAX_IMAGE_MB` / `WEB_BASE_URL` / `DATABASE`、トークン生成コマンド `uv run python -c "import secrets;print(secrets.token_urlsafe(32))"`、`server.py` で起動すること、`run.py` では API は起動しないこと）
3. レスポンス形式（成功・一覧・エラー、HTTP ステータスと `code` の表）
4. 共通エンドポイント（GET 一覧 / GET 詳細 / POST / PATCH、`limit`・`offset`・`q`、DELETE なし）
5. リソース別の項目表（Task 5〜11 の `fields`・`read_only`・フィルタをそのまま表にする。植え付けの排他、`/end`、記録・収穫の `planting_id` は変更不可、日記の `status` 既定 `published`、タスクの `status` 既定 `pending`）
6. 画像（`image` / `extra_images` / `photo_pool_id` / `extra_photo_pool_ids` / `remove_image`、形式・サイズ・枚数・HEIC 不可、栽培記録は追加画像不可、タスクは追加画像のみ）
7. 関連（`relations` のキー一覧と「送ったキーだけ置き換え」）
8. `/meta`・`/lookup`・`/photos`
9. 監査ログの見方

- [ ] **Step 3: `docs/api/firewall-windows.md` を書く**

設計書 §6 の内容に加え、次の手順を入れる:

```powershell
# 1. ネットワークプロファイルが「プライベート」か確認（パブリックだと Private 用ルールが効かない）
Get-NetConnectionProfile

# 2. 初回起動時に作られた python.exe のプログラム単位許可ルールを確認・無効化
Get-NetFirewallApplicationFilter | Where-Object { $_.Program -like '*python*' } |
  Get-NetFirewallRule | Select-Object DisplayName, Enabled, Direction, Action, Profile
# 該当する Inbound/Allow ルールがあれば無効化（名前を確認してから）
Disable-NetFirewallRule -DisplayName '<上で表示された名前>'

# 3. ポート単位のルールを追加（管理者 PowerShell）
New-NetFirewallRule -DisplayName "Garden API (Hermes only)" -Direction Inbound -Protocol TCP -LocalPort 5001 -RemoteAddress 192.168.11.24 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Garden Web (LAN)"        -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress LocalSubnet   -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Garden Web block Hermes" -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress 192.168.11.24 -Action Block

# 4. .env を設定してサーバーを再起動
#    HOST=0.0.0.0 / API_HOST=0.0.0.0 / API_TOKEN=... / WEB_BASE_URL=http://<このPCのIP>:5000
```

確認手順の表（どこから・どの URL・期待結果）:

| 実行元 | コマンド | 期待 |
|---|---|---|
| Ubuntu (.24) | `curl -sS -H "Authorization: Bearer $T" http://<PC>:5001/api/v1/health` | `{"ok": true, ...}` |
| Ubuntu (.24) | `curl -sS -m 5 http://<PC>:5000/` | タイムアウト（ブロック） |
| スマホ | ブラウザで `http://<PC>:5000/` | 画面が開く |
| スマホ | ブラウザで `http://<PC>:5001/api/v1/health` | 開けない |

元に戻す: `Remove-NetFirewallRule -DisplayName "Garden API (Hermes only)"` など。

- [ ] **Step 4: `docs/api/migration-to-ubuntu.md` を書く**

設計書 §10 の7手順を、コマンド付きで書く。systemd ユニット例:

```ini
# /etc/systemd/system/garden-app.service
[Unit]
Description=Garden app (web :5000 / api 127.0.0.1:5001)
After=network.target

[Service]
User=garden
Group=garden
WorkingDirectory=/opt/garden-app
EnvironmentFile=/opt/garden-app/.env
ExecStart=/home/garden/.local/bin/uv run python server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`.env` 例（移設後）: `HOST=0.0.0.0`、`API_HOST=127.0.0.1`、`API_PORT=5001`、`DATABASE=/opt/garden-app/instance/garden.db`、`WEB_BASE_URL=http://192.168.11.24:5000`、`API_TOKEN=...`、`FLASK_ENV=production`、`SECRET_KEY=...`。

権限: `sudo useradd --system --create-home garden`、`sudo chown -R garden:garden /opt/garden-app`、`sudo chmod 700 /opt/garden-app`、Hermes 実行ユーザーで `ls /opt/garden-app` が Permission denied になること・`sudo -l` で権限が無いことを確認。

ufw: `sudo ufw allow from 192.168.11.0/24 to any port 5000 proto tcp`（5001 は 127.0.0.1 待受のため開けない）。

バックアップ（garden ユーザーの crontab）:

```cron
15 3 * * * sqlite3 /opt/garden-app/instance/garden.db ".backup '/var/backups/garden/garden-$(date +\%a).db'"
30 3 * * * rsync -a --delete /opt/garden-app/app/static/uploads/ /var/backups/garden/uploads/
```

データ移行: Windows 側で `server.py` を停止 → `instance/garden.db` と `app/static/uploads/` を scp → 所有者を garden に変更 → 起動 → `/api/v1/health` と画面で件数を確認。Hermes 側の `GARDEN_API_URL` を `http://127.0.0.1:5001/api/v1` に変更。Windows 側では以後 server.py を起動しない（二重運用でデータが分岐しないよう、Windows 側の DB は退避して名前を変える）。

- [ ] **Step 5: `docs/api/hermes-skill/SKILL.md` を書く**

```markdown
---
name: garden-app
description: 家庭菜園アプリに作物・品種・場所・植え付け・栽培記録・収穫・料理・日記・タスク・写真を登録・更新・検索する。ユーザーが畑の様子、収穫、料理、作業予定、写真を送ってきたときに使う。
---

# 家庭菜園アプリ API

## 接続情報
- ベース URL: 環境変数 `GARDEN_API_URL`（例: `http://127.0.0.1:5001/api/v1`）
- 認証: すべてのリクエストに `Authorization: Bearer $GARDEN_API_TOKEN`
- 呼び出し例: `curl -sS -H "Authorization: Bearer $GARDEN_API_TOKEN" "$GARDEN_API_URL/health"`

## 基本の流れ
1. 初回や選択肢が必要なときは `GET /meta` を読む（ステータス・天気・既存の種類やカテゴリ・使える関連キー）
2. 名前から ID を探す: `GET /lookup?q=<名前>`（作物・品種・場所）。植え付けは `GET /plantings?q=<作物名か場所名>`（既定は栽培中のみ）
3. 候補が複数・0件なら、推測で決めずにユーザーに確認する（例: 「ミニトマトの植え付けが2件あります: 南の畑（5/1）とベランダ（5/3）。どちらですか？」）
4. 作成（POST）または更新（PATCH）する
5. 返ってきた `data.web_url` をユーザーに伝える

## 依頼の対応表
| ユーザーの依頼 | 呼ぶ API |
|---|---|
| 「アイコに花が咲いた（写真）」 | 植え付けを探す → `POST /planting_records`（`planting_id`, `recorded_at`, `notes`, `image`） |
| 「ミニトマト300g収穫」 | 植え付けを探す → `POST /harvests`（`quantity: 300`, `unit: "g"`） |
| 「トマトサラダを作った」 | `POST /cooking_records`（`relations.harvest_ids` に当日の収穫） |
| 「明日追肥する」 | `POST /tasks`（`due_date` は今日の日付から計算） |
| 「今日の畑日記」 | `POST /diary_entries` |
| 「アイコの栽培を終わりにした」 | `POST /plantings/{id}/end` |
| 写真が複数枚 | 1枚目を `image`、残りを `extra_images`（栽培記録は1件1枚なので、枚数分の記録を作るかユーザーに確認） |

## 送り方
- JSON: `-H 'Content-Type: application/json' -d '{...}'`
- 写真付き: `-F 'data={...JSON...}' -F image=@/path/to/photo.jpg -F extra_images=@/path/2.jpg`
- 日付は `YYYY-MM-DD`。数値に単位を付けない（`"quantity": 300, "unit": "g"`）
- PATCH は変えたい項目だけ送る。`relations` は送ったキーだけ置き換わる（`[]` で全解除）

## 守ること
- 削除はできない。削除を頼まれたら「API では削除できないので、アプリの画面から操作してください」と伝え、`web_url` を示す
- PATCH の前に、対象（名前・日付・ID）をユーザーに確認する
- 422 が返ったら `error.details` の `field` と `reason` を読んで直し、再送は1回まで。直せなければユーザーに内容を伝える
- 接続できない（タイムアウト・接続拒否）ときは再送せず、「菜園アプリのサーバー（メインPC）が起動していない可能性があります」と伝える
- POST がタイムアウトしたときは、同じ内容を再送する前に一覧（例: `GET /harvests?date_from=<今日>`）で登録済みか確認する（二重登録防止）
- HEIC は送れない。415 の場合は「写真」として送り直してもらう
```

- [ ] **Step 6: CLAUDE.md 群と README を更新する**

- ルート `CLAUDE.md`「主な機能」に追記:
  `- **外部API（エージェント連携）:** `/api/v1/*` の JSON API で作物〜タスク・写真プールを参照・作成・部分更新（削除なし）。Bearer トークン（`.env` の `API_TOKEN`）必須、`server.py` が Web とは別ポート（`API_PORT`、既定5001）で起動。実装は `app/api/`（`Resource` 基底クラス＋リソースごとの定義）。詳細は `docs/api/README.md`、エージェント用スキルは `docs/api/hermes-skill/SKILL.md`。ネットワーク・画像まわりを変えるときは API 側（`app/api/images.py`）も確認する`
- ルート `CLAUDE.md` のプロジェクト構造に `app/api/` と `docs/api/` を追記、「ディレクトリ別ガイド」表の下に「API の規約は `docs/api/README.md`」を追記
- `CLAUDE.md` の `_CV_JOIN` の節に「`app/api/` は `app.models.planting._CV_JOIN` を import して使う（5箇所目のコピーは作らない）」を追記
- `app/routes/CLAUDE.md` の冒頭に「外部 JSON API は Blueprint ではなく `app/api/`（`create_api_app` 専用）にある」を追記
- `README.md` に外部 API の節（概要・起動方法・`docs/api/` へのリンク）
- `docs/dev-workflow-tips.md` に「API の手動確認」節: コピー DB に `DATABASE` を向けて `server.py` を起動、`API_PORT` を変えて既存サーバーと衝突させない、`gapi` 関数の使い方

- [ ] **Step 7: コミット**

```bash
git add docs/api CLAUDE.md app/routes/CLAUDE.md README.md docs/dev-workflow-tips.md
git commit -m "外部API: リファレンス・FW設定・移設手順・Hermes用スキルの下書きを追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: コピー DB での通し確認

**Files:**
- なし（確認のみ。問題があれば該当 Task のファイルを修正してコミット）

- [ ] **Step 1: コピー DB と別ポートでサーバーを起動**

```bash
netstat -ano | grep LISTEN | grep -E ':(5000|5071)\b'   # 空きを確認（5000 が使用中なら本番サーバーが動いているので止めてもらうか確認を待つ）
cp instance/garden.db "$SCRATCH/garden_copy.db"
DATABASE="$SCRATCH/garden_copy.db" API_TOKEN="<40文字のテスト用トークン>" API_PORT=5071 \
  WEB_BASE_URL=http://127.0.0.1:5000 uv run python server.py   # run_in_background
```

アップロード先は実際の `app/static/uploads/` になる点に注意。確認で作った画像は Step 4 で消す（作成したファイルのパスを記録しておく）。

- [ ] **Step 2: curl で一通り確認する**

`docs/api/curl-examples.md` を上から実行し（`GARDEN_API_URL=http://127.0.0.1:5071/api/v1`）、少なくとも次を確認する:
- `/health` 200、トークンなし 401、`http://127.0.0.1:5071/` が JSON 401、`http://127.0.0.1:5000/` が HTML
- `/meta` に実データの `crop_types` が並ぶ、`/lookup?q=<実在の作物名>` が期待どおり
- 実データの植え付けに栽培記録を写真付きで作成 → 返った `web_url` をブラウザで開いて画面に表示されること（Claude in Chrome で確認）
- 日記を relations 付きで作成 → 画面の詳細で関連カードが出ること
- 422 のメッセージが読みやすいこと

- [ ] **Step 3: 監査ログを確認**

サーバーの出力に `POST /api/v1/... -> 201 id=...` が出ており、トークンが出ていないこと。

- [ ] **Step 4: 後片付け**

サーバーを停止し、Step 2 で作成した画像ファイル（`app/static/uploads/` 配下、記録したパスのみ）を削除する。コピー DB はスクラッチ領域なので放置でよい。`git status` で uploads 以外に意図しない変更が無いことを確認。

- [ ] **Step 5: 全テスト**

Run: `uv run python -m pytest`
Expected: PASS（全件）
