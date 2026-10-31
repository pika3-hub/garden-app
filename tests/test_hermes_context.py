import json

import pytest

from app.utils.hermes_context import (
    build_instructions, describe_target, earlier_questions, friendly_tool_label,
    links_for_messages,
)
from tests.hermes_fakes import crop_id, planting_id, variety_id  # noqa: F401


def test_describe_planting(app, planting_id):
    with app.app_context():
        t = describe_target('planting', planting_id)
    assert t['kind_label'] == '植え付け'
    assert t['api_path'] == f'/plantings/{planting_id}'
    assert '玉ねぎ' in t['label'] and '東の畑' in t['label']


def test_describe_crop_and_variety(app, crop_id, variety_id):
    with app.app_context():
        c = describe_target('crop', crop_id)
        v = describe_target('variety', variety_id)
    assert c['kind_label'] == '作物' and c['api_path'] == f'/crops/{crop_id}'
    assert v['kind_label'] == '品種' and v['api_path'] == f'/varieties/{variety_id}'
    assert 'ネオアース' in v['label']


def test_describe_missing_or_unknown_is_none(app):
    with app.app_context():
        assert describe_target('planting', 99999) is None
        assert describe_target('harvest', 1) is None


def test_instructions_contain_target(app, planting_id):
    with app.app_context():
        text = build_instructions(describe_target('planting', planting_id))
    assert f'id={planting_id}' in text and f'GET /plantings/{planting_id}' in text
    assert '省かれていたら' in text


def test_instructions_without_target():
    assert 'パネルから質問している' in build_instructions(None)


@pytest.mark.parametrize('preview,expected', [
    ('curl -s -H "Authorization: Bearer $GARDEN_API_TOKEN" http://127.0.0.1:5001/api/v1/plantings/12', '植え付けの情報を読んでいます'),
    ('curl -s -X POST http://127.0.0.1:5001/api/v1/tasks -d @t.json', 'タスクを登録しています'),
    ('curl -s -X PATCH http://127.0.0.1:5001/api/v1/diary_entries/3', '日記を更新しています'),
    ('ls -la', '作業中…'),
])
def test_friendly_tool_label_terminal(preview, expected):
    assert friendly_tool_label({'event': 'tool.started', 'tool': 'terminal', 'preview': preview}) == expected


def test_friendly_label_never_echoes_preview():
    label = friendly_tool_label({'event': 'tool.started', 'tool': 'terminal', 'preview': 'echo SECRET123'})
    assert 'SECRET123' not in label


def test_friendly_label_other_tools():
    assert friendly_tool_label({'tool': 'web_search'}) == 'Web で調べています'
    assert friendly_tool_label({'tool': 'vision_analyze'}) == '写真を見ています'
    assert friendly_tool_label({'tool': 'unknown', 'preview': 'x'}) == '作業中…'
    assert friendly_tool_label({'tool': 'terminal'}) == '作業中…'


def _call(command):
    return {'id': 'c1', 'function': {'name': 'terminal', 'arguments': json.dumps({'command': command})}}


@pytest.mark.parametrize('as_list', [True, False])
def test_links_for_messages_accepts_list_or_json_string(as_list):
    calls = [_call('curl -s -X PATCH http://127.0.0.1:5001/api/v1/tasks/7')]
    messages = [
        {'id': 55, 'role': 'user', 'content': 'やって', 'tool_calls': None},
        {'id': 56, 'role': 'assistant', 'content': '', 'tool_calls': calls if as_list else json.dumps(calls)},
    ]
    assert links_for_messages(messages) == [
        {'entity_type': 'task', 'entity_id': 7, 'kind': 'updated', 'hermes_message_id': 56}]


def test_build_instructions_chat_place():
    assert 'チャット画面' in build_instructions(None, place='chat')
    assert build_instructions(None) == 'ユーザーはアプリ（家庭菜園管理アプリ）の画面のパネルから質問している。'


def test_build_instructions_say_earlier_turns_come_from_history():
    # 「前の質問はいつ？」に API（アドバイスの記録）を探しに行かず、会話の履歴で答えさせる（2026-10-30）
    target = {'kind_label': '植え付け', 'label': 'えびす ビニールハウス', 'entity_id': 128,
              'api_path': '/plantings/128'}
    for text in (build_instructions(target), build_instructions(None, place='chat')):
        assert 'この会話の履歴から答える' in text


# 2026-10-29 23:38:00 JST（＝ 14:38:00 UTC）
_TS = 1793284680.0


def _user(content, ts):
    return {'role': 'user', 'content': content, 'timestamp': ts}


def test_earlier_questions_lists_user_messages_with_jst_time():
    text = earlier_questions([
        _user('葉が白っぽいのは\nなぜ？', _TS),
        {'role': 'assistant', 'content': 'ANSWER_X', 'timestamp': _TS + 60},
        {'role': 'tool', 'content': 'SECRET123', 'timestamp': _TS + 70},
        _user('経過をまとめて', _TS + 86400 * 2),
    ])
    assert '10/29 23:38「葉が白っぽいのは なぜ？」' in text
    assert '10/31 23:38「経過をまとめて」' in text
    assert text.index('10/29') < text.index('10/31')
    assert 'SECRET123' not in text and 'ANSWER_X' not in text


def test_earlier_questions_limits_count_and_length():
    msgs = [_user(f'質問{i:02d}', _TS + i * 60) for i in range(15)]
    msgs.append(_user('あ' * 50, _TS + 3600))
    text = earlier_questions(msgs)
    lines = [l for l in text.splitlines() if l.startswith('- ')]
    assert len(lines) == 10
    assert '質問05' not in text and '質問06' in text
    assert '「' + 'あ' * 40 + '…」' in text


def test_earlier_questions_skips_bad_entries_and_empty():
    assert earlier_questions([]) == ''
    assert earlier_questions([{'role': 'assistant', 'content': 'x', 'timestamp': _TS}]) == ''
    text = earlier_questions([
        _user('時刻なし', None), _user('巨大', 10 ** 400), _user('  ', _TS),
        {'role': 'user', 'content': [{'type': 'text'}], 'timestamp': _TS},
    ])
    assert '日時不明「時刻なし」' in text and '日時不明「巨大」' in text
    assert len([l for l in text.splitlines() if l.startswith('- ')]) == 2


def test_instructions_append_earlier_questions(app, planting_id):
    with app.app_context():
        target = describe_target('planting', planting_id)
        text = build_instructions(target, earlier='これまでの質問XYZ')
    assert text.endswith('これまでの質問XYZ')
    assert build_instructions(None, 'chat', earlier='E').endswith('\nE')
    assert build_instructions(None, 'chat') == build_instructions(None, 'chat', earlier='')
