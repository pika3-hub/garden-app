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


DEV_DEFAULT_KEY = 'dev-secret-key-change-in-production'


def _non_testing_config(tmp_path, secret_key):
    class NonTestingConfig(TestingConfig):
        TESTING = False
        DATABASE = str(tmp_path / 'test.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        SECRET_KEY = secret_key
    return NonTestingConfig


def test_public_dev_secret_key_is_replaced(tmp_path, monkeypatch, caplog):
    """公開されている開発用の既定値のままだと、ログインのセッションを偽造できるので使わない"""
    monkeypatch.setitem(config, 'devkey', _non_testing_config(tmp_path, DEV_DEFAULT_KEY))
    app = create_app('devkey')

    assert app.config['SECRET_KEY']
    assert app.config['SECRET_KEY'] != DEV_DEFAULT_KEY
    assert 'ログインが外れます' in caplog.text


def test_explicit_secret_key_is_kept(tmp_path, monkeypatch):
    """.env で設定した SECRET_KEY はそのまま使う"""
    key = 'k' * 64
    monkeypatch.setitem(config, 'envkey', _non_testing_config(tmp_path, key))
    app = create_app('envkey')

    assert app.config['SECRET_KEY'] == key
