"""Hermes に聞くパネル用: 対象の説明、Hermes への指示、途中経過の言い換え、リンクの取り出し。"""
import json

from app.database import get_db
from app.models.photo_pool import _labels
from app.utils.conversation_links import (
    _parse_curl, _segments, _tokenize, extract_links,
)

# パネルを置く画面の種類: entity_type -> (表示名, API のパス)
_TARGETS = {
    'planting': ('植え付け', '/plantings'),
    'crop': ('作物', '/crops'),
    'variety': ('品種', '/varieties'),
}

# API のパス -> 日本語名
_RESOURCE_NAMES = {
    'crops': '作物', 'varieties': '品種', 'locations': '場所', 'plantings': '植え付け',
    'planting_records': '栽培記録', 'harvests': '収穫', 'cooking_records': '料理',
    'diary_entries': '日記', 'tasks': 'タスク', 'advices': 'アドバイス', 'photos': '写真プール',
}

_DEFAULT_LABEL = '作業中…'

_INSTRUCTIONS_WITH_TARGET = (
    'ユーザーはアプリ（家庭菜園管理アプリ）の{kind_label}の画面を見ながら、画面の横のパネルから質問している。\n'
    '見ている{kind_label}: {label}（id={entity_id}）\n'
    '質問の主語や対象が省かれていたら、この{kind_label}のことと考える。\n'
    '答える前に、API の GET {api_path} で中身を確かめる（植え付けなら栽培記録も）。\n'
    '答えはパネルに表示されるので、Element X のときより少し短めにまとめる。'
)
_INSTRUCTIONS_NO_TARGET = 'ユーザーはアプリ（家庭菜園管理アプリ）の画面のパネルから質問している。'


_INSTRUCTIONS_CHAT = (
    'ユーザーはアプリ（家庭菜園管理アプリ）のチャット画面から相談している。見ているデータは無い。\n'
    '答えは画面いっぱいに表示されるので、Element X と同じくらいの長さでよい。'
)


def describe_target(entity_type, entity_id):
    """パネルを置く対象の説明。種類が違う・消えているなら None"""
    spec = _TARGETS.get(entity_type)
    if spec is None:
        return None
    label = _labels(get_db(), entity_type, [entity_id]).get(entity_id)
    if label is None:
        return None
    kind_label, base = spec
    return {'entity_type': entity_type, 'entity_id': entity_id, 'kind_label': kind_label,
            'label': label, 'api_path': f'{base}/{entity_id}'}


def build_instructions(target, place='panel'):
    """place は相談している画面（'panel' = 詳細画面のパネル、'chat' = チャット画面）。
    対象があるときは place に関係なく同じ（対象の画面を見ながらの相談として扱う）"""
    if not target:
        return _INSTRUCTIONS_CHAT if place == 'chat' else _INSTRUCTIONS_NO_TARGET
    return _INSTRUCTIONS_WITH_TARGET.format(**target)


def _terminal_label(preview):
    if not isinstance(preview, str):
        return _DEFAULT_LABEL
    for seg in _segments(_tokenize(preview)):
        parsed = _parse_curl(seg)
        if not parsed:
            continue
        method, parts = parsed
        name = _RESOURCE_NAMES.get(parts[0]) if parts else None
        if name is None:
            continue
        if method == 'GET':
            return f'{name}の情報を読んでいます'
        if method == 'POST':
            return f'{name}を登録しています'
        if method == 'PATCH':
            return f'{name}を更新しています'
    return _DEFAULT_LABEL


def friendly_tool_label(event):
    """tool.started の event から、画面に出す文。preview の中身はそのまま出さない"""
    tool = str(event.get('tool') or '')
    if tool == 'terminal':
        return _terminal_label(event.get('preview'))
    if tool.startswith('web_search') or tool == 'web_extract':
        return 'Web で調べています'
    if tool == 'vision_analyze':
        return '写真を見ています'
    return _DEFAULT_LABEL


def links_for_messages(messages):
    """Hermes のセッションの発言から、作った・変えた・見たデータのリンクを取り出す"""
    prepared = []
    for m in messages:
        calls = m.get('tool_calls')
        if isinstance(calls, (list, dict)):
            calls = json.dumps(calls, ensure_ascii=False)
        prepared.append({
            'role': m.get('role'), 'content': m.get('content'), 'tool_calls': calls,
            'tool_call_id': m.get('tool_call_id'), 'hermes_message_id': m.get('id'),
        })
    return extract_links(prepared)
