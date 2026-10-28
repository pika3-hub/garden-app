import sqlite3

import pytest

from app.models.passkey import Passkey


def test_create_and_get(app):
    with app.app_context():
        pid = Passkey.create('cid', 'pk', 0, 'PC')
        assert Passkey.get_by_id(pid)['name'] == 'PC'
        assert Passkey.get_by_credential_id('cid')['id'] == pid
        assert Passkey.get_by_id(9999) is None
        assert Passkey.get_by_credential_id('none') is None


def test_credential_id_unique(app):
    with app.app_context():
        Passkey.create('cid', 'pk', 0, 'PC')
        with pytest.raises(sqlite3.IntegrityError):
            Passkey.create('cid', 'pk2', 0, 'Phone')


def test_record_use_updates_count_and_time(app):
    with app.app_context():
        pid = Passkey.create('cid', 'pk', 0, 'PC')
        assert Passkey.get_by_id(pid)['last_used_at'] is None
        Passkey.record_use(pid, 5)
        row = Passkey.get_by_id(pid)
        assert row['sign_count'] == 5
        assert row['last_used_at']


def test_rename_and_delete(app):
    with app.app_context():
        pid = Passkey.create('cid', 'pk', 0, 'PC')
        Passkey.rename(pid, 'スマホ')
        assert Passkey.get_by_id(pid)['name'] == 'スマホ'
        Passkey.delete(pid)
        assert Passkey.get_by_id(pid) is None


def test_count_and_get_all_order(app):
    with app.app_context():
        assert Passkey.count() == 0
        a = Passkey.create('a', 'pk', 0, 'A')
        b = Passkey.create('b', 'pk', 0, 'B')
        assert Passkey.count() == 2
        assert [r['id'] for r in Passkey.get_all()] == [a, b]


def test_registration_token_single_use(app):
    with app.app_context():
        t = Passkey.issue_registration_token()
        assert Passkey.check_registration_token(t) is True
        assert Passkey.consume_registration_token(t) is True
        assert Passkey.consume_registration_token(t) is False


def test_registration_token_wrong_value(app):
    with app.app_context():
        assert Passkey.consume_registration_token('x') is False
        Passkey.issue_registration_token()
        assert Passkey.consume_registration_token('x') is False


def test_registration_token_expired(app):
    with app.app_context():
        t = Passkey.issue_registration_token(ttl_minutes=-1)
        assert Passkey.check_registration_token(t) is False


def test_registration_token_reissue_invalidates_old(app):
    with app.app_context():
        t1 = Passkey.issue_registration_token()
        t2 = Passkey.issue_registration_token()
        assert Passkey.check_registration_token(t1) is False
        assert Passkey.check_registration_token(t2) is True
