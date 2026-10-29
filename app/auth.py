"""持ち主のログイン（パスキー）の判定、既定で拒否、CSRF 対策

- 見るだけ（GET 等）は誰でもできる。ただし編集画面（OWNER_ONLY_GET_ENDPOINTS）はログインが要る
- GET 等以外（POST など）は、ログイン画面の処理（ANONYMOUS_POST_ENDPOINTS）を除き、ログインが要る
- GET 等以外はすべて CSRF トークンを照合する（ログイン画面の処理も含む）
- 新しい POST のルートは何もしなくても拒否される（既定で拒否）。新しい GET のルートは
  tests/test_auth_gate.py の分類のテストで、編集画面か閲覧用かを決めさせる
"""
import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from flask import g, jsonify, redirect, request, session

from app.models.passkey import Passkey

SESSION_PASSKEY_KEY = 'owner_passkey_id'
SESSION_CSRF_KEY = 'csrf_token'

# ログイン画面の URL（auth.login のルート。Blueprint は Task 3 で足す）
LOGIN_PATH = '/auth/login'

LOGIN_LIFETIME = timedelta(days=180)

SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

# ログインしていないと開けない GET の画面（新規作成・編集・見取り図の配置など）
OWNER_ONLY_GET_ENDPOINTS = frozenset({
    'crops.new', 'crops.edit',
    'varieties.new', 'varieties.edit',
    'locations.new', 'locations.edit', 'locations.canvas',
    'plantings.plant_new', 'plantings.new', 'plantings.bulk_new', 'plantings.edit',
    'plantings.planting_edit', 'plantings.planting_edit_ended', 'plantings.place',
    'harvests.new', 'harvests.edit', 'harvests.bulk_new',
    'cooking.new', 'cooking.edit',
    'diary.new', 'diary.edit',
    'tasks.new', 'tasks.edit',
    'advices.edit',
    'photo_pool.use', 'photo_sort.index',
    'hermes_ask.history', 'hermes_ask.events', 'hermes_ask.run_status',
})

# ログインしていなくても受ける POST（ログイン・パスキー登録の処理。CSRF の照合は受ける）
ANONYMOUS_POST_ENDPOINTS = frozenset({
    'auth.login_options', 'auth.login_verify',
    'auth.register_options', 'auth.register_verify',
})

LOGIN_REQUIRED_MESSAGE = 'ログインが必要です'
CSRF_FAILED_MESSAGE = '画面を開き直してから、もう一度操作してください'

_NOT_LOADED = object()


def current_passkey():
    """ログインに使ったパスキーの行。DB から消えていればセッションから外して None"""
    cached = g.get('_owner_passkey', _NOT_LOADED)
    if cached is not _NOT_LOADED:
        return cached
    passkey = None
    passkey_id = session.get(SESSION_PASSKEY_KEY)
    if passkey_id is not None:
        if isinstance(passkey_id, int):
            passkey = Passkey.get_by_id(passkey_id)
        if passkey is None:
            session.pop(SESSION_PASSKEY_KEY, None)
    g._owner_passkey = passkey
    return passkey


def is_owner():
    return current_passkey() is not None


def login_owner(passkey_id):
    """ログイン状態にする（セッション固定攻撃を防ぐため、前のセッションの中身は捨てる）"""
    session.clear()
    session[SESSION_PASSKEY_KEY] = passkey_id
    session[SESSION_CSRF_KEY] = secrets.token_urlsafe(32)
    session.permanent = True
    g.pop('_owner_passkey', None)


def logout_owner():
    session.clear()
    g.pop('_owner_passkey', None)


def csrf_token():
    token = session.get(SESSION_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_CSRF_KEY] = token
    return token


def _wants_json():
    if request.is_json:
        return True
    accept = request.accept_mimetypes
    best = accept.best_match(['text/html', 'application/json'])
    return best == 'application/json' and accept[best] > accept['text/html']


def _login_url(with_next):
    if with_next:
        return f'{LOGIN_PATH}?{urlencode({"next": request.full_path.rstrip("?")})}'
    return LOGIN_PATH


def _reject_anonymous():
    if _wants_json():
        return jsonify({'ok': False, 'error': LOGIN_REQUIRED_MESSAGE,
                        'login_url': _login_url(False)}), 401
    return redirect(_login_url(request.method in SAFE_METHODS))


def _csrf_ok():
    expected = session.get(SESSION_CSRF_KEY)
    sent = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
    if not expected or not sent:
        return False
    return hmac.compare_digest(str(expected), str(sent))


def _reject_csrf():
    if _wants_json():
        return jsonify({'ok': False, 'error': CSRF_FAILED_MESSAGE}), 400
    return CSRF_FAILED_MESSAGE, 400, {'Content-Type': 'text/plain; charset=utf-8'}


def _gate():
    endpoint = request.endpoint
    if endpoint is None or endpoint == 'static':
        return None
    safe = request.method in SAFE_METHODS
    if safe and endpoint not in OWNER_ONLY_GET_ENDPOINTS:
        return None
    if not is_owner() and endpoint not in ANONYMOUS_POST_ENDPOINTS:
        return _reject_anonymous()
    if not safe and not _csrf_ok():
        return _reject_csrf()
    return None


def init_auth(app):
    app.config['PERMANENT_SESSION_LIFETIME'] = LOGIN_LIFETIME
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.before_request(_gate)
    app.jinja_env.globals['is_owner'] = is_owner
    app.jinja_env.globals['csrf_token'] = csrf_token
    app.jinja_env.globals['owner_base_url'] = app.config['OWNER_BASE_URL']
