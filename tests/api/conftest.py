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
