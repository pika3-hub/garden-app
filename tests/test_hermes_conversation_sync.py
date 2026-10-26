"""tools/hermes_conversation_sync.py のテスト。送信は偽物に差し替え、実サーバーには接続しない。"""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / 'tools' / 'hermes_conversation_sync.py'
_spec = importlib.util.spec_from_file_location('hermes_conversation_sync', _PATH)
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)

_SESSIONS = ('id TEXT PRIMARY KEY, source TEXT, title TEXT, started_at REAL, ended_at REAL, '
             'last_activity_at REAL, end_reason TEXT, parent_session_id TEXT')
_MESSAGES = ('id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, '
             'tool_call_id TEXT, tool_name TEXT, timestamp REAL, display_kind TEXT, '
             'reasoning TEXT, reasoning_content TEXT')


def make_db(tmp_path, messages_ddl=_MESSAGES):
    path = tmp_path / 'state.db'
    c = sqlite3.connect(path)
    c.execute(f'CREATE TABLE sessions ({_SESSIONS})')
    c.execute(f'CREATE TABLE messages ({messages_ddl})')
    c.commit()
    c.close()
    return str(path)


def add_session(path, sid, source='matrix', title='t', started=1000.0):
    c = sqlite3.connect(path)
    c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)',
              (sid, source, title, started, None, started, None, None))
    c.commit()
    c.close()


def add_msg(path, sid, role, content, mid=None, tool_calls=None, tool_name=None,
            tool_call_id=None, ts=1001.0, reasoning=None):
    c = sqlite3.connect(path)
    c.execute('INSERT INTO messages (id, session_id, role, content, tool_calls, tool_call_id, '
              'tool_name, timestamp, display_kind, reasoning, reasoning_content) '
              'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
              (mid, sid, role, content, tool_calls, tool_call_id, tool_name, ts, None,
               reasoning, reasoning))
    c.commit()
    c.close()


class FakeTransport:
    def __init__(self, status=201):
        self.status = status
        self.calls = []

    def __call__(self, url, headers, body):
        self.calls.append({'url': url, 'headers': headers, 'body': body})
        return self.status, json.dumps({'ok': True, 'data': {}}).encode()


def setup_run(tmp_path):
    db = make_db(tmp_path)
    cache = tmp_path / 'cache'
    cache.mkdir()
    env = tmp_path / 'api.env'
    env.write_text('export GARDEN_API_URL="http://127.0.0.1:5001/api/v1"\n'
                   'GARDEN_API_TOKEN=secret-token-value\n', encoding='utf-8')
    argv = ['--db', db, '--state', str(tmp_path / 'state.json'), '--env', str(env),
            '--cache-dir', str(cache)]
    return db, cache, argv


def test_check_schema_missing_column(tmp_path):
    db = make_db(tmp_path, messages_ddl='id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT')
    conn = hs.open_db(db)
    with pytest.raises(hs.SchemaError) as e:
        hs.check_schema(conn)
    assert 'tool_calls' in str(e.value)


def test_selects_only_matrix_and_changed(tmp_path):
    db = make_db(tmp_path)
    add_session(db, 'a', started=1.0)
    add_session(db, 'b', started=2.0)
    add_session(db, 'c', source='cli', started=3.0)
    add_msg(db, 'a', 'user', 'hi', mid=1)
    add_msg(db, 'b', 'user', 'yo', mid=2)
    conn = hs.open_db(db)
    row_a = [r for r in conn.execute('SELECT * FROM sessions')][0]
    state = {'sessions': {'a': {'fingerprint': hs.fingerprint(conn, row_a)}}}
    assert [r['id'] for r in hs.select_sessions(conn, state)] == ['b']
    assert [r['id'] for r in hs.select_sessions(conn, {'sessions': {}})] == ['a', 'b']


def test_build_payload_filters(tmp_path):
    db = make_db(tmp_path)
    add_session(db, 's')
    add_msg(db, 's', 'session_meta', 'meta', mid=1)
    add_msg(db, 's', 'user', 'hello', mid=2)
    calls = json.dumps([
        {'id': 'c1', 'call_id': 'c1', 'response_item_id': 'fc_1', 'type': 'function',
         'function': {'name': 'terminal', 'arguments': '{"command": "ls"}'}},
        {'id': 'c2', 'call_id': 'c2', 'type': 'function',
         'function': {'name': 'skill_view', 'arguments': '{}'}},
    ])
    add_msg(db, 's', 'assistant', 'ok', mid=3, tool_calls=calls, reasoning='secret thoughts')
    add_msg(db, 's', 'tool', 'x' * 50, mid=4, tool_name='terminal', tool_call_id='c1')
    add_msg(db, 's', 'tool', 'skill body', mid=5, tool_name='skill_view', tool_call_id='c2')
    add_msg(db, 's', 'assistant', 'plain', mid=6, tool_calls=json.dumps(
        [{'id': 'c3', 'function': {'name': 'vision_analyze', 'arguments': '{}'}}]))
    conn = hs.open_db(db)
    row = conn.execute('SELECT * FROM sessions').fetchone()
    payload = hs.build_payload(conn, row, tool_limit=10)
    assert set(payload['session']) == {'id', 'source', 'title', 'started_at', 'ended_at',
                                       'last_activity_at', 'end_reason', 'parent_session_id'}
    msgs = payload['messages']
    assert [m['id'] for m in msgs] == [2, 3, 4, 6]
    assert all(set(m) == {'id', 'role', 'content', 'tool_calls', 'tool_call_id', 'tool_name',
                          'timestamp', 'display_kind'} for m in msgs)
    assert msgs[1]['tool_calls'] == [{'id': 'c1', 'call_id': 'c1', 'function': {
        'name': 'terminal', 'arguments': '{"command": "ls"}'}}]
    assert msgs[2]['content'] == 'x' * 10
    assert msgs[3]['tool_calls'] is None
    assert 'secret thoughts' not in json.dumps(payload)


def test_image_refs_outside_cache_are_ignored(tmp_path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    (cache / 'img_a.jpg').write_bytes(b'x')
    (cache / 'notes.txt').write_bytes(b'x')
    text = (f'[Image attached at: {cache / "img_a.jpg"}] [Image attached at: /etc/passwd] '
            f'[Image attached at: {cache / "notes.txt"}] [Image attached at: {cache / "img_b.jpg"}] '
            f'[Image attached at: {cache / "img_a.jpg"}] [Image attached at: {cache}/../x/img_c.jpg]')
    payload = {'messages': [{'role': 'user', 'content': text},
                            {'role': 'assistant', 'content': f'[Image attached at: {cache / "img_a.jpg"}]'}]}
    refs = hs.image_refs(payload, str(cache))
    assert refs == [str((cache / 'img_a.jpg').resolve())]


def _one_conversation(db, cache=None):
    add_session(db, 's')
    content = 'photo'
    if cache is not None:
        content = f'[Image attached at: {cache / "img_a.jpg"}] [screenshot]'
    add_msg(db, 's', 'user', content, mid=1)


def test_main_sends_and_saves_state(tmp_path):
    db, cache, argv = setup_run(tmp_path)
    _one_conversation(db)
    t = FakeTransport(201)
    assert hs.main(argv, transport=t) == 0
    assert len(t.calls) == 1
    assert t.calls[0]['url'] == 'http://127.0.0.1:5001/api/v1/conversations'
    assert t.calls[0]['headers']['Authorization'] == 'Bearer secret-token-value'
    state = json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))
    assert state['sessions']['s']['fingerprint'][0] == 1
    assert state['sessions']['s']['sent_images'] == []
    assert hs.main(argv, transport=t) == 0
    assert len(t.calls) == 1


def test_send_failure_keeps_state(tmp_path, monkeypatch, capsys):
    db, cache, argv = setup_run(tmp_path)
    _one_conversation(db)
    t = FakeTransport(500)
    assert hs.main(argv, transport=t) == 1
    state = json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))
    assert state == {'sessions': {}}
    out = capsys.readouterr()
    assert 'secret-token-value' not in out.out + out.err

    # DB がロックされていれば送らず終了コード 1
    monkeypatch.setattr(hs, 'DB_TIMEOUT', 0.1)
    locker = sqlite3.connect(db, isolation_level=None)
    locker.execute('BEGIN EXCLUSIVE')
    t2 = FakeTransport(201)
    try:
        assert hs.main(argv, transport=t2) == 1
    finally:
        locker.execute('ROLLBACK')
        locker.close()
    assert t2.calls == []


def test_images_not_resent(tmp_path):
    db, cache, argv = setup_run(tmp_path)
    (cache / 'img_a.jpg').write_bytes(b'JPEGDATA')
    _one_conversation(db, cache)
    t = FakeTransport(201)
    assert hs.main(argv, transport=t) == 0
    assert b'filename="img_a.jpg"' in t.calls[0]['body']
    add_msg(db, 's', 'assistant', 'more', mid=2)
    assert hs.main(argv, transport=t) == 0
    assert len(t.calls) == 2
    assert b'name="images"' not in t.calls[1]['body']
    state = json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))
    assert state['sessions']['s']['sent_images'] == ['img_a.jpg']


def test_dry_run_sends_nothing(tmp_path, capsys):
    db, cache, argv = setup_run(tmp_path)
    _one_conversation(db)
    t = FakeTransport(201)
    assert hs.main(argv + ['--dry-run'], transport=t) == 0
    assert t.calls == []
    out = capsys.readouterr().out
    assert 's' in out and '発言 1' in out
    assert not (tmp_path / 'state.json').exists()


def test_images_batched_by_twenty(tmp_path):
    db, cache, argv = setup_run(tmp_path)
    add_session(db, 's')
    names = [f'img_{i:02d}.jpg' for i in range(25)]
    for n in names:
        (cache / n).write_bytes(b'x')
    add_msg(db, 's', 'user', ' '.join(f'[Image attached at: {cache / n}]' for n in names), mid=1)
    t = FakeTransport(201)
    assert hs.main(argv, transport=t) == 0
    assert t.calls[0]['body'].count(b'name="images"') == 20
    state = json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))
    assert len(state['sessions']['s']['sent_images']) == 20
    assert state['sessions']['s']['fingerprint'] != [1, 't', None, None]
    assert hs.main(argv, transport=t) == 0
    assert len(t.calls) == 2
    assert t.calls[1]['body'].count(b'name="images"') == 5
    state = json.loads((tmp_path / 'state.json').read_text(encoding='utf-8'))
    assert len(state['sessions']['s']['sent_images']) == 25
    assert state['sessions']['s']['fingerprint'] == [1, 't', None, None]
    assert hs.main(argv, transport=t) == 0
    assert len(t.calls) == 2


def test_bad_image_name_skipped_and_422_logged(tmp_path, capsys):
    db, cache, argv = setup_run(tmp_path)
    add_session(db, 's')
    (cache / 'img bad.jpg').write_bytes(b'x')
    add_msg(db, 's', 'user', f'[Image attached at: {cache / "img bad.jpg"}]', mid=1)

    def t422(url, headers, body):
        assert b'name="images"' not in body
        return 422, json.dumps({'ok': False, 'error': {'code': 'validation_error', 'message': 'bad'}}).encode()
    assert hs.main(argv, transport=t422) == 1
    err = capsys.readouterr()
    assert 'validation_error' in err.err and 'HTTP 422' in err.err
    assert '不正な名前の写真 1' in err.out
