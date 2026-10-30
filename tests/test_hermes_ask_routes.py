"""Hermes に聞くパネルの中継のルート（/hermes/ask）のテスト。Hermes は呼ばず _open を差し替える"""
import json
import urllib.error

from tests.hermes_fakes import crop_id, fake_open, planting_id, variety_id  # noqa: F401


def _sse(*events):
    lines = [b': keepalive\n']
    for e in events:
        lines.append(('data: ' + json.dumps(e, ensure_ascii=False) + '\n').encode('utf-8'))
        lines.append(b'\n')
    return lines


def _start(client, fake_open, planting_id, run_id='run_1', key='k1'):
    fake_open.reply(202, {'run_id': run_id, 'status': 'started'})
    resp = client.post(f'/hermes/ask/planting/{planting_id}/runs',
                       json={'text': '質問', 'request_key': key})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return json.loads(fake_open.calls[-1].data)['session_id']


def _events_text(text):
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith('data: ')]


def _events(resp):
    return _events_text(resp.get_data(as_text=True))


def test_anonymous_rejected_and_nothing_sent(anon_client, fake_open, planting_id):
    for method, path in [('get', f'/hermes/ask/planting/{planting_id}/history'),
                         ('post', f'/hermes/ask/planting/{planting_id}/runs'),
                         ('post', f'/hermes/ask/planting/{planting_id}/new'),
                         ('get', '/hermes/ask/runs/run_x'),
                         ('get', '/hermes/ask/runs/run_x/events'),
                         ('post', '/hermes/ask/runs/run_x/approval')]:
        resp = getattr(anon_client, method)(path, json={}, headers={'Accept': 'application/json'})
        assert resp.status_code in (400, 401), path
    assert fake_open.calls == []


def test_start_run_sends_instructions_and_session(client, fake_open, planting_id):
    fake_open.reply(202, {'run_id': 'run_1', 'status': 'started'})
    resp = client.post(f'/hermes/ask/planting/{planting_id}/runs',
                       json={'text': 'そろそろ植え付けですかね？', 'request_key': 'k1'})
    assert resp.json == {'ok': True, 'run_id': 'run_1'}
    body = json.loads(fake_open.calls[0].data)
    assert body['session_id'].startswith(f'garden-planting-{planting_id}-')
    assert f'GET /plantings/{planting_id}' in body['instructions']
    assert body['input'] == 'そろそろ植え付けですかね？'


def test_start_run_sends_idempotency_key(client, fake_open, planting_id):
    fake_open.reply(202, {'run_id': 'run_1'})
    client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k1'})
    body = json.loads(fake_open.calls[0].data)
    assert fake_open.calls[0].get_header('Idempotency-key') == f"{body['session_id']}:k1"


def test_start_run_rejects_empty_and_long_text(client, fake_open, planting_id):
    url = f'/hermes/ask/planting/{planting_id}/runs'
    assert client.post(url, json={'text': '  ', 'request_key': 'k'}).status_code == 400
    assert client.post(url, json={'text': 'あ' * 4001, 'request_key': 'k'}).status_code == 400
    assert fake_open.calls == []


def test_start_run_hermes_down_returns_503(client, fake_open, planting_id):
    fake_open.raise_(urllib.error.URLError('refused'))
    resp = client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k'})
    assert resp.status_code == 503 and resp.json['error'] == 'Hermes に届きません'


def test_start_run_bad_key_and_other_error(client, fake_open, planting_id):
    url = f'/hermes/ask/planting/{planting_id}/runs'
    fake_open.reply(401, {'error': {'message': 'bad key'}})
    resp = client.post(url, json={'text': 'q', 'request_key': 'k'})
    assert resp.status_code == 503 and resp.json['error'] == 'Hermes のキーが合いません'
    fake_open.reply(500, {'error': 'boom'})
    resp = client.post(url, json={'text': 'q', 'request_key': 'k2'})
    assert resp.status_code == 502 and resp.json['error'] == 'Hermes でエラーが起きました'


def test_not_configured_returns_503(client, app, fake_open, planting_id):
    app.config['HERMES_API_KEY'] = ''
    resp = client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k'})
    assert resp.status_code == 503
    assert resp.json['error'] == 'Hermes への接続が設定されていません'
    assert fake_open.calls == []


def test_unknown_target_404_and_nothing_sent(client, fake_open):
    assert client.post('/hermes/ask/planting/99999/runs', json={'text': 'q', 'request_key': 'k'}).status_code == 404
    assert client.post('/hermes/ask/harvest/1/runs', json={'text': 'q', 'request_key': 'k'}).status_code == 404
    assert client.get('/hermes/ask/planting/99999/history').status_code == 404
    assert fake_open.calls == []


def test_crop_and_variety_targets(client, fake_open, crop_id, variety_id):
    fake_open.reply(202, {'run_id': 'run_c'})
    assert client.post(f'/hermes/ask/crop/{crop_id}/runs',
                       json={'text': 'q', 'request_key': 'k'}).status_code == 200
    fake_open.reply(202, {'run_id': 'run_v'})
    assert client.post(f'/hermes/ask/variety/{variety_id}/runs',
                       json={'text': 'q', 'request_key': 'k'}).status_code == 200
    assert f'GET /crops/{crop_id}' in json.loads(fake_open.calls[0].data)['instructions']
    assert f'GET /varieties/{variety_id}' in json.loads(fake_open.calls[1].data)['instructions']


def test_history_reports_running_run(client, fake_open, planting_id):
    fake_open.reply(202, {'run_id': 'run_1'})
    client.post(f'/hermes/ask/planting/{planting_id}/runs', json={'text': 'q', 'request_key': 'k'})
    fake_open.reply(200, {'object': 'list', 'data': []})            # get_session_messages
    fake_open.reply(200, {'run_id': 'run_1', 'status': 'running'})   # get_run
    data = client.get(f'/hermes/ask/planting/{planting_id}/history').json
    assert data['running_run_id'] == 'run_1'


def test_history_messages_and_finished_run(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.reply(200, {'object': 'list', 'data': [
        {'id': 1, 'role': 'user', 'content': '質問', 'timestamp': 1},
        {'id': 2, 'role': 'assistant', 'content': '', 'tool_calls': [{'x': 1}]},
        {'id': 3, 'role': 'tool', 'content': 'SECRET123'},
        {'id': 4, 'role': 'assistant', 'content': '**答え**', 'timestamp': 2},
    ]})
    fake_open.reply(200, {'run_id': 'run_1', 'status': 'completed'})
    data = client.get(f'/hermes/ask/planting/{planting_id}/history').json
    assert data['ok'] is True
    assert data['target']['kind_label'] == '植え付け'
    assert [m['role'] for m in data['messages']] == ['user', 'assistant']
    assert data['messages'][0]['html'] is None
    assert '<strong>答え</strong>' in data['messages'][1]['html']
    assert data['running_run_id'] is None
    assert 'SECRET123' not in json.dumps(data, ensure_ascii=False)


def _curl_call(call_id, path):
    return [{'id': call_id, 'type': 'function', 'function': {'name': 'terminal', 'arguments': json.dumps(
        {'command': f'curl -s -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/{path}'})}}]


def test_history_links_on_last_assistant_of_each_turn(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.reply(200, {'object': 'list', 'data': [
        {'id': 1, 'role': 'user', 'content': '質問1'},
        {'id': 2, 'role': 'assistant', 'content': '', 'tool_calls': _curl_call('c1', f'plantings/{planting_id}')},
        {'id': 3, 'role': 'tool', 'content': 'SECRET123', 'tool_call_id': 'c1'},
        {'id': 4, 'role': 'assistant', 'content': '答え1'},
        {'id': 5, 'role': 'user', 'content': '質問2'},
        {'id': 6, 'role': 'assistant', 'content': '答え2'},
    ]})
    fake_open.reply(200, {'run_id': 'run_1', 'status': 'completed'})
    data = client.get(f'/hermes/ask/planting/{planting_id}/history').json
    msgs = data['messages']
    assert [m['text'] for m in msgs] == ['質問1', '答え1', '質問2', '答え2']
    assert [(l['url'], l['kind_label']) for l in msgs[1]['links']] == [(f'/plantings/{planting_id}', '見た')]
    assert set(msgs[1]['links'][0]) == {'label', 'url', 'kind_label'}
    assert msgs[0]['links'] == [] and msgs[2]['links'] == [] and msgs[3]['links'] == []
    assert 'SECRET123' not in json.dumps(data, ensure_ascii=False)


def test_history_links_crash_gives_empty(client, fake_open, planting_id, monkeypatch):
    from app.routes import hermes_ask_routes

    def boom(_):
        raise RuntimeError('x')
    monkeypatch.setattr(hermes_ask_routes, 'links_for_messages', boom)
    _start(client, fake_open, planting_id)
    fake_open.reply(200, {'object': 'list', 'data': [
        {'id': 1, 'role': 'user', 'content': 'q'},
        {'id': 2, 'role': 'assistant', 'content': 'a'},
    ]})
    fake_open.reply(200, {'run_id': 'run_1', 'status': 'completed'})
    data = client.get(f'/hermes/ask/planting/{planting_id}/history').json
    assert data['ok'] is True and data['messages'][1]['links'] == []


def test_history_without_chat_does_not_call_hermes(client, fake_open, planting_id):
    data = client.get(f'/hermes/ask/planting/{planting_id}/history').json
    assert data['messages'] == [] and data['running_run_id'] is None
    assert fake_open.calls == []


def test_events_relay_only_translated(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.stream(_sse(
        {'event': 'tool.started', 'tool': 'terminal',
         'preview': 'curl -H "Authorization: Bearer SECRET123" http://x/api/v1/plantings/1'},
        {'event': 'tool.completed', 'tool': 'terminal', 'preview': 'SECRET123'},
        {'event': 'reasoning.available', 'text': 'SECRET123 考え中'},
        {'event': 'message.delta', 'delta': 'こんにちは'},
        {'event': 'run.completed', 'output': '**答え**'},
    ))
    fake_open.reply(200, {'object': 'list', 'data': [
        {'id': 1, 'role': 'user', 'content': '質問'},
        {'id': 2, 'role': 'assistant', 'content': '答え'},
    ]})
    resp = client.get('/hermes/ask/runs/run_1/events')
    assert resp.headers['Content-Type'].startswith('text/event-stream')
    assert resp.headers['Cache-Control'] == 'no-cache'
    assert resp.headers['X-Accel-Buffering'] == 'no'
    text = resp.get_data(as_text=True)
    assert '"type": "tool"' in text and '"type": "done"' in text
    assert 'SECRET123' not in text and 'test-hermes-key' not in text
    events = _events(resp)
    assert [e['type'] for e in events] == ['tool', 'delta', 'done']
    assert events[0]['label'] == '植え付けの情報を読んでいます'
    assert events[1]['text'] == 'こんにちは'
    assert '<strong>答え</strong>' in events[2]['html']
    assert events[2]['links'] == []


def test_events_done_links_only_this_run(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    old_call = [{'id': 'c0', 'type': 'function', 'function': {'name': 'terminal', 'arguments': json.dumps(
        {'command': 'curl -s -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/crops/999'})}}]
    new_call = [{'id': 'c1', 'type': 'function', 'function': {'name': 'terminal', 'arguments': json.dumps(
        {'command': f'curl -s -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/plantings/{planting_id}'})}}]
    fake_open.stream(_sse({'event': 'run.completed', 'output': 'ok'}))
    fake_open.reply(200, {'object': 'list', 'data': [
        {'id': 1, 'role': 'user', 'content': '前の質問'},
        {'id': 2, 'role': 'assistant', 'content': '', 'tool_calls': old_call},
        {'id': 3, 'role': 'tool', 'content': '{}', 'tool_call_id': 'c0'},
        {'id': 4, 'role': 'user', 'content': '質問'},
        {'id': 5, 'role': 'assistant', 'content': '', 'tool_calls': new_call},
        {'id': 6, 'role': 'tool', 'content': '{}', 'tool_call_id': 'c1'},
        {'id': 7, 'role': 'assistant', 'content': 'ok'},
    ]})
    done = _events(client.get('/hermes/ask/runs/run_1/events'))[-1]
    assert done['type'] == 'done'
    assert [(l['url'], l['kind_label']) for l in done['links']] == [(f'/plantings/{planting_id}', '見た')]
    assert set(done['links'][0]) == {'label', 'url', 'kind_label'}


def test_events_approval_and_failed(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.stream(_sse(
        {'event': 'approval.request', 'command': 'rm -rf /tmp/x', 'description': 'd',
         'request_id': 'req_1', 'choices': ['once', 'session', 'always', 'deny']},
        {'event': 'approval.responded', 'choice': 'deny', 'request_id': 'req_1',
         'resolved': 1, 'extra': 'SECRET123'},
        {'event': 'run.failed', 'error': 'SECRET123'},
    ))
    events = _events(client.get('/hermes/ask/runs/run_1/events'))
    assert events == [
        {'type': 'approval', 'request_id': 'req_1', 'command': 'rm -rf /tmp/x'},
        {'type': 'approval_done', 'request_id': 'req_1', 'choice': 'deny'},
        {'type': 'failed', 'error': '答えを受け取れませんでした（failed）'},
    ]


def test_events_approval_done_drops_raw_fields(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.stream(_sse(
        {'event': 'approval.responded', 'choice': 'SECRET123', 'request_id': {'x': 'SECRET123'},
         'resolved': 'SECRET123'},
        {'event': 'approval.responded', 'choice': 'once'},
        {'event': 'run.failed'},
    ))
    resp = client.get('/hermes/ask/runs/run_1/events')
    assert 'SECRET123' not in resp.get_data(as_text=True)
    assert _events(resp)[:2] == [
        {'type': 'approval_done', 'request_id': None, 'choice': None},
        {'type': 'approval_done', 'request_id': None, 'choice': 'once'},
    ]


def test_events_relay_keepalive_as_comment(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    lines = _sse({'event': 'tool.started', 'tool': 'terminal'})
    lines += [b': keepalive\n', b'\n']
    lines += _sse({'event': 'message.delta', 'delta': 'あ'})
    lines += _sse({'event': 'run.completed', 'output': 'あ'})
    fake_open.stream(lines)
    fake_open.reply(200, {'object': 'list', 'data': []})
    text = client.get('/hermes/ask/runs/run_1/events').get_data(as_text=True)
    # _sse() が先頭に付ける keepalive（3回）と途中の keepalive が、それぞれコメント行として流れる
    assert text.count(': keepalive\n\n') == 4
    assert text.startswith(': keepalive\n\n')
    assert '_keepalive' not in text
    assert [e['type'] for e in _events_text(text)] == ['tool', 'delta', 'done']


def test_events_completed_does_not_rewind_last_run(client, app, fake_open, planting_id,
                                                   monkeypatch):
    from app.models.hermes_chat import HermesChat
    from app.utils import hermes_client
    session_id = _start(client, fake_open, planting_id, run_id='run_1', key='k1')

    def fake_iter_events(run_id):
        # run_1 の答えを待っている間に、別のタブなどから2つ目の run が始まった
        yield {'event': 'message.delta', 'delta': 'a'}
        HermesChat.set_last_run(session_id, 'run_2')
        yield {'event': 'run.completed', 'output': 'ok'}
    monkeypatch.setattr(hermes_client, 'iter_events', fake_iter_events)
    fake_open.reply(200, {'object': 'list', 'data': []})
    assert _events(client.get('/hermes/ask/runs/run_1/events'))[-1]['type'] == 'done'
    with app.app_context():
        assert HermesChat.find_by_run_id('run_2') is not None
        assert HermesChat.find_by_run_id('run_1') is None


def test_events_done_even_if_links_crash(client, fake_open, planting_id, monkeypatch):
    from app.routes import hermes_ask_routes

    def boom(messages):
        raise RuntimeError('SECRET123')
    monkeypatch.setattr(hermes_ask_routes, 'links_for_messages', boom)
    _start(client, fake_open, planting_id)
    fake_open.stream(_sse({'event': 'run.completed', 'output': '答え'}))
    fake_open.reply(200, {'object': 'list', 'data': [{'id': 1, 'role': 'user', 'content': '質問'}]})
    events = _events(client.get('/hermes/ask/runs/run_1/events'))
    assert events[-1]['type'] == 'done' and events[-1]['links'] == []


def test_events_connection_lost(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.raise_(urllib.error.URLError('refused'))
    events = _events(client.get('/hermes/ask/runs/run_1/events'))
    assert events == [{'type': 'failed', 'error': 'Hermes との接続が切れました'}]


def test_events_stream_ends_without_terminal(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.stream(_sse({'event': 'message.delta', 'delta': 'a'}))
    events = _events(client.get('/hermes/ask/runs/run_1/events'))
    assert events[-1] == {'type': 'failed', 'error': 'Hermes との接続が切れました'}


def test_run_status(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.reply(200, {'run_id': 'run_1', 'status': 'waiting_for_approval'})
    assert client.get('/hermes/ask/runs/run_1').json == {'ok': True, 'status': 'waiting_for_approval'}


def test_approval_sends_choice(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    fake_open.reply(200, {'ok': True})
    resp = client.post('/hermes/ask/runs/run_1/approval', json={'choice': 'once', 'request_id': 'req_1'})
    assert resp.json == {'ok': True}
    assert json.loads(fake_open.calls[-1].data) == {'choice': 'once', 'request_id': 'req_1'}


def test_approval_rejects_always(client, fake_open, planting_id):
    _start(client, fake_open, planting_id)
    n = len(fake_open.calls)
    assert client.post('/hermes/ask/runs/run_1/approval', json={'choice': 'always'}).status_code == 400
    assert client.post('/hermes/ask/runs/run_1/approval', json={'choice': 'session'}).status_code == 400
    assert len(fake_open.calls) == n


def test_run_id_not_ours_404(client, fake_open):
    assert client.get('/hermes/ask/runs/run_someone_else').status_code == 404
    assert client.get('/hermes/ask/runs/run_someone_else/events').status_code == 404
    assert client.post('/hermes/ask/runs/run_someone_else/approval',
                       json={'choice': 'once', 'request_id': 'r'}).status_code == 404
    assert fake_open.calls == []


def test_new_chat_changes_session(client, fake_open, planting_id):
    first = _start(client, fake_open, planting_id, run_id='run_1', key='k1')
    assert client.post(f'/hermes/ask/planting/{planting_id}/new').json == {'ok': True}
    second = _start(client, fake_open, planting_id, run_id='run_2', key='k2')
    assert first != second
    assert second.startswith(f'garden-planting-{planting_id}-')


# --- チャット画面用（会話の行の id で扱うルート） ---

def _chat_count(app):
    from app.database import get_db
    with app.app_context():
        return get_db().execute('SELECT COUNT(*) FROM hermes_chats').fetchone()[0]


def test_chat_create_starts_free_run(client, fake_open):
    fake_open.reply(202, {'run_id': 'run_1'})
    r = client.post('/hermes/ask/chats/runs', json={'text': '来年オクラを作りたい', 'request_key': 'k'})
    assert r.json['ok'] and r.json['run_id'] == 'run_1' and r.json['title'] == '来年オクラを作りたい'
    assert r.json['chat_url'] == f"/hermes/chat/{r.json['chat_id']}"
    body = json.loads(fake_open.calls[0].data)
    assert body['session_id'].startswith('garden-free-') and 'チャット画面' in body['instructions']


def test_chat_create_hermes_down_leaves_no_chat(client, app, fake_open):
    fake_open.raise_(urllib.error.URLError('down'))
    r = client.post('/hermes/ask/chats/runs', json={'text': 'q', 'request_key': 'k'})
    assert r.status_code == 503
    assert _chat_count(app) == 0


def test_chat_create_rejects_empty_text_without_creating(client, app, fake_open):
    r = client.post('/hermes/ask/chats/runs', json={'text': ' ', 'request_key': 'k'})
    assert r.status_code == 400
    assert _chat_count(app) == 0 and fake_open.calls == []


def test_chat_runs_continue_panel_chat_with_target(client, app, fake_open, planting_id):
    session_id = _start(client, fake_open, planting_id)
    from app.models.hermes_chat import HermesChat
    with app.app_context():
        chat = HermesChat.get_active('planting', planting_id)
    fake_open.reply(202, {'run_id': 'run_2'})
    r = client.post(f"/hermes/ask/chats/{chat['id']}/runs", json={'text': '続き', 'request_key': 'k2'})
    assert r.json == {'ok': True, 'run_id': 'run_2'}
    body = json.loads(fake_open.calls[-1].data)
    assert body['session_id'] == session_id
    assert f'GET /plantings/{planting_id}' in body['instructions']
    with app.app_context():
        assert HermesChat.get_by_id(chat['id'])['title'] == '続き'


def test_chat_runs_for_deleted_target_uses_free_instructions(client, app, fake_open, crop_id):
    from app.models.crop import Crop
    from app.models.hermes_chat import HermesChat
    from app.utils.hermes_context import _INSTRUCTIONS_CHAT
    fake_open.reply(202, {'run_id': 'run_1'})
    client.post(f'/hermes/ask/crop/{crop_id}/runs', json={'text': 'q', 'request_key': 'k'})
    with app.app_context():
        chat = HermesChat.get_active('crop', crop_id)
        Crop.delete(crop_id)
    fake_open.reply(202, {'run_id': 'run_2'})
    r = client.post(f"/hermes/ask/chats/{chat['id']}/runs", json={'text': 'q2', 'request_key': 'k2'})
    assert r.status_code == 200
    assert json.loads(fake_open.calls[-1].data)['instructions'] == _INSTRUCTIONS_CHAT


def test_chat_history_free_and_unknown(client, app, fake_open):
    from app.models.hermes_chat import HermesChat
    with app.app_context():
        chat = HermesChat.create_free('題')
    fake_open.reply(200, {'object': 'list', 'data': []})
    r = client.get(f"/hermes/ask/chats/{chat['id']}/history")
    assert r.status_code == 200 and r.json['target'] is None and r.json['messages'] == []
    n = len(fake_open.calls)
    assert client.get('/hermes/ask/chats/9999/history').status_code == 404
    assert client.post('/hermes/ask/chats/9999/runs', json={'text': 'q', 'request_key': 'k'}).status_code == 404
    assert len(fake_open.calls) == n


def test_chat_history_deleted_target(client, app, fake_open, crop_id):
    from app.models.crop import Crop
    from app.models.hermes_chat import HermesChat
    with app.app_context():
        chat = HermesChat.get_or_create_active('crop', crop_id)
        Crop.delete(crop_id)
    fake_open.reply(200, {'object': 'list', 'data': []})
    r = client.get(f"/hermes/ask/chats/{chat['id']}/history")
    assert r.json['target'] == {'kind_label': None, 'label': '（削除済み）'}


def test_events_after_delete_is_404(client, app, fake_open):
    from app.models.hermes_chat import HermesChat
    fake_open.reply(202, {'run_id': 'run_1'})
    r = client.post('/hermes/ask/chats/runs', json={'text': 'q', 'request_key': 'k'})
    with app.app_context():
        HermesChat.delete(r.json['chat_id'])
    assert client.get('/hermes/ask/runs/run_1/events').status_code == 404
    assert client.post('/hermes/ask/runs/run_1/approval', json={'choice': 'once'}).status_code == 404


def test_anonymous_rejected_for_chat_routes(anon_client, fake_open):
    for method, path in [('post', '/hermes/ask/chats/runs'),
                         ('post', '/hermes/ask/chats/1/runs'),
                         ('get', '/hermes/ask/chats/1/history')]:
        resp = getattr(anon_client, method)(path, json={}, headers={'Accept': 'application/json'})
        assert resp.status_code in (400, 401, 302), path
    assert fake_open.calls == []
