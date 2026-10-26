import json
import os
from datetime import datetime, timedelta, timezone

from PIL import Image

from app.utils.upload import THUMBNAIL_SIZE
from tests.api.helpers import file_part, image_bytes

URL = '/api/v1/conversations'
TS = 1761378929.5
CURL_GET = ('curl -sS -H "Authorization: Bearer $GARDEN_API_TOKEN" '
            '"$GARDEN_API_URL/plantings/45"')


def msg(mid, role='user', content='こんにちは', **kw):
    m = {'id': mid, 'role': role, 'content': content, 'tool_calls': None, 'tool_call_id': None,
         'tool_name': None, 'timestamp': TS + mid, 'display_kind': None}
    m.update(kw)
    return m


def call_msg(mid, command, call_id='call_1'):
    calls = [{'id': call_id, 'call_id': call_id,
              'function': {'name': 'terminal',
                           'arguments': json.dumps({'command': command, 'timeout': 30})}}]
    return msg(mid, 'assistant', '', tool_calls=calls)


def payload(title='じゃがいも', messages=None, **session):
    s = {'id': '20261025_165529_f52993ca', 'source': 'matrix', 'title': title,
         'started_at': TS, 'ended_at': None, 'last_activity_at': TS + 100,
         'end_reason': None, 'parent_session_id': None}
    s.update(session)
    if messages is None:
        messages = [msg(1), msg(2, 'assistant', 'はい'), msg(3)]
    return {'session': s, 'messages': messages}


def post_with_images(api, body, **images):
    form = {'data': json.dumps(body, ensure_ascii=False),
            'images': [file_part(data, name) for name, data in images.items()]}
    return api.post(URL, data=form, content_type='multipart/form-data')


def counts(sql):
    return [sql(f'SELECT COUNT(*) AS n FROM {t}')[0]['n']
            for t in ('conversation_messages', 'conversation_images', 'conversation_links')]


def test_create_then_update(api):
    r = api.post(URL, json=payload())
    assert r.status_code == 201 and r.json['data']['message_count'] == 3
    assert r.json['data']['hermes_id'] == '20261025_165529_f52993ca'
    r = api.post(URL, json=payload(title='変更'))
    assert r.status_code == 200


def test_resend_is_idempotent(api, sql):
    body = payload(messages=[msg(1), call_msg(2, CURL_GET)])
    first = post_with_images(api, body, **{'img_aaa.jpg': image_bytes('JPEG')})
    assert first.status_code == 201 and first.json['data']['image_count'] == 1
    before = counts(sql)
    assert before == [2, 1, 1]
    second = post_with_images(api, body, **{'img_aaa.jpg': image_bytes('JPEG')})
    assert second.status_code == 200 and second.json['data']['image_count'] == 1
    assert counts(sql) == before


def test_missing_messages_are_kept_and_links_use_all(api, sql):
    api.post(URL, json=payload(messages=[msg(1), call_msg(2, CURL_GET)]))
    r = api.post(URL, json=payload(messages=[msg(5, content='別の発言')]))
    assert r.json['data']['message_count'] == 3
    links = sql('SELECT entity_type, entity_id, kind FROM conversation_links')
    assert links == [{'entity_type': 'planting', 'entity_id': 45, 'kind': 'viewed'}]


def test_thumbnail_only(api, api_app):
    r = post_with_images(api, payload(), **{'img_big.png': image_bytes('PNG', (2000, 1500))})
    assert r.status_code == 201
    folder = os.path.join(api_app.config['UPLOAD_FOLDER'], 'conversations')
    assert not os.path.exists(os.path.join(folder, 'thumbs'))
    names = os.listdir(folder)
    assert len(names) == 1 and names[0].endswith('.jpg')
    with Image.open(os.path.join(folder, names[0])) as img:
        assert img.format == 'JPEG'
        assert img.width <= THUMBNAIL_SIZE[0] and img.height <= THUMBNAIL_SIZE[1]


def test_unreadable_image_is_skipped(api, sql):
    r = post_with_images(api, payload(), **{'img_bad.jpg': 'ただのテキスト'.encode(),
                                            'img_ok.jpg': image_bytes('JPEG')})
    assert r.status_code == 201
    assert r.json['data']['skipped_images'] == ['img_bad.jpg']
    assert r.json['data']['image_count'] == 1


def test_validation_errors(api):
    body = payload(messages=[msg(1, role='system')])
    del body['session']['id']
    body['session']['foo'] = 1
    r = api.post(URL, json=body)
    assert r.status_code == 422
    fields = [d['field'] for d in r.json['error']['details']]
    assert 'session.id' in fields and 'session.foo' in fields and 'messages[0].role' in fields
    r = api.post(URL, json={'session': payload()['session'], 'messages': 'x', 'extra': 1})
    assert r.status_code == 422
    fields = [d['field'] for d in r.json['error']['details']]
    assert 'messages' in fields and 'extra' in fields


def test_message_id_bounds(api):
    r = api.post(URL, json=payload(messages=[msg(2 ** 63)]))
    assert r.status_code == 422


def test_bad_image_name_is_422(api):
    r = post_with_images(api, payload(), **{'../x.jpg': image_bytes('JPEG')})
    assert r.status_code == 422


def test_requires_token(anon):
    assert anon.post(URL, json=payload()).status_code == 401


def test_times_are_jst_strings(api, sql):
    api.post(URL, json=payload())
    jst = timezone(timedelta(hours=9))
    expected = datetime.fromtimestamp(TS, jst).strftime('%Y-%m-%d %H:%M:%S')
    assert str(sql('SELECT started_at FROM conversations')[0]['started_at']) == expected


def test_relink_command(api_app, api, sql):
    api.post(URL, json=payload(messages=[call_msg(2, CURL_GET)]))
    assert counts(sql)[2] == 1
    sql('DELETE FROM conversation_links WHERE conversation_id > 0')
    assert counts(sql)[2] == 0
    from app import create_app
    web = create_app('api_pytest')
    result = web.test_cli_runner().invoke(args=['relink-conversations'])
    assert result.exit_code == 0, result.output
    assert counts(sql)[2] == 1
