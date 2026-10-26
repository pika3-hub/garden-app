"""Hermes の発言（terminal の curl）から、作った・変えた・見たデータを取り出す。

DB には触れない純粋関数。壊れた入力は例外にせず、拾わないだけにする。
"""
import json
import re
import shlex

RESOURCE_TYPES = {
    'crops': 'crop', 'varieties': 'variety', 'locations': 'location',
    'plantings': 'planting', 'planting_records': 'planting_record',
    'harvests': 'harvest', 'cooking_records': 'cooking',
    'diary_entries': 'diary', 'tasks': 'task', 'photos': 'photo_pool',
}

_URL_RE = re.compile(r'(?:\$GARDEN_API_URL|\$\{GARDEN_API_URL\}|/api/v1)/([^?#\s"\']*)')
_ID_RE = re.compile(r'[0-9]{1,19}')
_MAX_ID = 9223372036854775807  # SQLite の INTEGER の上限
_SEPARATORS = {'&&', '||', ';', '|', '&', '(', ')', '\n'}
# 値を1つ取るオプション（URL を探すとき値を飛ばす）
_VALUE_OPTS = {
    '-X', '--request', '-H', '--header', '-F', '--form', '-d', '-o', '--output',
    '-m', '--max-time', '-u', '--user', '-A', '--user-agent', '-e', '--referer',
    '-b', '--cookie', '-c', '--cookie-jar', '--connect-timeout', '-T', '--upload-file',
}


def _tokenize(command):
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return command.split()


def _segments(tokens):
    seg = []
    for t in tokens:
        if t in _SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def _parse_curl(seg):
    """curl 1つ分のトークンから (method, path) を返す。API の URL が無ければ None。"""
    start = next((i for i, t in enumerate(seg) if t.rsplit('/', 1)[-1] == 'curl'), None)
    if start is None:
        return None
    args = seg[start + 1:]
    method = None
    has_body = False
    is_get = False
    path = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('-X', '--request'):
            if i + 1 < len(args):
                method = args[i + 1].upper()
            i += 2
            continue
        if a.startswith('-X') and len(a) > 2 and not a.startswith('--'):
            method = a[2:].upper()
        elif a in ('-G', '--get'):
            is_get = True
        elif a in ('-F', '--form', '-d') or a.startswith('--data') or a == '--json':
            has_body = True
            if a in _VALUE_OPTS or a == '--data-urlencode' or a in ('--data', '--data-raw', '--data-binary', '--data-ascii'):
                i += 2
                continue
        elif a in _VALUE_OPTS:
            i += 2
            continue
        if path is None:
            m = _URL_RE.search(a)
            if m:
                path = m.group(1)
        i += 1
    if path is None:
        return None
    if method is None:
        method = 'POST' if has_body and not is_get else 'GET'
    return method, [p for p in path.split('/') if p]


def _valid_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= _MAX_ID


def _created_ids(call_id, messages):
    ids = []
    if not call_id:
        return ids
    for m in messages:
        if m.get('role') != 'tool' or m.get('tool_call_id') != call_id:
            continue
        try:
            data = json.loads(m.get('content') or '')
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        data = data.get('data')
        rows = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
        for r in rows:
            if isinstance(r, dict) and _valid_id(r.get('id')):
                ids.append(r['id'])
    return ids


def _commands(msg):
    """assistant の発言から (call_id, command) を順に返す。"""
    try:
        calls = json.loads(msg.get('tool_calls') or 'null')
    except (TypeError, ValueError):
        return
    if not isinstance(calls, list):
        return
    for c in calls:
        try:
            fn = c['function']
            if fn.get('name') != 'terminal':
                continue
            command = json.loads(fn['arguments']).get('command')
            if isinstance(command, str):
                yield c.get('id') or c.get('call_id'), command
        except (KeyError, TypeError, ValueError, AttributeError):
            continue


def extract_links(messages):
    links = []
    seen = set()

    def add(etype, eid, kind, mid):
        key = (etype, eid, kind)
        if key not in seen:
            seen.add(key)
            links.append({'entity_type': etype, 'entity_id': eid, 'kind': kind,
                          'hermes_message_id': mid})

    for msg in messages:
        if msg.get('role') != 'assistant':
            continue
        mid = msg.get('hermes_message_id')
        for call_id, command in _commands(msg):
            parsed = [p for p in (_parse_curl(s) for s in _segments(_tokenize(command))) if p]
            post_count = sum(1 for method, _ in parsed if method == 'POST')
            for method, parts in parsed:
                etype = RESOURCE_TYPES.get(parts[0]) if parts else None
                if etype is None:
                    continue
                eid = int(parts[1]) if len(parts) > 1 and _ID_RE.fullmatch(parts[1]) else None
                if eid is not None and not _valid_id(eid):
                    continue
                n = len(parts)
                if method == 'POST' and n == 1:
                    if post_count == 1:
                        for new_id in _created_ids(call_id, messages):
                            add(etype, new_id, 'created', mid)
                elif eid is None:
                    continue
                elif method == 'PATCH' and n == 2:
                    add(etype, eid, 'updated', mid)
                elif method == 'POST' and n == 3 and parts[2] in ('end', 'images'):
                    add(etype, eid, 'updated', mid)
                elif method == 'GET' and (n == 2 or (n == 3 and parts[2] == 'image')):
                    add(etype, eid, 'viewed', mid)
    return links
