"""パスキーのログイン・登録・管理と非常口のテスト（py_webauthn の検証は偽物に差し替える）"""
import inspect
import re
from types import SimpleNamespace

import pytest
import webauthn

from app.config import config, TestingConfig
from app.models.passkey import Passkey

CRED_ID = 'AQIDBA'  # base64url（b'\x01\x02\x03\x04'）
PUBLIC_KEY = 'BQYHCA'  # base64url（b'\x05\x06\x07\x08'）


def _fake_auth(new_sign_count=3, error=None):
    def fake(*, credential, expected_challenge, expected_rp_id, expected_origin,
             credential_public_key, credential_current_sign_count,
             require_user_verification=False):
        assert require_user_verification is True
        assert isinstance(expected_challenge, bytes)
        if error:
            raise error
        return SimpleNamespace(new_sign_count=new_sign_count)
    return fake


def _fake_reg(credential_id=b'\x09\x0a\x0b\x0c', public_key=b'\x0d\x0e', sign_count=0):
    def fake(*, credential, expected_challenge, expected_rp_id, expected_origin,
             require_user_presence=True, require_user_verification=False,
             supported_pub_key_algs=None, pem_root_certs_bytes_by_fmt=None):
        assert require_user_verification is True
        assert isinstance(expected_challenge, bytes)
        return SimpleNamespace(credential_id=credential_id,
                               credential_public_key=public_key, sign_count=sign_count)
    return fake


def test_fakes_match_real_signatures():
    for fake, real in ((_fake_auth(), webauthn.verify_authentication_response),
                       (_fake_reg(), webauthn.verify_registration_response)):
        assert list(inspect.signature(fake).parameters) == \
            list(inspect.signature(real).parameters)


@pytest.fixture
def fake_auth(monkeypatch):
    def install(**kwargs):
        monkeypatch.setattr('app.routes.auth_routes.verify_authentication_response',
                            _fake_auth(**kwargs))
    return install


@pytest.fixture
def fake_reg(monkeypatch):
    def install(**kwargs):
        monkeypatch.setattr('app.routes.auth_routes.verify_registration_response',
                            _fake_reg(**kwargs))
    return install


@pytest.fixture
def registered(app):
    with app.app_context():
        return Passkey.create(CRED_ID, PUBLIC_KEY, 0, 'PC')


def _csrf(c, path='/auth/login'):
    c.get(path)
    with c.session_transaction() as s:
        return s['csrf_token']


def _post_json(c, url, token, body=None):
    return c.post(url, json=body or {}, headers={'X-CSRFToken': token})


def _auth_credential(cred_id=CRED_ID):
    return {'id': cred_id, 'rawId': cred_id, 'type': 'public-key',
            'response': {'clientDataJSON': 'e30', 'authenticatorData': 'AA',
                         'signature': 'AA', 'userHandle': None},
            'clientExtensionResults': {}}


def _reg_credential():
    return {'id': 'CQoLDA', 'rawId': 'CQoLDA', 'type': 'public-key',
            'response': {'clientDataJSON': 'e30', 'attestationObject': 'AA',
                         'transports': ['internal']},
            'clientExtensionResults': {}}


def _logged_in(c):
    return c.get('/crops/new').status_code == 200


def _login(c, token, cred_id=CRED_ID, next_url=None):
    opts = _post_json(c, '/auth/login/options', token)
    assert opts.status_code == 200
    body = {'credential': _auth_credential(cred_id)}
    if next_url is not None:
        body['next'] = next_url
    return _post_json(c, '/auth/login/verify', token, body)


def test_login_flow(app, anon_client, registered, fake_auth):
    fake_auth(new_sign_count=3)
    token = _csrf(anon_client)
    opts = _post_json(anon_client, '/auth/login/options', token)
    assert opts.status_code == 200
    assert opts.json['challenge']
    assert opts.json['userVerification'] == 'required'
    assert not opts.json.get('allowCredentials')
    resp = _post_json(anon_client, '/auth/login/verify', token,
                      {'credential': _auth_credential(), 'next': '/crops/'})
    assert resp.status_code == 200
    assert resp.json == {'ok': True, 'redirect': '/crops/'}
    assert _logged_in(anon_client)
    with app.app_context():
        pk = Passkey.get_by_id(registered)
        assert pk['sign_count'] == 3
        assert pk['last_used_at']


def test_login_redirect_rejects_external_next(anon_client, registered, fake_auth):
    fake_auth()
    token = _csrf(anon_client)
    resp = _login(anon_client, token, next_url='//evil.example/')
    assert resp.status_code == 200
    assert resp.json['redirect'] == '/'


CONTROL_CHAR_NEXTS = ['/\t/evil.example', '/\n/evil.example', '/\r/evil.example']


@pytest.mark.parametrize('next_url', CONTROL_CHAR_NEXTS)
def test_login_redirect_rejects_control_chars(anon_client, registered, fake_auth, next_url):
    fake_auth()
    token = _csrf(anon_client)
    resp = _login(anon_client, token, next_url=next_url)
    assert resp.status_code == 200
    assert resp.json['redirect'] == '/'


@pytest.mark.parametrize('next_url', CONTROL_CHAR_NEXTS)
def test_login_page_logged_in_rejects_control_chars(client, next_url):
    resp = client.get('/auth/login', query_string={'next': next_url})
    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/', 'http://localhost/')


def test_login_unknown_credential(anon_client, registered, fake_auth):
    fake_auth()
    token = _csrf(anon_client)
    resp = _login(anon_client, token, cred_id='ZZZZ')
    assert resp.status_code == 400
    assert resp.json['ok'] is False
    assert not _logged_in(anon_client)


def test_login_verify_failure(anon_client, registered, fake_auth):
    fake_auth(error=ValueError('bad signature'))
    token = _csrf(anon_client)
    resp = _login(anon_client, token)
    assert resp.status_code == 400
    assert resp.json['ok'] is False
    assert not _logged_in(anon_client)


def test_login_challenge_single_use(anon_client, registered, fake_auth):
    fake_auth(error=ValueError('bad signature'))
    token = _csrf(anon_client)
    assert _login(anon_client, token).status_code == 400
    fake_auth()
    # options を取り直さずに同じチャレンジでもう一度
    resp = _post_json(anon_client, '/auth/login/verify', token,
                      {'credential': _auth_credential()})
    assert resp.status_code == 400
    assert not _logged_in(anon_client)


def test_login_verify_without_options(anon_client, registered, fake_auth):
    fake_auth()
    token = _csrf(anon_client)
    resp = _post_json(anon_client, '/auth/login/verify', token,
                      {'credential': _auth_credential()})
    assert resp.status_code == 400


def test_register_requires_login_or_token(anon_client, fake_reg):
    fake_reg()
    token = _csrf(anon_client)
    resp = _post_json(anon_client, '/auth/passkeys/register/options', token)
    assert resp.status_code in (401, 302)
    resp = _post_json(anon_client, '/auth/passkeys/register/verify', token,
                      {'credential': _reg_credential(), 'name': 'x'})
    assert resp.status_code in (401, 302)


def test_emergency_link_registers_and_logs_in(app, anon_client, fake_reg):
    fake_reg(credential_id=b'\x09\x0a\x0b\x0c', public_key=b'\x0d\x0e', sign_count=0)
    with app.app_context():
        t = Passkey.issue_registration_token()
    page = anon_client.get(f'/auth/register/{t}')
    assert page.status_code == 200
    assert 'data-passkey-action="register"' in page.get_data(as_text=True)
    with anon_client.session_transaction() as s:
        token = s['csrf_token']
    opts = _post_json(anon_client, '/auth/passkeys/register/options', token)
    assert opts.status_code == 200
    assert opts.json['authenticatorSelection']['residentKey'] == 'required'
    assert opts.json['authenticatorSelection']['userVerification'] == 'required'
    assert opts.json['attestation'] == 'none'
    assert opts.json['rp']['name'] == '家庭菜園'
    resp = _post_json(anon_client, '/auth/passkeys/register/verify', token,
                      {'credential': _reg_credential(), 'name': 'iPhone'})
    assert resp.status_code == 200
    assert resp.json['ok'] is True
    with app.app_context():
        assert Passkey.count() == 1
        pk = Passkey.get_all()[0]
        assert pk['credential_id'] == 'CQoLDA'
        assert pk['public_key'] == 'DQ4'
        assert pk['name'] == 'iPhone'
        assert Passkey.check_registration_token(t) is False
    assert _logged_in(anon_client)
    assert anon_client.get(f'/auth/register/{t}').status_code != 200


def test_emergency_link_expired(app, anon_client):
    with app.app_context():
        t = Passkey.issue_registration_token(ttl_minutes=-1)
    resp = anon_client.get(f'/auth/register/{t}')
    assert resp.status_code != 200
    assert 'data-passkey-action="register"' not in resp.get_data(as_text=True)


def test_emergency_link_invalid_token_cannot_register(app, anon_client, fake_reg):
    fake_reg()
    with app.app_context():
        Passkey.issue_registration_token()
    anon_client.get('/auth/register/wrong-token')
    with anon_client.session_transaction() as s:
        token = s['csrf_token']
    resp = _post_json(anon_client, '/auth/passkeys/register/options', token)
    assert resp.status_code in (401, 302)


def test_owner_adds_passkey(app, client, fake_reg):
    fake_reg(credential_id=b'\x11\x12\x13', public_key=b'\x14')
    with app.app_context():
        before = Passkey.count()
    opts = client.post('/auth/passkeys/register/options', json={})
    assert opts.status_code == 200
    resp = client.post('/auth/passkeys/register/verify',
                       json={'credential': _reg_credential(), 'name': '  iPad  '})
    assert resp.status_code == 200
    assert resp.json['ok'] is True
    with app.app_context():
        assert Passkey.count() == before + 1
        assert Passkey.get_all()[-1]['name'] == 'iPad'
    assert _logged_in(client)


def test_owner_adds_passkey_default_name(app, client, fake_reg):
    fake_reg(credential_id=b'\x21\x22\x23')
    client.post('/auth/passkeys/register/options', json={})
    resp = client.post('/auth/passkeys/register/verify',
                       json={'credential': _reg_credential(), 'name': ''})
    assert resp.status_code == 200
    with app.app_context():
        assert Passkey.get_all()[-1]['name'] == 'パスキー 2'


def test_register_options_excludes_existing(app, client, registered):
    opts = client.post('/auth/passkeys/register/options', json={})
    assert opts.status_code == 200
    ids = [c['id'] for c in opts.json.get('excludeCredentials', [])]
    assert CRED_ID in ids


def test_rename_and_delete_passkey(app, client, registered):
    page = client.get('/settings/').get_data(as_text=True)
    assert 'PC' in page
    resp = client.post(f'/auth/passkeys/{registered}/rename', data={'name': 'デスクトップ'})
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/settings/')
    with app.app_context():
        assert Passkey.get_by_id(registered)['name'] == 'デスクトップ'
    resp = client.post(f'/auth/passkeys/{registered}/delete')
    assert resp.status_code == 302
    with app.app_context():
        assert Passkey.get_by_id(registered) is None


def test_rename_empty_name_keeps_old(app, client, registered):
    client.post(f'/auth/passkeys/{registered}/rename', data={'name': '  '})
    with app.app_context():
        assert Passkey.get_by_id(registered)['name'] == 'PC'


def test_deleting_own_passkey_logs_out(client):
    with client.session_transaction() as s:
        own = s['owner_passkey_id']
    client.post(f'/auth/passkeys/{own}/delete')
    assert not _logged_in(client)


def test_settings_anonymous_sees_count_only(anon_client, registered):
    html = anon_client.get('/settings/').get_data(as_text=True)
    assert '1件' in html
    assert '/auth/passkeys/' not in html
    assert 'data-passkey-action' not in html


def test_logout(client):
    assert _logged_in(client)
    resp = client.post('/auth/logout')
    assert resp.status_code == 302
    assert client.get('/crops/new').status_code == 302


def test_nav_login_logout(client, anon_client):
    anon_html = anon_client.get('/').get_data(as_text=True)
    assert '/auth/login' in anon_html
    assert 'action="/auth/logout"' not in anon_html
    owner_html = client.get('/').get_data(as_text=True)
    assert 'action="/auth/logout"' in owner_html


def test_login_page_logged_in_redirects(client):
    resp = client.get('/auth/login?next=/crops/')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/crops/')


def test_login_page_on_owner_origin_shows_button(anon_client):
    html = anon_client.get('/auth/login', base_url='http://localhost:5000').get_data(as_text=True)
    assert 'data-passkey-action="login"' in html


def test_login_page_on_other_origin_shows_link(tmp_path, monkeypatch):
    from app import create_app

    class OtherConfig(TestingConfig):
        DATABASE = str(tmp_path / 'other.db')
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        OWNER_BASE_URL = 'https://example.local'

    monkeypatch.setitem(config, 'other_pytest', OtherConfig)
    other = create_app('other_pytest')
    html = other.test_client().get('/auth/login').get_data(as_text=True)
    assert 'https://example.local/auth/login' in html
    assert 'data-passkey-action="login"' not in html


def test_cli_register_link(app):
    result = app.test_cli_runner().invoke(
        args=['passkey-register-link', '--base-url', 'https://x.local'])
    assert result.exit_code == 0, result.output
    m = re.search(r'https://x\.local/auth/register/(\S+)', result.output)
    assert m
    assert '15分以内に1回だけ使えます' in result.output
    with app.app_context():
        assert Passkey.check_registration_token(m.group(1)) is True
