"""tools/matrix_helper.py のテスト。HTTP は偽物に差し替え、実サーバーには接続しない。"""
import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / 'tools' / 'matrix_helper.py'
_spec = importlib.util.spec_from_file_location('matrix_helper', _PATH)
mh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mh)


class FakeTransport:
    """(method, path) ごとに用意した応答を順に返し、受けた呼び出しを記録する"""

    def __init__(self, responses):
        self.responses = {k: list(v) for k, v in responses.items()}
        self.calls = []

    def __call__(self, method, url, body=None, headers=None):
        path = url.split('?', 1)[0].split('127.0.0.1:8008', 1)[1]
        self.calls.append({'method': method, 'path': path, 'url': url,
                           'body': body, 'headers': headers or {}})
        return self.responses[(method, path)].pop(0)


def _json(call):
    return json.loads(call['body'])


def test_register_completes_registration_token_stage():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/register'): [
            (401, {'session': 's1', 'flows': [{'stages': ['m.login.registration_token']}]}),
            (200, {'user_id': '@alice:garden.home.arpa'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    user_id = client.register('alice', 'pw', 'tok')

    assert user_id == '@alice:garden.home.arpa'
    first, second = (_json(c) for c in fake.calls)
    assert first['username'] == 'alice' and 'auth' not in first
    assert second['auth'] == {'type': 'm.login.registration_token',
                              'token': 'tok', 'session': 's1'}
    assert second['inhibit_login'] is True


def test_register_completes_dummy_stage_after_token():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/register'): [
            (401, {'session': 's1',
                   'flows': [{'stages': ['m.login.registration_token', 'm.login.dummy']}]}),
            (401, {'session': 's1', 'completed': ['m.login.registration_token'],
                   'flows': [{'stages': ['m.login.registration_token', 'm.login.dummy']}]}),
            (200, {'user_id': '@alice:garden.home.arpa'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    client.register('alice', 'pw', 'tok')

    assert _json(fake.calls[2])['auth'] == {'type': 'm.login.dummy', 'session': 's1'}


def test_register_raises_on_error():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/register'): [
            (403, {'errcode': 'M_FORBIDDEN', 'error': 'Registration is disabled'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    with pytest.raises(mh.MatrixError, match='M_FORBIDDEN'):
        client.register('alice', 'pw', 'tok')


def test_login_returns_token_and_sends_password_identifier():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/login'): [
            (200, {'access_token': 'AT', 'user_id': '@hermes:garden.home.arpa',
                   'device_id': 'DEV'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    result = client.login('hermes', 'pw')

    assert result['access_token'] == 'AT'
    body = _json(fake.calls[0])
    assert body['type'] == 'm.login.password'
    assert body['identifier'] == {'type': 'm.id.user', 'user': 'hermes'}


def test_create_dm_is_unencrypted_and_marks_direct():
    fake = FakeTransport({
        ('GET', '/_matrix/client/v3/account/whoami'): [
            (200, {'user_id': '@me:garden.home.arpa'}),
        ],
        ('POST', '/_matrix/client/v3/createRoom'): [(200, {'room_id': '!r:garden.home.arpa'})],
        ('GET', '/_matrix/client/v3/user/%40me%3Agarden.home.arpa/account_data/m.direct'): [
            (404, {'errcode': 'M_NOT_FOUND'}),
        ],
        ('PUT', '/_matrix/client/v3/user/%40me%3Agarden.home.arpa/account_data/m.direct'): [
            (200, {}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake)

    room_id = client.create_dm('@hermes:garden.home.arpa')

    assert room_id == '!r:garden.home.arpa'
    create = _json(fake.calls[1])
    assert create['is_direct'] is True
    assert create['invite'] == ['@hermes:garden.home.arpa']
    assert create['preset'] == 'private_chat'  # trusted_private_chat だと Hermes も部屋の管理者になる
    assert all(ev['type'] != 'm.room.encryption' for ev in create.get('initial_state', []))
    assert _json(fake.calls[3]) == {'@hermes:garden.home.arpa': ['!r:garden.home.arpa']}
    assert fake.calls[1]['headers']['Authorization'] == 'Bearer AT'


def test_send_image_uploads_then_sends_m_image(tmp_path):
    img = tmp_path / 'leaf.jpg'
    img.write_bytes(b'\xff\xd8\xff\xe0jpegdata')
    fake = FakeTransport({
        ('POST', '/_matrix/media/v3/upload'): [(200, {'content_uri': 'mxc://garden.home.arpa/abc'})],
        ('PUT', '/_matrix/client/v3/rooms/%21r%3Agarden.home.arpa/send/m.room.message/t1'): [
            (200, {'event_id': '$e'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake,
                       txn_ids=iter(['t1']))

    client.send_image('!r:garden.home.arpa', img)

    upload, send = fake.calls
    assert upload['body'] == img.read_bytes()
    assert upload['headers']['Content-Type'] == 'image/jpeg'
    assert 'filename=leaf.jpg' in upload['url']
    event = _json(send)
    assert event['msgtype'] == 'm.image'
    assert event['url'] == 'mxc://garden.home.arpa/abc'
    assert event['body'] == 'leaf.jpg'
    assert event['info'] == {'mimetype': 'image/jpeg', 'size': len(img.read_bytes())}
    assert event['filename'] == 'leaf.jpg'


def test_send_image_caption_goes_to_body_and_filename_is_kept(tmp_path):
    img = tmp_path / 'leaf.jpg'
    img.write_bytes(b'\xff\xd8\xff\xe0jpegdata')
    fake = FakeTransport({
        ('POST', '/_matrix/media/v3/upload'): [(200, {'content_uri': 'mxc://garden.home.arpa/abc'})],
        ('PUT', '/_matrix/client/v3/rooms/%21r%3Agarden.home.arpa/send/m.room.message/t1'): [
            (200, {'event_id': '$e'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake,
                       txn_ids=iter(['t1']))

    client.send_image('!r:garden.home.arpa', img, caption='葉の写真')

    event = _json(fake.calls[1])
    assert event['body'] == '葉の写真'
    assert event['filename'] == 'leaf.jpg'


def test_send_image_without_caption_uses_filename_as_body(tmp_path):
    img = tmp_path / 'leaf.png'
    img.write_bytes(b'\x89PNGdata')
    fake = FakeTransport({
        ('POST', '/_matrix/media/v3/upload'): [(200, {'content_uri': 'mxc://garden.home.arpa/p'})],
        ('PUT', '/_matrix/client/v3/rooms/%21r%3Agarden.home.arpa/send/m.room.message/t1'): [
            (200, {'event_id': '$e'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake,
                       txn_ids=iter(['t1']))

    client.send_image('!r:garden.home.arpa', img)

    event = _json(fake.calls[1])
    assert event['body'] == 'leaf.png'
    assert fake.calls[0]['headers']['Content-Type'] == 'image/png'


def test_read_token_file_finds_matrix_access_token_line(tmp_path):
    env = tmp_path / '.env'
    env.write_text('TELEGRAM_BOT_TOKEN=x\nMATRIX_ACCESS_TOKEN=abc123\n', encoding='utf-8')

    assert mh.read_token_file(env) == 'abc123'


def test_read_token_file_without_line_raises(tmp_path):
    env = tmp_path / '.env'
    env.write_text('TELEGRAM_BOT_TOKEN=x\n', encoding='utf-8')

    with pytest.raises(mh.MatrixError, match='MATRIX_ACCESS_TOKEN'):
        mh.read_token_file(env)
