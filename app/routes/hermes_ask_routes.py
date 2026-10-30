"""Hermes に聞くパネルの中継（/hermes/ask）

ブラウザ ⇔ アプリ ⇔ Hermes の API Server。ブラウザは Hermes に直接つながず、
キーも見ない。Hermes の event は言い換えたものだけを流す（tool の preview などは流さない）。
すべてログイン必須（POST は app/auth.py の既定の拒否、GET は OWNER_ONLY_GET_ENDPOINTS）。
"""
import json

from flask import (
    Blueprint, Response, abort, current_app, jsonify, request, stream_with_context, url_for,
)

from app.models.hermes_chat import ENTITY_TYPES, HermesChat, make_title
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
# approval.responded の choice のうち、ブラウザへそのまま伝えてよい値（Hermes が受け付ける4つ）
APPROVAL_DONE_CHOICES = ('once', 'session', 'always', 'deny')

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


def _turns(messages):
    """発言を「回」ごとに分ける（user の発言から次の user の発言の前まで）。
    最初の user より前の発言は、最初の回に入れる"""
    turns = []
    for m in messages:
        if m.get('role') == 'user' or not turns:
            turns.append([])
        turns[-1].append(m)
    return turns


def _turn_links(turn):
    """1回分の発言（tool の呼び出し・結果を含む）から、作った・変えた・見たデータへのリンク。

    取れなくても答えは出せるので、想定外の例外は [] にする（ログに種類だけ残す。
    キーや本文は出さない）
    """
    try:
        items = link_items(links_for_messages(turn))
        return [{'label': i['label'], 'url': i['url'], 'kind_label': i['kind_label']}
                for i in items if i.get('url')]
    except Exception as e:  # noqa: BLE001 答えを出すことを優先する
        current_app.logger.warning('Hermes のリンクを作れませんでした: %s', type(e).__name__)
        return []


def _links(session_id):
    """今回の run（最後の回）のリンク。Hermes から取れなくても [] にする"""
    try:
        messages = hermes_client.get_session_messages(session_id)
    except HermesError:
        return []
    turns = _turns(messages)
    return _turn_links(turns[-1]) if turns else []


def _is_shown(m):
    content = m.get('content')
    return (m.get('role') in ('user', 'assistant') and isinstance(content, str)
            and bool(content.strip()))


def _history_payload(chat, target):
    """会話の発言と実行中の run を JSON にする。chat は None もある（まだ会話が無いパネル）。
    target は画面に出す対象（{'kind_label', 'label'}）か None"""
    messages = []
    running_run_id = None
    if chat:
        try:
            raw = hermes_client.get_session_messages(chat['session_id'])
        except HermesError as e:
            return _hermes_error(e)
        for turn in _turns(raw):
            shown = [m for m in turn if _is_shown(m)]
            last_bot = max((i for i, m in enumerate(shown) if m['role'] == 'assistant'),
                           default=None)
            for i, m in enumerate(shown):
                is_bot = m['role'] == 'assistant'
                messages.append({
                    'role': m['role'], 'text': m['content'],
                    'html': str(render_markdown(m['content'])) if is_bot else None,
                    'timestamp': m.get('timestamp'),
                    'links': _turn_links(turn) if i == last_bot else [],
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
        'target': target,
        'messages': messages,
        'running_run_id': running_run_id,
    })


def _parse_question():
    """リクエストの質問と request_key を取り出す。(text, request_key, エラーの応答) を返す"""
    data = request.get_json(silent=True) or {}
    text = data.get('text')
    if not isinstance(text, str) or not text.strip():
        return None, None, _error('質問を入力してください', 400)
    if len(text) > MAX_TEXT_LENGTH:
        return None, None, _error(f'質問は {MAX_TEXT_LENGTH} 文字以内にしてください', 400)
    request_key = str(data.get('request_key') or '')
    if not request_key:
        return None, None, _error('request_key がありません', 400)
    return text, request_key, None


def _start_run(chat, target, place, text, request_key):
    """質問を Hermes に送って run を始める。(run_id, エラーの応答) を返す"""
    session_id = chat['session_id']
    try:
        run_id = hermes_client.start_run(session_id, text, build_instructions(target, place),
                                         f'{session_id}:{request_key}')
    except HermesError as e:
        return None, _hermes_error(e)
    HermesChat.set_last_run(session_id, run_id)
    return run_id, None


def _chat_target(chat):
    """会話の行の対象（植え付けなど）。対象なし・消えているときは None"""
    if not chat['entity_type']:
        return None
    return describe_target(chat['entity_type'], chat['entity_id'])


def _chat_or_404(chat_id):
    chat = HermesChat.get_by_id(chat_id)
    if chat is None:
        abort(404)
    return chat


def _chat_url(chat_id):
    return url_for('hermes_chat.show', chat_id=chat_id)


@bp.route('/<entity_type>/<int:entity_id>/history')
def history(entity_type, entity_id):
    """パネルを開いたときの、今の会話の発言と実行中の run"""
    target = _target_or_404(entity_type, entity_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    chat = HermesChat.get_active(entity_type, entity_id)
    return _history_payload(chat, {'kind_label': target['kind_label'], 'label': target['label']})


@bp.route('/<entity_type>/<int:entity_id>/runs', methods=['POST'])
def start(entity_type, entity_id):
    """質問を Hermes に送り、run を始める"""
    target = _target_or_404(entity_type, entity_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    text, request_key, err = _parse_question()
    if err:
        return err
    chat = HermesChat.get_or_create_active(entity_type, entity_id)
    run_id, err = _start_run(chat, target, 'panel', text, request_key)
    if err:
        return err
    HermesChat.set_title_if_empty(chat['id'], make_title(text))
    return jsonify({'ok': True, 'run_id': run_id})


@bp.route('/chats/<int:chat_id>/history')
def chat_history(chat_id):
    """チャット画面で会話を開いたときの、発言と実行中の run（会話の行の id で指す）"""
    chat = _chat_or_404(chat_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    target = None
    if chat['entity_type']:
        found = _chat_target(chat)
        target = ({'kind_label': found['kind_label'], 'label': found['label']} if found
                  else {'kind_label': None, 'label': '（削除済み）'})
    return _history_payload(chat, target)


@bp.route('/chats/<int:chat_id>/runs', methods=['POST'])
def chat_start(chat_id):
    """チャット画面から、既にある会話に質問を送る"""
    chat = _chat_or_404(chat_id)
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    text, request_key, err = _parse_question()
    if err:
        return err
    run_id, err = _start_run(chat, _chat_target(chat), 'chat', text, request_key)
    if err:
        return err
    HermesChat.set_title_if_empty(chat_id, make_title(text))
    return jsonify({'ok': True, 'run_id': run_id})


@bp.route('/chats/runs', methods=['POST'])
def chat_create():
    """チャット画面で新しい会話（対象なし）を作って、最初の質問を送る"""
    if not hermes_client.is_configured():
        return _error(NOT_CONFIGURED_MESSAGE, 503)
    text, request_key, err = _parse_question()
    if err:
        return err
    title = make_title(text)
    chat = HermesChat.create_free(title)
    run_id, err = _start_run(chat, None, 'chat', text, request_key)
    if err:
        # 一覧に残さない。Hermes が受け付けていたかもしれないので、行だけを消す
        # （delete だと削除済みとして覚え、その会話が取り込まれなくなる）
        HermesChat.discard(chat['id'])
        return err
    return jsonify({'ok': True, 'run_id': run_id, 'chat_id': chat['id'],
                    'chat_url': _chat_url(chat['id']), 'title': title})


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
                if name == hermes_client.KEEPALIVE_EVENT:
                    # ブラウザへ書き込む（EventSource はコメント行を無視する）。ブラウザが
                    # 去っていれば書き込みで失敗してジェネレーターが閉じ、Hermes への接続も閉じる
                    yield ': keepalive\n\n'
                elif name == 'tool.started':
                    yield _sse({'type': 'tool', 'label': friendly_tool_label(e)})
                elif name == 'message.delta':
                    delta = e.get('delta')
                    if isinstance(delta, str) and delta:
                        yield _sse({'type': 'delta', 'text': delta})
                elif name == 'approval.request':
                    yield _sse({'type': 'approval', 'request_id': e.get('request_id'),
                                'command': e.get('command')})
                elif name == 'approval.responded':
                    # Hermes はつなぎ直した購読者に、それまでの event を最初から流し直す。
                    # 返事を済ませた承認のボタンを出し直さないよう、済んだことも伝える
                    request_id = e.get('request_id')
                    choice = e.get('choice')
                    yield _sse({'type': 'approval_done',
                                'request_id': request_id if isinstance(request_id, str) else None,
                                'choice': choice if choice in APPROVAL_DONE_CHOICES else None})
                elif name == 'run.completed':
                    output = e.get('output')
                    links = _links(session_id)
                    # last_run_id は変えない（この間に始めた新しい run を古い run に戻さない）
                    HermesChat.touch(session_id)
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
