from types import SimpleNamespace

import anthropic
import pytest

try:
    import httpx2 as httpx
except ImportError:  # anthropic 0.x 系
    import httpx

from app.utils import ai_notes
from app.utils.ai_notes import AiNotesError, generate_notes, resolve_model

_REQ = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')


def _status_error(cls, status):
    return cls('error', response=httpx.Response(status, request=_REQ), body=None)


def text_block(text, citations=None):
    return SimpleNamespace(type='text', text=text, citations=citations)


def citation(url, title):
    return SimpleNamespace(type='web_search_result_location', url=url, title=title,
                           cited_text='...')


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


def call(client, **overrides):
    kwargs = dict(crop_name='ミニトマト', crop_type='トマト', variety_name=None,
                  region='神奈川県（温暖地）露地', use_web_search=False,
                  client=client, model='claude-opus-5-5')
    kwargs.update(overrides)
    return generate_notes(**kwargs)


# --- resolve_model / is_available ---

def test_resolve_model_defaults_when_unset():
    assert resolve_model(None) == 'claude-opus-5-5'
    assert resolve_model('') == 'claude-opus-5-5'


def test_resolve_model_accepts_allowed_values():
    assert resolve_model('claude-sonnet-5-5') == 'claude-sonnet-5-5'
    assert resolve_model('claude-haiku-5-5') == 'claude-haiku-5-5'
    assert resolve_model(' claude-opus-5-5 ') == 'claude-opus-5-5'


def test_resolve_model_falls_back_on_unknown(caplog):
    assert resolve_model('claude-haiku-4-5') == 'claude-opus-5-5'
    assert 'claude-haiku-4-5' in caplog.text


def test_model_info_covers_allowed_models():
    for model in ('claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'):
        info = ai_notes.MODEL_INFO[model]
        assert info['label'] and info['estimate_off'] and info['estimate_on']


@pytest.mark.parametrize('value, expected', [
    (None, False), ('', False), ('   ', False), ('sk-ant-xxx', True),
])
def test_is_available(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    else:
        monkeypatch.setenv('ANTHROPIC_API_KEY', value)
    assert ai_notes.is_available() is expected


# --- リクエスト内容 ---

def test_request_params_without_web_search():
    client = FakeClient(response([text_block('## 植え付け時期\n4月')]))
    call(client)
    params = client.calls[0]
    assert params['model'] == 'claude-opus-5-5'
    assert params['max_tokens'] == 16000
    assert params['output_config'] == {'effort': 'medium'}
    assert params['betas'] == ['server-side-fallback-2026-07-01']
    assert params['fallbacks'] == 'default'
    assert 'thinking' not in params
    assert 'tools' not in params
    assert '## 栽培のコツ' in params['system']


def test_request_params_with_web_search():
    client = FakeClient(response([text_block('本文')]))
    call(client, use_web_search=True)
    assert client.calls[0]['tools'] == [{
        'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 5,
        'user_location': {'type': 'approximate', 'country': 'JP'},
    }]


def test_haiku_request_has_no_fallbacks_and_uses_basic_web_search():
    # Haiku 5.5 はサーバー側フォールバックが無く、web_search_20260209 も公式の対応外
    client = FakeClient(response([text_block('本文')]))
    call(client, model='claude-haiku-5-5', use_web_search=True)
    params = client.calls[0]
    assert params['model'] == 'claude-haiku-5-5'
    assert params['output_config'] == {'effort': 'medium'}
    assert 'betas' not in params
    assert 'fallbacks' not in params
    assert params['tools'] == [{
        'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 5,
        'user_location': {'type': 'approximate', 'country': 'JP'},
    }]


def test_user_message_for_crop_contains_crop_and_region():
    client = FakeClient(response([text_block('本文')]))
    call(client)
    message = client.calls[0]['messages'][0]['content']
    assert 'ミニトマト' in message
    assert 'トマト' in message
    assert '神奈川県（温暖地）露地' in message
    assert '品種名' not in message


def test_user_message_for_variety_mentions_variety_specific():
    client = FakeClient(response([text_block('本文')]))
    call(client, crop_name='トマト', crop_type='トマト', variety_name='アイコ')
    message = client.calls[0]['messages'][0]['content']
    assert '品種名: アイコ' in message
    assert '品種固有' in message


def test_uses_given_model():
    client = FakeClient(response([text_block('本文')]))
    call(client, model='claude-sonnet-5-5')
    assert client.calls[0]['model'] == 'claude-sonnet-5-5'


# --- 出力と参考URL ---

def test_returns_joined_text_without_sources_when_search_off():
    client = FakeClient(response([text_block('## 植え付け時期\n'), text_block('4月〜5月')]))
    assert call(client) == '## 植え付け時期\n4月〜5月'


def test_empty_text_raises():
    blocks = [SimpleNamespace(type='web_search_tool_result', tool_use_id='s1', content=[]),
              text_block('   ')]
    with pytest.raises(AiNotesError, match='空'):
        call(FakeClient(response(blocks)), use_web_search=True)


# --- pause_turn ---

def test_pause_turn_continues_with_accumulated_content():
    first = [SimpleNamespace(type='server_tool_use', id='s1', name='web_search', input={})]
    client = FakeClient(response(first, 'pause_turn'), response([text_block('続き')]))
    assert call(client, use_web_search=True) == '続き'
    second_messages = client.calls[1]['messages']
    assert second_messages[0]['role'] == 'user'
    assert second_messages[1] == {'role': 'assistant', 'content': first}


def test_pause_turn_limit_raises():
    pauses = [response([text_block('途中')], 'pause_turn') for _ in range(4)]
    client = FakeClient(*pauses)
    with pytest.raises(AiNotesError, match='途中'):
        call(client, use_web_search=True)
    assert len(client.calls) == 4  # 初回 + 継続3回


# --- stop_reason ---

def test_refusal_raises():
    with pytest.raises(AiNotesError, match='生成できませんでした'):
        call(FakeClient(response([], 'refusal')))


def test_max_tokens_raises():
    with pytest.raises(AiNotesError, match='途中'):
        call(FakeClient(response([text_block('途中まで')], 'max_tokens')))


# --- 例外変換 ---

@pytest.mark.parametrize('exc, fragment', [
    (lambda: _status_error(anthropic.AuthenticationError, 401), 'APIキーが無効'),
    (lambda: _status_error(anthropic.PermissionDeniedError, 403), '権限'),
    (lambda: _status_error(anthropic.RateLimitError, 429), '混み合って'),
    (lambda: _status_error(anthropic.InternalServerError, 500), 'AIサービス側'),
    (lambda: _status_error(anthropic.BadRequestError, 400), '生成に失敗しました'),
    (lambda: anthropic.APITimeoutError(request=_REQ), '時間内に'),
    (lambda: anthropic.APIConnectionError(request=_REQ), '通信エラー'),
])
def test_sdk_errors_are_translated(exc, fragment):
    with pytest.raises(AiNotesError, match=fragment):
        call(FakeClient(exc()))


def test_missing_api_key_raises_without_client(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(AiNotesError) as e:
        generate_notes('トマト', None, None, '東京', False)
    assert str(e.value) == ai_notes.NO_API_KEY_MESSAGE


# --- タイムアウトと再試行（最終レビュー指摘） ---

def test_client_is_created_without_sdk_retries(monkeypatch):
    created = {}

    def fake_anthropic(**kwargs):
        created.update(kwargs)
        return FakeClient(response([text_block('本文')]))

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    monkeypatch.setattr(ai_notes.anthropic, 'Anthropic', fake_anthropic)
    generate_notes('トマト', None, None, '東京', False)
    assert created['max_retries'] == 0


def test_each_call_gets_remaining_time_budget():
    first = [SimpleNamespace(type='server_tool_use', id='s1', name='web_search', input={})]
    client = FakeClient(response(first, 'pause_turn'), response([text_block('続き')]))
    call(client, use_web_search=True)
    timeouts = [c['timeout'] for c in client.calls]
    assert all(0 < t <= ai_notes.REQUEST_TIMEOUT_SECONDS for t in timeouts)
    assert timeouts[1] <= timeouts[0]


def test_overall_deadline_exceeded_raises_timeout(monkeypatch):
    clock = iter([0.0, 0.0, 200.0])
    monkeypatch.setattr(ai_notes.time, 'monotonic', lambda: next(clock))
    first = [SimpleNamespace(type='server_tool_use', id='s1', name='web_search', input={})]
    client = FakeClient(response(first, 'pause_turn'), response([text_block('続き')]))
    with pytest.raises(AiNotesError, match='時間内に'):
        call(client, use_web_search=True)
    assert len(client.calls) == 1




# --- 参考URL: AI が書いた「## 参考URL」を検索結果・citations と照合し、実在するものだけ残す ---
# （web_search_20260209 は動的フィルタリングで citations が付かないことが多い。
#   検索結果の上位をそのまま付けると、読んでいないページ（カブ→バイクのカブ）が混ざる）

def search_result_block(*pairs):
    return SimpleNamespace(type='web_search_tool_result', tool_use_id='s1',
                           content=[SimpleNamespace(type='web_search_result', url=u, title=t)
                                    for u, t in pairs])


BODY = '## 植え付け時期\n9月'


def test_sources_written_by_ai_are_kept_only_if_in_search_results():
    blocks = [
        search_result_block(('https://a.example/1', 'A [種苗]'), ('https://b.example/2', 'B')),
        text_block(BODY + '\n\n## 参考URL\n'
                   '- [Aのページ](https://a.example/1)\n'
                   '- [架空](https://fake.example/x)\n'),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result == BODY + '\n\n## 参考URL\n- [A ［種苗］](https://a.example/1)'


def test_url_variants_are_matched():
    # 末尾の /・http/https・ホストの大文字・%エンコードの有無は同一とみなす
    blocks = [
        search_result_block(('https://a.example/kabu/', 'A'),
                            ('https://b.example/%E3%82%AB%E3%83%96', 'B'),
                            ('http://c.example/x', 'C')),
        text_block(BODY + '\n\n## 参考URL\n'
                   '- [a](http://A.example/kabu)\n'
                   '- [b](https://b.example/カブ)\n'
                   '- https://c.example/x/\n'),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result == (BODY + '\n\n## 参考URL\n'
                      '- [A](https://a.example/kabu/)\n'
                      '- [B](https://b.example/%E3%82%AB%E3%83%96)\n'
                      '- [C](http://c.example/x)')


def test_query_string_difference_is_not_matched():
    blocks = [
        search_result_block(('https://a.example/?p=1', 'A')),
        text_block(BODY + '\n\n## 参考URL\n- [a](https://a.example/?p=2)\n'),
    ]
    assert call(FakeClient(response(blocks)), use_web_search=True) == BODY


def test_url_with_parentheses_in_markdown_link():
    blocks = [
        search_result_block(('https://w.example/カブ_(植物)', 'カブ (植物)')),
        text_block(BODY + '\n\n## 参考URL\n- [カブ](https://w.example/カブ_(植物))\n'),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result.endswith('- [カブ (植物)](https://w.example/カブ_(植物))')


def test_duplicate_sources_are_listed_once_in_ai_order():
    blocks = [
        search_result_block(('https://a.example/1', 'A'), ('https://b.example/2', 'B')),
        text_block(BODY + '\n\n## 参考URL\n'
                   '- [b](https://b.example/2)\n- [a](https://a.example/1)\n'
                   '- [b again](https://b.example/2/)\n'),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result.endswith('## 参考URL\n- [B](https://b.example/2)\n- [A](https://a.example/1)')


def test_cited_urls_count_as_known():
    blocks = [
        text_block('9月まき。', [citation('https://cited.example/', 'Cited')]),
        text_block('\n\n## 参考URL\n- [c](https://cited.example/)\n'),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result == '9月まき。\n\n## 参考URL\n- [Cited](https://cited.example/)'


def test_section_in_middle_is_removed_and_rest_kept():
    blocks = [
        search_result_block(('https://a.example/1', 'A')),
        text_block('## 特性\n甘い\n\n## 参考URL\n- [a](https://a.example/1)\n\n## 栽培のコツ\n- 株間: 10cm'),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result == ('## 特性\n甘い\n\n## 栽培のコツ\n- 株間: 10cm\n\n'
                      '## 参考URL\n- [A](https://a.example/1)')


def test_no_section_when_all_urls_unknown():
    blocks = [
        search_result_block(('https://a.example/1', 'A')),
        text_block(BODY + '\n\n## 参考URL\n- [x](https://fake.example/)\n'),
    ]
    assert call(FakeClient(response(blocks)), use_web_search=True) == BODY


def test_search_results_alone_are_not_appended():
    blocks = [search_result_block(('https://bike.example/cub', 'スーパーカブ')), text_block(BODY)]
    assert call(FakeClient(response(blocks)), use_web_search=True) == BODY


def test_citations_used_when_ai_wrote_no_section():
    blocks = [
        search_result_block(('https://other.example/', 'Other')),
        text_block('アイコは甘い。', [citation('https://a.example/aiko', 'アイコ | 種苗A')]),
        text_block('裂果しにくい。', [citation('https://a.example/aiko', 'アイコ | 種苗A'),
                                     citation('https://b.example/x', 'B [特集]')]),
    ]
    result = call(FakeClient(response(blocks)), use_web_search=True)
    assert result == (
        'アイコは甘い。裂果しにくい。\n\n'
        '## 参考URL\n'
        '- [アイコ | 種苗A](https://a.example/aiko)\n'
        '- [B ［特集］](https://b.example/x)'
    )


def test_section_removed_when_search_off():
    text = BODY + '\n\n## 参考URL\n- [x](https://a.example/1)\n'
    assert call(FakeClient(response([text_block(text)]))) == BODY


def test_search_error_result_is_ignored():
    error = SimpleNamespace(type='web_search_tool_result', tool_use_id='s1',
                            content=SimpleNamespace(type='web_search_tool_result_error',
                                                    error_code='max_uses_exceeded'))
    result = call(FakeClient(response([error, text_block('本文')])), use_web_search=True)
    assert result == '本文'


def test_title_falls_back_to_url():
    blocks = [
        search_result_block(('https://a.example/1', '')),
        text_block(BODY + '\n\n## 参考URL\n- [a](https://a.example/1)\n'),
    ]
    assert call(FakeClient(response(blocks)), use_web_search=True).endswith(
        '- [https://a.example/1](https://a.example/1)')


def test_user_message_asks_to_search_when_web_search_on():
    client = FakeClient(response([text_block('本文')]))
    call(client, use_web_search=True)
    assert 'Web検索' in client.calls[0]['messages'][0]['content']
    client = FakeClient(response([text_block('本文')]))
    call(client)
    assert 'Web検索' not in client.calls[0]['messages'][0]['content']
