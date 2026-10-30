"""Hermes とのチャット画面（/hermes/chat）のテスト。Hermes は呼ばず _open を差し替える"""
import os

from app.database import get_db
from app.models.hermes_chat import HermesChat
from tests.hermes_fakes import crop_id, fake_open, planting_id, variety_id  # noqa: F401


def _conv_with_image(app, session_id, title):
    """会話の履歴の行と写真ファイル（tmp の UPLOAD_FOLDER）を作る。写真の絶対パスを返す"""
    with app.app_context():
        db = get_db()
        cur = db.execute(
            'INSERT INTO conversations (hermes_id, source, title) '
            "VALUES (?, 'api_server', ?)", (session_id, title))
        db.execute("INSERT INTO conversation_images (conversation_id, file_name, image_path) "
                   "VALUES (?, 'a.jpg', 'conversations/a.jpg')", (cur.lastrowid,))
        db.commit()
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'conversations')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'a.jpg')
    with open(path, 'wb') as f:
        f.write(b'jpg')
    return path


def test_owner_sees_chat_page_with_tabs(client, fake_open):
    html = client.get('/hermes/chat/').get_data(as_text=True)
    assert 'data-runs-url="/hermes/ask/chats/runs"' in html and '>チャット<' in html
    assert 'data-history-url' not in html


def test_anonymous_redirected_to_login(anon_client, fake_open):
    r = anon_client.get('/hermes/chat/')
    assert r.status_code == 302 and '/auth/login' in r.headers['Location']


def test_anonymous_show_redirected_to_login(anon_client, app, fake_open):
    with app.app_context():
        chat = HermesChat.create_free('オクラ')
    r = anon_client.get(f"/hermes/chat/{chat['id']}")
    assert r.status_code == 302 and '/auth/login' in r.headers['Location']


def test_nav_hermes_link_depends_on_login(client, anon_client, fake_open):
    assert 'href="/hermes/chat/"' in client.get('/').get_data(as_text=True)
    anon_home = anon_client.get('/').get_data(as_text=True)
    assert 'href="/hermes/chat/"' not in anon_home and 'href="/conversations/"' in anon_home
    tabs = anon_client.get('/conversations/').get_data(as_text=True)
    assert '>チャット<' not in tabs
    assert '>チャット<' in client.get('/conversations/').get_data(as_text=True)


def test_nav_without_key_goes_to_conversations(client, app):
    app.config['HERMES_API_KEY'] = ''
    html = client.get('/').get_data(as_text=True)
    assert 'href="/hermes/chat/"' not in html and 'href="/conversations/"' in html


def test_page_without_key_shows_message_and_no_input(client, app):
    app.config['HERMES_API_KEY'] = ''
    r = client.get('/hermes/chat/')
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'Hermes への接続が設定されていません' in html and 'data-hermes-ask' not in html


def test_list_shows_free_and_panel_chats(client, app, fake_open, planting_id):
    with app.app_context():
        HermesChat.create_free('オクラの育て方')
        HermesChat.get_or_create_active('planting', planting_id)
    html = client.get('/hermes/chat/').get_data(as_text=True)
    assert 'オクラの育て方' in html and '植え付け:' in html


def test_list_marks_deleted_target(client, app, fake_open):
    with app.app_context():
        HermesChat.get_or_create_active('planting', 9999)
    assert '（削除済み）' in client.get('/hermes/chat/').get_data(as_text=True)


def test_show_has_history_and_runs_urls(client, app, fake_open):
    with app.app_context():
        chat = HermesChat.create_free('オクラの育て方')
    cid = chat['id']
    html = client.get(f'/hermes/chat/{cid}').get_data(as_text=True)
    assert f'data-history-url="/hermes/ask/chats/{cid}/history"' in html
    assert f'data-runs-url="/hermes/ask/chats/{cid}/runs"' in html
    assert 'data-autoload' in html
    assert f'action="/hermes/chat/{cid}/rename"' in html
    assert f'action="/hermes/chat/{cid}/delete"' in html


def test_show_unknown_is_404(client, fake_open):
    assert client.get('/hermes/chat/999').status_code == 404


def test_rename(client, app, fake_open):
    with app.app_context():
        chat = HermesChat.create_free('元の題名')
    cid = chat['id']
    r = client.post(f'/hermes/chat/{cid}/rename', data={'title': ' オクラ '})
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/hermes/chat/{cid}')
    with app.app_context():
        assert HermesChat.get_by_id(cid)['custom_title'] == 'オクラ'
    r = client.post(f'/hermes/chat/{cid}/rename', data={'title': '  '})
    assert r.status_code == 302
    with app.app_context():
        assert HermesChat.get_by_id(cid)['custom_title'] == 'オクラ'
    client.post(f'/hermes/chat/{cid}/rename', data={'title': 'あ' * 201})
    with app.app_context():
        assert HermesChat.get_by_id(cid)['custom_title'] == 'オクラ'


def test_rename_unknown_is_404(client, fake_open):
    assert client.post('/hermes/chat/999/rename', data={'title': 'x'}).status_code == 404


def test_delete_removes_from_chat_and_conversations(client, app, fake_open):
    with app.app_context():
        chat = HermesChat.create_free('消す会話の題名')
    photo = _conv_with_image(app, chat['session_id'], '消す会話の題名')
    assert '消す会話の題名' in client.get('/conversations/').get_data(as_text=True)

    r = client.post(f"/hermes/chat/{chat['id']}/delete")
    assert r.status_code == 302 and r.headers['Location'].endswith('/hermes/chat/')
    assert '消す会話の題名' not in client.get('/conversations/').get_data(as_text=True)
    assert '消す会話の題名' not in client.get('/hermes/chat/').get_data(as_text=True)
    assert not os.path.exists(photo)
    with app.app_context():
        assert HermesChat.get_by_id(chat['id']) is None


def test_delete_unknown_is_404_and_deletes_nothing(client, app, fake_open):
    with app.app_context():
        keep = HermesChat.create_free('残す')
    assert client.post('/hermes/chat/999/delete').status_code == 404
    with app.app_context():
        assert HermesChat.get_by_id(keep['id']) is not None
    assert fake_open.calls == []


def test_key_not_in_chat_page(client, app, fake_open):
    assert 'test-hermes-key' not in client.get('/hermes/chat/').get_data(as_text=True)
    with app.app_context():
        chat = HermesChat.create_free('オクラ')
    assert 'test-hermes-key' not in client.get(f"/hermes/chat/{chat['id']}").get_data(as_text=True)


def test_title_is_escaped(client, app, fake_open):
    with app.app_context():
        HermesChat.create_free('<script>alert(1)</script>')
    html = client.get('/hermes/chat/').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html


def test_delete_succeeds_even_if_photo_removal_fails(client, app, fake_open, monkeypatch):
    with app.app_context():
        chat = HermesChat.create_free('消す')
    _conv_with_image(app, chat['session_id'], '消す')

    def broken(path):
        raise PermissionError('使用中')
    monkeypatch.setattr('app.routes.hermes_chat_routes.delete_image', broken)
    r = client.post(f"/hermes/chat/{chat['id']}/delete")
    assert r.status_code == 302 and r.headers['Location'].endswith('/hermes/chat/')
    assert '会話を削除しました' in client.get('/hermes/chat/').get_data(as_text=True)
    with app.app_context():
        assert HermesChat.get_by_id(chat['id']) is None
