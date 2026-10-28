"""ログインの判定と既定で拒否（before_request）のテスト"""
import fnmatch

import pytest
from flask import url_for

from app.auth import ANONYMOUS_POST_ENDPOINTS, OWNER_ONLY_GET_ENDPOINTS
from app.config import config, TestingConfig
from app.models.passkey import Passkey

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}

# 誰でも見られる閲覧用のエンドポイント（新しいルートの分類漏れを防ぐ）
VIEW_ENDPOINT_PATTERNS = [
    'index', '*.list', '*.detail', 'calendar.index', 'conversations.*',
    'locations.canvas_history', 'locations.canvas_history_range',
    'locations.get_canvas_data', 'photo_pool.index', 'plantings.index',
    'plantings.record_detail', 'settings.index', 'advices.list',
    'advices.detail', 'auth.login', 'auth.register_page',
]


def _url_for_rule(app, rule):
    """変換子に 1 を入れた URL を作る"""
    with app.test_request_context():
        return url_for(rule.endpoint, **{arg: 1 for arg in rule.arguments})


def _rules(app):
    return [r for r in app.url_map.iter_rules() if r.endpoint != 'static']


def _is_login_redirect(resp):
    return resp.status_code == 302 and '/auth/login' in resp.headers['Location']


def test_every_post_endpoint_rejects_anonymous(app, anon_client):
    checked = 0
    for rule in _rules(app):
        if not (rule.methods - SAFE_METHODS):
            continue
        if rule.endpoint in ANONYMOUS_POST_ENDPOINTS:
            continue
        resp = anon_client.post(_url_for_rule(app, rule))
        assert resp.status_code == 401 or _is_login_redirect(resp), \
            f'{rule.endpoint} ({rule.rule}) が拒否されない: {resp.status_code}'
        checked += 1
    assert checked > 0


@pytest.mark.parametrize('endpoint', sorted(OWNER_ONLY_GET_ENDPOINTS))
def test_owner_only_get_redirects_anonymous(app, anon_client, endpoint):
    rules = [r for r in app.url_map.iter_rules() if r.endpoint == endpoint]
    assert rules, f'{endpoint} が url_map に無い'
    url = _url_for_rule(app, rules[0])
    resp = anon_client.get(url)
    assert _is_login_redirect(resp), f'{endpoint}: {resp.status_code}'
    assert 'next=' in resp.headers['Location']


def test_get_endpoints_are_classified(app):
    unclassified = []
    for rule in _rules(app):
        if rule.methods - SAFE_METHODS:
            continue
        ep = rule.endpoint
        if ep in OWNER_ONLY_GET_ENDPOINTS:
            continue
        if any(fnmatch.fnmatchcase(ep, p) for p in VIEW_ENDPOINT_PATTERNS):
            continue
        unclassified.append(ep)
    assert not unclassified, f'分類されていない GET のエンドポイント: {unclassified}'


@pytest.mark.parametrize('path', ['/', '/crops/', '/settings/', '/calendar/'])
def test_view_pages_ok_for_anonymous(anon_client, path):
    assert anon_client.get(path).status_code == 200


def test_view_pages_ok_with_secure_cookie_over_http(tmp_path, monkeypatch):
    from app import create_app

    class SecureConfig(TestingConfig):
        DATABASE = str(tmp_path / 'secure.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        SESSION_COOKIE_SECURE = True

    monkeypatch.setitem(config, 'secure_pytest', SecureConfig)
    secure_app = create_app('secure_pytest')
    assert secure_app.config['SESSION_COOKIE_SECURE'] is True
    assert secure_app.test_client().get('/crops/').status_code == 200


def test_json_rejection_shape(anon_client):
    resp = anon_client.post('/settings/ai/notes-draft', json={})
    assert resp.status_code == 401
    assert resp.json['ok'] is False
    assert 'login_url' in resp.json
    assert '/auth/login' in resp.json['login_url']


def test_deleted_passkey_logs_out(app, client):
    assert client.get('/crops/new').status_code == 200
    with client.session_transaction() as sess:
        passkey_id = sess['owner_passkey_id']
    with app.app_context():
        Passkey.delete(passkey_id)
    resp = client.get('/crops/new')
    assert resp.status_code == 302
    assert '/auth/login' in resp.headers['Location']
    with client.session_transaction() as sess:
        assert 'owner_passkey_id' not in sess


def test_owner_can_open_edit_pages(client):
    assert client.get('/crops/new').status_code == 200


def test_api_app_unaffected(tmp_path, monkeypatch):
    from app import create_api_app
    from tests.api.helpers import TOKEN

    class ApiTestConfig(TestingConfig):
        DATABASE = str(tmp_path / 'api.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        API_TOKEN = TOKEN
        WEB_BASE_URL = 'http://garden.test:5000'

    monkeypatch.setitem(config, 'api_gate_pytest', ApiTestConfig)
    api_app = create_api_app('api_gate_pytest')
    api = api_app.test_client()
    resp = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科'},
                    headers={'Authorization': f'Bearer {TOKEN}'})
    assert resp.status_code == 201, resp.get_data(as_text=True)
