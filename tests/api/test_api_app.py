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
