from app.models.conversation import Conversation
from app.models.crop import Crop
from app.routes.conversation_routes import strip_image_markers


def _session(hermes_id='20261025_165529_f52993ca', title='じゃがいもの相談', **kw):
    s = {'hermes_id': hermes_id, 'source': 'matrix', 'title': title,
         'started_at': '2026-10-25 16:55:29', 'ended_at': None,
         'last_activity_at': '2026-10-25 16:56:00',
         'end_reason': None, 'parent_hermes_id': None}
    s.update(kw)
    return s


def _msg(mid, role='user', content='こんにちは', ts='2026-10-25 16:55:30', **kw):
    m = {'hermes_message_id': mid, 'role': role, 'content': content, 'timestamp': ts}
    m.update(kw)
    return m


def _make(app, session=None, messages=()):
    with app.app_context():
        cid, _ = Conversation.upsert(session or _session())
        Conversation.upsert_messages(cid, list(messages))
        return cid


def test_strip_image_markers():
    text, names = strip_image_markers(
        '登録して  [Image attached at: /home/u/.hermes/cache/images/img_7e4f.jpg] [screenshot]')
    assert text.strip() == '登録して' and names == ['img_7e4f.jpg']


def test_list_and_keyword(app, client):
    _make(app, _session('a', 'じゃがいもの相談'))
    _make(app, _session('b', 'トマトの相談'))
    body = client.get('/conversations/').get_data(as_text=True)
    assert 'じゃがいもの相談' in body and 'トマトの相談' in body
    body = client.get('/conversations/?keyword=じゃがいも').get_data(as_text=True)
    assert 'じゃがいもの相談' in body and 'トマトの相談' not in body


def test_detail_hides_tools_and_markers(app, client):
    cid = _make(app, messages=[
        _msg(1, 'user', '登録して [Image attached at: /x/img_1.jpg]'),
        _msg(2, 'tool', 'SKILL_BODY', ts='2026-10-25 16:55:31'),
        _msg(3, 'assistant', '登録しました', ts='2026-10-25 16:55:32'),
    ])
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert 'SKILL_BODY' not in body and 'Image attached at' not in body
    assert '登録して' in body and '登録しました' in body


def test_detail_shows_saved_and_missing_photos(app, client):
    cid = _make(app, messages=[
        _msg(1, 'user', '[Image attached at: /x/img_1.jpg] [Image attached at: /x/img_2.jpg]'),
    ])
    with app.app_context():
        Conversation.add_image(cid, 'img_1.jpg', 'conversations/abc.jpg')
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert body.count('uploads/conversations/abc.jpg') == 1
    assert '写真あり（保存されていません）' in body


def test_detail_shows_links(app, client):
    cid = _make(app, messages=[_msg(1)])
    with app.app_context():
        crop_id = Crop.create({'name': 'ミニトマト', 'crop_type': '果菜類'})
        Conversation.replace_links(cid, [
            {'entity_type': 'crop', 'entity_id': crop_id, 'kind': 'created'}])
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert f'/crops/{crop_id}' in body and '作った' in body and 'ミニトマト' in body


def test_detail_shows_deleted_link(app, client):
    cid = _make(app, messages=[_msg(1)])
    with app.app_context():
        Conversation.replace_links(cid, [
            {'entity_type': 'planting', 'entity_id': 999, 'kind': 'viewed'}])
    r = client.get(f'/conversations/{cid}')
    assert r.status_code == 200
    assert '削除済み' in r.get_data(as_text=True)


def test_user_bubble_has_no_extra_whitespace(app, client):
    cid = _make(app, messages=[_msg(1, 'user', 'じゃがいも')])
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert 'chat-bubble">じゃがいも</div>' in body


def test_detail_shows_planting_link(app, client):
    from app.models.location import Location
    from app.models.planting import Planting
    cid = _make(app, messages=[_msg(1)])
    with app.app_context():
        crop_id = Crop.create({'name': 'ミニトマト', 'crop_type': '果菜類'})
        loc_id = Location.create({'name': '南の畑', 'location_type': '畑'})
        pid = Planting.plant({'location_id': loc_id, 'crop_id': crop_id,
                              'planted_date': '2026-05-01'})
        Conversation.replace_links(cid, [
            {'entity_type': 'planting', 'entity_id': pid, 'kind': 'created'}])
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert f'href="/plantings/{pid}"' in body
    assert 'ミニトマト 南の畑' in body and '削除済み' not in body


def test_detail_photo_pool_link(app, client):
    from app.models.photo_pool import PhotoPool
    cid = _make(app, messages=[_msg(1)])
    with app.app_context():
        pid = PhotoPool.create('photo_pool/x.jpg')
        Conversation.replace_links(cid, [
            {'entity_type': 'photo_pool', 'entity_id': pid, 'kind': 'viewed'}])
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert f'写真プールの写真 #{pid}' in body and 'href="/photo_pool/"' in body


def test_detail_404_redirects(client):
    r = client.get('/conversations/999')
    assert r.status_code == 302 and r.headers['Location'].endswith('/conversations/')


def test_nav_has_menu(client):
    assert '/conversations/' in client.get('/').get_data(as_text=True)
