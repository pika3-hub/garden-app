import json

import pytest

from app.utils.hermes_context import (
    build_instructions, describe_target, friendly_tool_label, links_for_messages,
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
