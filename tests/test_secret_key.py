from flask import flash

from app import create_app
from app.config import config, TestingConfig


def test_flash_works_without_secret_key(tmp_path, monkeypatch):
    """本番設定で SECRET_KEY 未設定でも、保存後の flash() で 500 にならない"""
    class NoSecretConfig(TestingConfig):
        DATABASE = str(tmp_path / 'test.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        SECRET_KEY = None

    monkeypatch.setitem(config, 'nosecret', NoSecretConfig)
    app = create_app('nosecret')

    assert app.config['SECRET_KEY']
    with app.test_request_context('/'):
        flash('保存しました')
