"""CSRF 対策のテスト"""
from flask.testing import FlaskClient

from app.models.passkey import Passkey


def _logged_in_plain_client(app, token='right-token'):
    """自動で X-CSRFToken を付けない素のクライアントでログイン状態にする"""
    with app.app_context():
        passkey_id = Passkey.create('csrf-cred', 'csrf-pk', 0, 'CSRF テスト')
    c = FlaskClient(app, app.response_class, use_cookies=True)
    with c.session_transaction() as sess:
        sess['owner_passkey_id'] = passkey_id
        sess['csrf_token'] = token
    return c


def test_post_without_token_rejected_for_owner(app):
    c = _logged_in_plain_client(app)
    resp = c.post('/settings/', data={'region': '関東'})
    assert resp.status_code == 400


def test_post_with_form_token_ok(app):
    c = _logged_in_plain_client(app)
    resp = c.post('/settings/', data={'region': '関東', 'csrf_token': 'right-token'})
    assert resp.status_code == 302


def test_post_with_wrong_header_rejected(app):
    c = _logged_in_plain_client(app)
    resp = c.post('/settings/', data={'region': '関東'},
                  headers={'X-CSRFToken': 'wrong-token'})
    assert resp.status_code == 400


def test_json_csrf_rejection_shape(app):
    c = _logged_in_plain_client(app)
    resp = c.post('/settings/ai/notes-draft', json={},
                  headers={'X-CSRFToken': 'wrong-token'})
    assert resp.status_code == 400
    assert resp.json['ok'] is False
    assert resp.json['error'] == '画面を開き直してから、もう一度操作してください'


def test_base_template_has_meta_and_script(client):
    html = client.get('/').get_data(as_text=True)
    assert 'name="csrf-token"' in html
    assert 'js/csrf.js' in html
    assert html.index('js/csrf.js') < html.index('js/main.js')
