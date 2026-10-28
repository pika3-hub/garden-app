import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

from app import create_app
from app.config import config, TestingConfig
from app.models.passkey import Passkey

TEST_CSRF_TOKEN = 'test-csrf-token'


class CsrfFlaskClient(FlaskClient):
    """GET 等以外の要求に X-CSRFToken を自動で付けるテスト用クライアント
    （既存のテストを書き換えずに、ログイン済み＋CSRF 対策ありのアプリで通すため）"""

    def open(self, *args, **kwargs):
        method = (kwargs.get('method') or 'GET').upper()
        if method not in ('GET', 'HEAD', 'OPTIONS'):
            headers = Headers(kwargs.get('headers') or {})
            if 'X-CSRFToken' not in headers:
                headers['X-CSRFToken'] = TEST_CSRF_TOKEN
            kwargs['headers'] = headers
        return super().open(*args, **kwargs)


@pytest.fixture
def app(tmp_path, monkeypatch):
    """tmp_path 上の使い捨て DB でアプリを生成する（instance/garden.db には触れない）"""
    class PytestConfig(TestingConfig):
        DATABASE = str(tmp_path / 'test.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')

    assert 'garden.db' not in PytestConfig.DATABASE
    monkeypatch.setitem(config, 'pytest', PytestConfig)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_MODEL', raising=False)
    return create_app('pytest')


@pytest.fixture
def client(app):
    """ログイン済みのクライアント（POST などには CSRF トークンを自動で付ける）"""
    with app.app_context():
        passkey_id = Passkey.create('test-cred', 'test-pk', 0, 'テスト')
    app.test_client_class = CsrfFlaskClient
    try:
        c = app.test_client()
    finally:
        app.test_client_class = None
    with c.session_transaction() as sess:
        sess['owner_passkey_id'] = passkey_id
        sess['csrf_token'] = TEST_CSRF_TOKEN
    return c


@pytest.fixture
def anon_client(app):
    """ログインしていない素のクライアント"""
    return app.test_client()
