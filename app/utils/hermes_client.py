"""Hermes の API Server（OpenAI 互換、既定 127.0.0.1:8642）のクライアント

標準ライブラリ（urllib）だけで書く。API キーはログにも例外メッセージにも出さない。
"""
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

from flask import current_app

REQUEST_TIMEOUT = 15
# keepalive が 10 秒ごとに来るので、これだけ無音なら切れたとみなす
EVENTS_TIMEOUT = 330

TERMINAL_EVENTS = ('run.completed', 'run.failed', 'run.cancelled', 'run.interrupted')
APPROVAL_CHOICES = ('once', 'deny')
# iter_events がコメント行（keepalive）を受けたときに返す event 名（Hermes の event 名とは重ならない）
KEEPALIVE_EVENT = '_keepalive'


class HermesError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.message = message
        self.status = status


class HermesUnavailable(HermesError):
    """接続できない・タイムアウト"""


def is_configured() -> bool:
    return bool(current_app.config.get('HERMES_API_KEY'))


def _open(req, timeout):
    """urllib.request.urlopen を呼ぶだけ（テストで差し替える）"""
    return urllib.request.urlopen(req, timeout=timeout)


def _error_message(e: urllib.error.HTTPError) -> str:
    try:
        data = json.loads(e.read().decode('utf-8'))
        err = data.get('error')
        if isinstance(err, dict) and err.get('message'):
            return str(err['message'])
        if isinstance(err, str):
            return err
    except Exception:
        pass
    return f'HTTP {e.code}'


def _request(method, path, payload=None, headers=None, timeout=REQUEST_TIMEOUT):
    """要求を送って応答（開いたまま）を返す。失敗は HermesError / HermesUnavailable に変える"""
    url = current_app.config['HERMES_API_URL'].rstrip('/') + path
    all_headers = {'Authorization': 'Bearer ' + current_app.config['HERMES_API_KEY']}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        all_headers['Content-Type'] = 'application/json'
    all_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=all_headers, method=method)
    try:
        return _open(req, timeout)
    except urllib.error.HTTPError as e:
        raise HermesError(_error_message(e), status=e.code) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise HermesUnavailable(f'Hermes に接続できません: {type(e).__name__}') from None


def _json(method, path, payload=None, headers=None) -> dict:
    resp = _request(method, path, payload, headers)
    try:
        return json.loads(resp.read().decode('utf-8'))
    except ValueError:
        raise HermesError('Hermes の応答を読めませんでした') from None
    except (TimeoutError, OSError, http.client.HTTPException) as e:
        raise HermesUnavailable(f'Hermes の応答を読み切れませんでした: {type(e).__name__}') from None
    finally:
        resp.close()


def start_run(session_id: str, text: str, instructions: str, idempotency_key: str) -> str:
    data = _json('POST', '/v1/runs',
                 {'input': text, 'instructions': instructions, 'session_id': session_id},
                 {'Idempotency-Key': idempotency_key})
    run_id = data.get('run_id')
    if not run_id:
        raise HermesError('Hermes の応答に run_id がありません')
    return run_id


def get_run(run_id: str) -> dict:
    return _json('GET', f'/v1/runs/{urllib.parse.quote(run_id, safe="")}')


def iter_events(run_id: str) -> Iterator[dict]:
    """SSE の data: 行を JSON にして順に返す。終了イベントを返したら終わる

    コメント行（Hermes の `: keepalive`）は {'event': KEEPALIVE_EVENT} として返す。
    呼び出し側がブラウザへ書き込むことで、ブラウザが去ったのに気づけるようにするため。
    """
    resp = _request('GET', f'/v1/runs/{urllib.parse.quote(run_id, safe="")}/events',
                    headers={'Accept': 'text/event-stream'}, timeout=EVENTS_TIMEOUT)
    try:
        for raw in resp:
            line = raw.decode('utf-8', 'replace').strip()
            if line.startswith(':'):
                yield {'event': KEEPALIVE_EVENT}
                continue
            if not line.startswith('data:'):
                continue
            try:
                event = json.loads(line[5:].strip())
            except ValueError:
                continue
            yield event
            if event.get('event') in TERMINAL_EVENTS:
                return
    except (TimeoutError, OSError, http.client.HTTPException) as e:
        raise HermesUnavailable(f'Hermes との接続が切れました: {type(e).__name__}') from None
    finally:
        resp.close()


def send_approval(run_id: str, choice: str, request_id: str | None) -> dict:
    if choice not in APPROVAL_CHOICES:
        raise ValueError(f'choice は {APPROVAL_CHOICES} のどちらかです')
    payload = {'choice': choice}
    if request_id:
        payload['request_id'] = request_id
    return _json('POST', f'/v1/runs/{urllib.parse.quote(run_id, safe="")}/approval', payload)


def get_session_messages(session_id: str) -> list[dict]:
    try:
        data = _json('GET', f'/api/sessions/{urllib.parse.quote(session_id, safe="")}'
                            '/messages?inline_images=false')
    except HermesError as e:
        if e.status == 404 and not isinstance(e, HermesUnavailable):
            return []
        raise
    return data.get('data') or []
