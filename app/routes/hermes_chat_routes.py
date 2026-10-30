"""Hermes とのチャット画面（/hermes/chat）

左に会話の一覧（対象なしの会話とパネルの会話）、右に選んだ会話の吹き出しと入力欄。
送る・履歴は hermes-ask.js が /hermes/ask/chats/... に話す（このファイルは画面と題名変更・削除だけ）。
すべてログイン必須（GET は OWNER_ONLY_GET_ENDPOINTS、POST は app/auth.py の既定の拒否）。
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from app.models.hermes_chat import HermesChat
from app.utils.hermes_context import describe_target
from app.utils.upload import delete_image

bp = Blueprint('hermes_chat', __name__, url_prefix='/hermes/chat')

MAX_TITLE_LENGTH = 200
DELETED_TARGET_LABEL = '（削除済み）'


def _time_label(value):
    """last_used_at（'YYYY-MM-DD HH:MM:SS'）を MM/DD HH:MM にする"""
    s = str(value or '')
    if len(s) < 16:
        return s
    return f'{s[5:7]}/{s[8:10]} {s[11:16]}'


def _target_label(chat):
    """パネルの会話の対象の印（「植え付け: …」）。対象なしは None、消えていれば（削除済み）"""
    if not chat['entity_type']:
        return None
    target = describe_target(chat['entity_type'], chat['entity_id'])
    if target is None:
        return DELETED_TARGET_LABEL
    return f"{target['kind_label']}: {target['label']}"


def _chats():
    chats = HermesChat.list_for_chat()
    for c in chats:
        c['time_label'] = _time_label(c['last_used_at'])
        c['target_label'] = _target_label(c)
    return chats


def _chat_or_404(chat_id):
    chat = HermesChat.get_by_id(chat_id)
    if chat is None:
        abort(404)
    return chat


@bp.route('/')
def index():
    """新しい会話（右は空の吹き出しと入力欄）"""
    return render_template('hermes_chat/index.html', chats=_chats(), chat=None)


@bp.route('/<int:chat_id>')
def show(chat_id):
    """既にある会話の続き"""
    _chat_or_404(chat_id)
    chats = _chats()
    chat = next(c for c in chats if c['id'] == chat_id)
    return render_template('hermes_chat/index.html', chats=chats, chat=chat)


@bp.route('/<int:chat_id>/rename', methods=['POST'])
def rename(chat_id):
    """題名を変える（会話の履歴の題名も揃える）"""
    _chat_or_404(chat_id)
    title = ' '.join((request.form.get('title') or '').split())
    if not title:
        flash('題名を入力してください', 'danger')
    elif len(title) > MAX_TITLE_LENGTH:
        flash(f'題名は {MAX_TITLE_LENGTH} 文字以内にしてください', 'danger')
    else:
        HermesChat.rename(chat_id, title)
        flash('題名を変えました', 'success')
    return redirect(url_for('hermes_chat.show', chat_id=chat_id))


@bp.route('/<int:chat_id>/delete', methods=['POST'])
def delete(chat_id):
    """会話を消す（会話の履歴・写真も。Hermes の中の記録とアドバイスは残る）"""
    paths = HermesChat.delete(chat_id)
    if paths is None:
        abort(404)
    for path in paths:
        # 会話は消し終えている（コミット済み）ので、写真が消せなくても成功として扱う
        try:
            delete_image(path)
        except OSError:
            current_app.logger.warning('会話の写真を消せませんでした: %s', path, exc_info=True)
    flash('会話を削除しました', 'success')
    return redirect(url_for('hermes_chat.index'))
