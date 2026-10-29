"""Hermes に聞くパネルの中継（/hermes/ask）

ブラウザ ⇔ アプリ ⇔ Hermes の API Server。ブラウザは Hermes に直接つながず、
キーも見ない。Hermes の event は言い換えたものだけを流す（tool の preview などは流さない）。
すべてログイン必須（POST は app/auth.py の既定の拒否、GET は OWNER_ONLY_GET_ENDPOINTS）。
"""
import json

from flask import Blueprint, Response, abort, jsonify, request, stream_with_context

from app.models.hermes_chat import ENTITY_TYPES, HermesChat
from app.routes.conversation_routes import link_items
from app.utils import hermes_client
from app.utils.hermes_client import HermesError, HermesUnavailable
from app.utils.hermes_context import (
    build_instructions, describe_target, friendly_tool_label, links_for_messages,
)
from app.utils.markdown_render import render_markdown

bp = Blueprint('hermes_ask', __name__, url_prefix='/hermes/ask')

MAX_TEXT_LENGTH = 4000
RUNNING_STATUSES = ('queued', 'running', 'waiting_for_approval')
FAILED_EVENTS = ('run.failed', 'run.cancelled', 'run.interrupted')

NOT_CONFIGURED_MESSAGE = 'Hermes への接続が設定されていません'
UNAVAILABLE_MESSAGE = 'Hermes に届きません'
BAD_KEY_MESSAGE = 'Hermes のキーが合いません'
ERROR_MESSAGE = 'Hermes でエラーが起きました'
CONNECTION_LOST_MESSAGE = 'Hermes との接続が切れました'


def _error(message, status):
    return jsonify({'ok': False, 'error': message}), status


@bp.errorhandler(404)
def _not_found(e):
    return _error('見つかりません', 404)


def _hermes_error(e):
    if isinstance(e, HermesUnavailable):
        return _error(UNAVAILABLE_MESSAGE, 503)
    if e.status == 401:
        return _error(BAD_KEY_MESSAGE, 503)
    return _error(ERROR_MESSAGE, 502)


def _target_or_404(entity_type, entity_id):
    if entity_type not in ENTITY_TYPES:
        abort(404)
    target = describe_target(entity_type, entity_id)
    if target is None:
        abort(404)
    return target


def _chat_for_run_or_404(run_id):
    chat = HermesChat.find_by_run_id(run_id)
    if chat is None:
        abort(404)
    return chat


def _this_run_messages(messages):
    """最後の user の発言から後（今回の run の分）"""
    last_user = None
    for i, m in enumerate(messages):
        if m.get('role') == 'user':
            last_user = i
    return messages[last_user:] if last_user is not None else messages


def _links(session_id):
    messages = hermes_client.get_session_messages(session_id)
    items = link_items(links_for_messages(_this_run_messages(messages)))
    return [{'label': i['label'], 'url': i['url'], 'kind_label': i['kind_label']}
            for i in items if i.get('url')]


@bp.route('/<entity_type>/<int:entity_id>/history')
def history(entity_type, entity_id):
    """パネルを開いたときの、今の会話の発言と実行中の run"""
    target = _target_or_404(entity_type, entity_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    chat = HermesChat.get_active(entity_type, entity_id)
    messages = []
    running_run_id = None
    if chat:
        try:
            raw = hermes_client.get_session_messages(chat['session_id'])
        except HermesError as e:
            return _hermes_error(e)
        for m in raw:
            role, content = m.get('role'), m.get('content')
            if role not in ('user', 'assistant') or not isinstance(content, str) or not content.strip():
                continue
            messages.append({
                'role': role, 'text': content,
                'html': str(render_markdown(content)) if role == 'assistant' else None,
                'timestamp': m.get('timestamp'),
            })
        if chat.get('last_run_id'):
            try:
                status = hermes_client.get_run(chat['last_run_id']).get('status')
            except HermesError:
                status = None
            if status in RUNNING_STATUSES:
                running_run_id = chat['last_run_id']
    return jsonify({
        'ok': True,
        'target': {'kind_label': target['kind_label'], 'label': target['label']},
        'messages': messages,
        'running_run_id': running_run_id,
    })


@bp.route('/<entity_type>/<int:entity_id>/runs', methods=['POST'])
def start(entity_type, entity_id):
    """質問を Hermes に送り、run を始める"""
    target = _target_or_404(entity_type, entity_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    data = request.get_json(silent=True) or {}
    text = data.get('text')
    if not isinstance(text, str) or not text.strip():
        return _error('質問を入力してください', 400)
    if len(text) > MAX_TEXT_LENGTH:
        return _error(f'質問は {MAX_TEXT_LENGTH} 文字以内にしてください', 400)
    request_key = str(data.get('request_key') or '')
    if not request_key:
        return _error('request_key がありません', 400)

    chat = HermesChat.get_or_create_active(entity_type, entity_id)
    session_id = chat['session_id']
    try:
        run_id = hermes_client.start_run(session_id, text, build_instructions(target),
                                         f'{session_id}:{request_key}')
    except HermesError as e:
        return _hermes_error(e)
    HermesChat.set_last_run(session_id, run_id)
    return jsonify({'ok': True, 'run_id': run_id})


@bp.route('/<entity_type>/<int:entity_id>/new', methods=['POST'])
def new_chat(entity_type, entity_id):
    """新しい会話にする（古い会話は Hermes 側にも表にも残る）"""
    _target_or_404(entity_type, entity_id)
    HermesChat.start_new(entity_type, entity_id)
    return jsonify({'ok': True})


def _sse(payload):
    return 'data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n'


@bp.route('/runs/<run_id>/events')
def events(run_id):
    """Hermes の event を言い換えて text/event-stream で流す"""
    chat = _chat_for_run_or_404(run_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    session_id = chat['session_id']

    def generate():
        try:
            for e in hermes_client.iter_events(run_id):
                name = e.get('event')
                if name == 'tool.started':
                    yield _sse({'type': 'tool', 'label': friendly_tool_label(e)})
                elif name == 'message.delta':
                    delta = e.get('delta')
                    if isinstance(delta, str) and delta:
                        yield _sse({'type': 'delta', 'text': delta})
                elif name == 'approval.request':
                    yield _sse({'type': 'approval', 'request_id': e.get('request_id'),
                                'command': e.get('command')})
                elif name == 'run.completed':
                    output = e.get('output')
                    try:
                        links = _links(session_id)
                    except HermesError:
                        links = []
                    HermesChat.set_last_run(session_id, run_id)
                    yield _sse({'type': 'done',
                                'html': str(render_markdown(output if isinstance(output, str) else '')),
                                'links': links})
                    return
                elif name in FAILED_EVENTS:
                    state = name.split('.', 1)[1]
                    yield _sse({'type': 'failed', 'error': f'答えを受け取れませんでした（{state}）'})
                    return
        except HermesUnavailable:
            pass
        except HermesError:
            yield _sse({'type': 'failed', 'error': ERROR_MESSAGE})
            return
        # 接続できない・途中で切れた・終わりの event が来ないまま閉じた
        yield _sse({'type': 'failed', 'error': CONNECTION_LOST_MESSAGE})

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@bp.route('/runs/<run_id>')
def run_status(run_id):
    """run の状態（queued / running / waiting_for_approval / completed / failed など）"""
    _chat_for_run_or_404(run_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    try:
        status = hermes_client.get_run(run_id).get('status')
    except HermesError as e:
        return _hermes_error(e)
    return jsonify({'ok': True, 'status': status})


@bp.route('/runs/<run_id>/approval', methods=['POST'])
def approval(run_id):
    """承認の答え（once / deny だけ）を Hermes に返す"""
    _chat_for_run_or_404(run_id)
    data = request.get_json(silent=True) or {}
    choice = data.get('choice')
    if choice not in hermes_client.APPROVAL_CHOICES:
        return _error('choice は once か deny です', 400)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    request_id = data.get('request_id')
    try:
        hermes_client.send_approval(run_id, choice,
                                    request_id if isinstance(request_id, str) else None)
    except HermesError as e:
        return _hermes_error(e)
    return jsonify({'ok': True})
