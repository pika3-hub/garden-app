import base64
from types import SimpleNamespace

import pytest

from app.utils.ai_notes import AiNotesError
from app.utils.ai_photo_drafts import generate_photo_draft

IMAGE = b'\xff\xd8\xff\xe0fake-jpeg'


def text_block(text):
    return SimpleNamespace(type='text', text=text, citations=None)


def thinking_block():
    return SimpleNamespace(type='thinking', thinking='')


def response(content, stop_reason='end_turn'):
    return SimpleNamespace(content=content, stop_reason=stop_reason, _request_id='req_test')


class FakeClient:
    """client.beta.messages.create(**kwargs) を記録し、用意した応答を順に返す"""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


PREV_IMAGE = b'\xff\xd8\xff\xe0previous-jpeg'

RECORD_CONTEXT = {
    'date': '2026-10-25',
    'plantings': [
        {'label': 'ミニトマト（アイコ）／南の畑',
         'previous': {'date': '2026-10-18', 'notes': '第2花房が開花。下葉に黄変なし', 'image': PREV_IMAGE}},
        {'label': 'なす／南の畑', 'previous': None},
    ],
}


def _user_text(call):
    return '\n'.join(b['text'] for b in call['messages'][0]['content'] if b['type'] == 'text')


def _b64(data):
    return base64.standard_b64encode(data).decode('ascii')


def test_planting_record_draft_sends_current_and_previous_photos():
    client = FakeClient(response([thinking_block(), text_block('{"notes": "第3花房まで開花"}')]))
    result = generate_photo_draft('planting_record', IMAGE, RECORD_CONTEXT,
                                  client=client, model='claude-opus-5-5')

    assert result == {'notes': '第3花房まで開花'}
    call = client.calls[0]
    content = call['messages'][0]['content']
    images = [b for b in content if b['type'] == 'image']
    assert [b['source']['data'] for b in images] == [_b64(IMAGE), _b64(PREV_IMAGE)]
    assert images[0]['source']['media_type'] == 'image/jpeg'
    # それぞれの写真の直前に、どの写真かを書いた文がある
    assert '今回の写真' in content[content.index(images[0]) - 1]['text']
    prev_label = content[content.index(images[1]) - 1]['text']
    assert '前回' in prev_label and 'ミニトマト（アイコ）／南の畑' in prev_label and '2026-10-18' in prev_label
    assert '第2花房が開花。下葉に黄変なし' in prev_label
    text = _user_text(call)
    assert 'なす／南の畑' in text
    assert '2026-10-25' in text
    assert 'tools' not in call
    fmt = call['output_config']['format']
    assert fmt['type'] == 'json_schema'
    assert fmt['schema']['required'] == ['notes']
    assert fmt['schema']['additionalProperties'] is False
    assert call['fallbacks'] == 'default'


def test_system_prompt_forbids_advice():
    client = FakeClient(response([text_block('{"notes": "x"}')]))
    generate_photo_draft('planting_record', IMAGE, RECORD_CONTEXT, client=client, model='claude-opus-5-5')
    assert 'アドバイス' in client.calls[0]['system']


def test_cooking_draft_returns_title_category_notes():
    client = FakeClient(response([text_block(
        '{"title": "トマトのマリネ", "category": "副菜", "notes": "ミニトマトを半分に切って和えた"}')]))
    context = {'date': '2026-10-25', 'categories': ['副菜', '汁物'], 'related': ['ミニトマト（アイコ）']}
    result = generate_photo_draft('cooking', IMAGE, context, client=client, model='claude-opus-5-5')

    assert result == {'title': 'トマトのマリネ', 'category': '副菜', 'notes': 'ミニトマトを半分に切って和えた'}
    text = _user_text(client.calls[0])
    assert '副菜' in text and '汁物' in text
    assert client.calls[0]['output_config']['format']['schema']['required'] == ['title', 'category', 'notes']


def test_diary_draft_returns_title_content():
    client = FakeClient(response([text_block('{"title": "秋の畑", "content": "畝全体の様子"}')]))
    result = generate_photo_draft('diary', IMAGE, {'date': '2026-10-25', 'related': []},
                                  client=client, model='claude-opus-5-5')
    assert result == {'title': '秋の畑', 'content': '畝全体の様子'}


def test_location_draft_uses_name():
    client = FakeClient(response([text_block('{"notes": "日当たりのよい畑"}')]))
    result = generate_photo_draft('location', IMAGE, {'name': '南の畑'}, client=client, model='claude-opus-5-5')
    assert result == {'notes': '日当たりのよい畑'}
    assert '南の畑' in _user_text(client.calls[0])


def test_haiku_has_no_fallbacks():
    client = FakeClient(response([text_block('{"notes": "x"}')]))
    generate_photo_draft('harvest', IMAGE, RECORD_CONTEXT, client=client, model='claude-haiku-5-5')
    call = client.calls[0]
    assert 'fallbacks' not in call
    assert 'betas' not in call


def test_missing_key_in_json_raises():
    client = FakeClient(response([text_block('{"title": "x"}')]))
    with pytest.raises(AiNotesError, match='読み取れません'):
        generate_photo_draft('cooking', IMAGE, {'date': '2026-10-25', 'categories': [], 'related': []},
                             client=client, model='claude-opus-5-5')


def test_invalid_json_raises():
    client = FakeClient(response([text_block('not json')]))
    with pytest.raises(AiNotesError, match='読み取れません'):
        generate_photo_draft('location', IMAGE, {'name': '畑'}, client=client, model='claude-opus-5-5')


def test_refusal_raises():
    client = FakeClient(response([], 'refusal'))
    with pytest.raises(AiNotesError, match='生成できません'):
        generate_photo_draft('location', IMAGE, {'name': '畑'}, client=client, model='claude-opus-5-5')


def test_unknown_kind_raises_value_error():
    with pytest.raises(ValueError):
        generate_photo_draft('crop', IMAGE, {}, client=FakeClient(), model='claude-opus-5-5')


def test_missing_api_key_raises_without_client(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(AiNotesError, match='ANTHROPIC_API_KEY'):
        generate_photo_draft('location', IMAGE, {'name': '畑'})


def test_without_previous_sends_only_current_photo():
    context = {'date': '2026-10-25', 'plantings': [{'label': 'なす／南の畑', 'previous': None}]}
    client = FakeClient(response([text_block('{"notes": "x"}')]))
    generate_photo_draft('planting_record', IMAGE, context, client=client, model='claude-opus-5-5')
    content = client.calls[0]['messages'][0]['content']
    assert [b['source']['data'] for b in content if b['type'] == 'image'] == [_b64(IMAGE)]
    assert '前回の写真' not in _user_text(client.calls[0])


def test_system_prompt_treats_notes_as_supplement_to_photo():
    client = FakeClient(response([text_block('{"notes": "x"}')]))
    generate_photo_draft('planting_record', IMAGE, RECORD_CONTEXT, client=client, model='claude-opus-5-5')
    system = client.calls[0]['system']
    assert '前回の写真' in system and '補助' in system
