import json
import urllib.error

import pytest

from app.utils import hermes_client
from app.utils.hermes_client import HermesError, HermesUnavailable
from tests.hermes_fakes import fake_open, planting_id, crop_id, variety_id  # noqa: F401


def test_start_run_sends_body_and_headers(app, fake_open):
    fake_open.reply(202, {'run_id': 'run_x', 'status': 'started'})
    with app.app_context():
        assert hermes_client.start_run('garden-planting-1-ab', '質問', '指示', 'idem-1') == 'run_x'
    req = fake_open.calls[0]
    assert req.full_url == 'http://127.0.0.1:8642/v1/runs'
    assert req.get_method() == 'POST'
    assert req.get_header('Authorization') == 'Bearer test-hermes-key'
    assert req.get_header('Idempotency-key') == 'idem-1'
    assert req.get_header('Content-type') == 'application/json'
    body = json.loads(req.data.decode('utf-8'))
    assert body == {'input': '質問', 'instructions': '指示', 'session_id': 'garden-planting-1-ab'}
    assert fake_open.timeouts[0] == 15


def test_connection_error_is_unavailable(app, fake_open):
    fake_open.raise_(urllib.error.URLError('refused'))
    with app.app_context(), pytest.raises(HermesUnavailable):
        hermes_client.get_run('run_x')


def test_timeout_is_unavailable(app, fake_open):
    fake_open.raise_(TimeoutError())
    with app.app_context(), pytest.raises(HermesUnavailable):
        hermes_client.get_run('run_x')


def test_http_error_carries_status(app, fake_open):
    fake_open.reply(401, {'error': {'message': 'bad key'}})
    with app.app_context(), pytest.raises(HermesError) as e:
        hermes_client.get_run('run_x')
    assert e.value.status == 401
    assert 'bad key' in e.value.message
    assert not isinstance(e.value, HermesUnavailable)


def test_get_run_returns_json(app, fake_open):
    fake_open.reply(200, {'run_id': 'run_x', 'status': 'running'})
    with app.app_context():
        assert hermes_client.get_run('run_x')['status'] == 'running'
    assert fake_open.calls[0].full_url == 'http://127.0.0.1:8642/v1/runs/run_x'
    assert fake_open.calls[0].get_method() == 'GET'


def test_iter_events_skips_keepalive_and_stops_at_terminal(app, fake_open):
    fake_open.stream([b': keepalive\n', b'\n',
                      b'data: {"event": "tool.started", "tool": "terminal"}\n', b'\n',
                      b'data: {"event": "run.completed", "output": "done"}\n', b'\n',
                      b'data: {"event": "never"}\n'])
    with app.app_context():
        events = list(hermes_client.iter_events('run_x'))
    assert [e['event'] for e in events] == ['tool.started', 'run.completed']
    assert fake_open.calls[0].full_url == 'http://127.0.0.1:8642/v1/runs/run_x/events'
    assert fake_open.timeouts[0] == 330


@pytest.mark.parametrize('terminal', ['run.failed', 'run.cancelled', 'run.interrupted'])
def test_iter_events_stops_at_other_terminals(app, fake_open, terminal):
    fake_open.stream([('data: {"event": "%s"}\n' % terminal).encode(),
                      b'data: {"event": "never"}\n'])
    with app.app_context():
        assert [e['event'] for e in hermes_client.iter_events('r')] == [terminal]


def test_iter_events_connection_error(app, fake_open):
    fake_open.raise_(urllib.error.URLError('refused'))
    with app.app_context(), pytest.raises(HermesUnavailable):
        list(hermes_client.iter_events('run_x'))


def test_send_approval_posts(app, fake_open):
    fake_open.reply(200, {'ok': True})
    with app.app_context():
        assert hermes_client.send_approval('run_x', 'once', 'req1') == {'ok': True}
    req = fake_open.calls[0]
    assert req.full_url == 'http://127.0.0.1:8642/v1/runs/run_x/approval'
    assert json.loads(req.data.decode('utf-8')) == {'choice': 'once', 'request_id': 'req1'}


def test_send_approval_rejects_session_and_always(app):
    with app.app_context(), pytest.raises(ValueError):
        hermes_client.send_approval('run_x', 'always', None)
    with app.app_context(), pytest.raises(ValueError):
        hermes_client.send_approval('run_x', 'session', None)


def test_get_session_messages(app, fake_open):
    fake_open.reply(200, {'object': 'list', 'data': [{'role': 'user', 'content': 'hi'}]})
    with app.app_context():
        msgs = hermes_client.get_session_messages('garden-x')
    assert msgs == [{'role': 'user', 'content': 'hi'}]
    assert fake_open.calls[0].full_url == (
        'http://127.0.0.1:8642/api/sessions/garden-x/messages?inline_images=false')


def test_get_session_messages_404_is_empty(app, fake_open):
    fake_open.reply(404, {'error': {'message': 'not found'}})
    with app.app_context():
        assert hermes_client.get_session_messages('garden-x') == []


def test_is_configured(app):
    with app.app_context():
        app.config['HERMES_API_KEY'] = ''
        assert hermes_client.is_configured() is False
        app.config['HERMES_API_KEY'] = 'k'
        assert hermes_client.is_configured() is True
