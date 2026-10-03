import pytest

from app import create_app
from app.config import config, TestingConfig


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
    return app.test_client()
