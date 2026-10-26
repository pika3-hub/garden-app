"""会話の履歴 API（POST /api/v1/conversations）

Hermes の会話を同期スクリプトが送ってくる専用の入口。何度送っても結果が同じになる
（会話は hermes_id、発言は hermes_message_id で上書き。送られなかった発言は消さない）。
削除はできない。写真は縮小版（サムネイルサイズの JPEG）だけを保存する。
"""
import json
import math
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

from flask import current_app, g
from PIL import Image

from app.api import bp
from app.api.errors import ApiError, detail, ok, validation_error
from app.api.images import MAX_FILES_PER_REQUEST, check_image
from app.api.payload import parse_request
from app.api.validation import SQLITE_MAX_INT
from app.models.conversation import Conversation
from app.utils.upload import THUMBNAIL_SIZE, _save_heif_as_jpeg, is_heif, make_thumbnail

MAX_MESSAGES = 5000
_SESSION_KEYS = ('id', 'source', 'title', 'started_at', 'ended_at', 'last_activity_at',
                 'end_reason', 'parent_session_id')
_MESSAGE_KEYS = ('id', 'role', 'content', 'tool_calls', 'tool_call_id', 'tool_name',
                 'timestamp', 'display_kind')
_ROLES = ('user', 'assistant', 'tool')
_ID_RE = re.compile(r'[A-Za-z0-9_.-]{1,128}')
_FILE_NAME_RE = re.compile(r'[A-Za-z0-9_.-]{1,100}')
_JST = timezone(timedelta(hours=9))


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _jst(ts):
    """UNIX 秒 → 日本時間の 'YYYY-MM-DD HH:MM:SS'。範囲外は None"""
    try:
        return datetime.fromtimestamp(ts, _JST).strftime('%Y-%m-%d %H:%M:%S')
    except (OverflowError, OSError, ValueError):
        return None


def _echo(v):
    return v if isinstance(v, (int, str)) and not isinstance(v, bool) else None


def _check_time(obj, key, where, errors, required=False):
    v = obj.get(key)
    if v is None:
        if required:
            errors.append(detail(f'{where}.{key}', '必須です（UNIX 秒の数値）'))
        return None
    if not _is_number(v):
        errors.append(detail(f'{where}.{key}', 'UNIX 秒の数値か null で指定してください', _echo(v)))
        return None
    s = _jst(v)
    if s is None:
        errors.append(detail(f'{where}.{key}', '時刻の範囲外です', v))
    return s


def _check_str_or_null(obj, key, where, errors):
    v = obj.get(key)
    if v is not None and not isinstance(v, str):
        errors.append(detail(f'{where}.{key}', '文字列か null で指定してください'))
        return None
    return v


def _validate_session(session, errors):
    if not isinstance(session, dict):
        errors.append(detail('session', 'オブジェクトで指定してください'))
        return None
    for k in session:
        if k not in _SESSION_KEYS:
            errors.append(detail(f'session.{k}', f'未知の項目です。使える項目: {", ".join(_SESSION_KEYS)}'))
    sid = session.get('id')
    if not isinstance(sid, str) or not _ID_RE.fullmatch(sid):
        errors.append(detail('session.id', '必須です（英数字と _ . - の128文字まで）', _echo(sid)))
    if not isinstance(session.get('source'), str):
        errors.append(detail('session.source', '必須の文字列です'))
    return {
        'hermes_id': sid,
        'source': session.get('source'),
        'title': _check_str_or_null(session, 'title', 'session', errors),
        'started_at': _check_time(session, 'started_at', 'session', errors, required=True),
        'ended_at': _check_time(session, 'ended_at', 'session', errors),
        'last_activity_at': _check_time(session, 'last_activity_at', 'session', errors),
        'end_reason': _check_str_or_null(session, 'end_reason', 'session', errors),
        'parent_hermes_id': _check_str_or_null(session, 'parent_session_id', 'session', errors),
    }


def _validate_message(m, i, errors):
    where = f'messages[{i}]'
    if not isinstance(m, dict):
        errors.append(detail(where, 'オブジェクトで指定してください'))
        return None
    for k in m:
        if k not in _MESSAGE_KEYS:
            errors.append(detail(f'{where}.{k}', f'未知の項目です。使える項目: {", ".join(_MESSAGE_KEYS)}'))
    mid = m.get('id')
    if not isinstance(mid, int) or isinstance(mid, bool) or not 1 <= mid <= SQLITE_MAX_INT:
        errors.append(detail(f'{where}.id', f'必須の整数です（1〜{SQLITE_MAX_INT}）', _echo(mid)))
    if m.get('role') not in _ROLES:
        errors.append(detail(f'{where}.role', f'{" / ".join(_ROLES)} のどれかで指定してください',
                             _echo(m.get('role'))))
    ts = None
    if not _is_number(m.get('timestamp')):
        errors.append(detail(f'{where}.timestamp', '必須です（UNIX 秒の数値）'))
    else:
        ts = _jst(m['timestamp'])
        if ts is None:
            errors.append(detail(f'{where}.timestamp', '時刻の範囲外です', m['timestamp']))
    tool_calls = m.get('tool_calls')
    if tool_calls is not None and not isinstance(tool_calls, list):
        errors.append(detail(f'{where}.tool_calls', '配列か null で指定してください'))
        tool_calls = None
    return {
        'hermes_message_id': mid,
        'role': m.get('role'),
        'content': _check_str_or_null(m, 'content', where, errors),
        'tool_calls': json.dumps(tool_calls, ensure_ascii=False) if tool_calls is not None else None,
        'tool_call_id': _check_str_or_null(m, 'tool_call_id', where, errors),
        'tool_name': _check_str_or_null(m, 'tool_name', where, errors),
        'display_kind': _check_str_or_null(m, 'display_kind', where, errors),
        'timestamp': ts,
    }


def _save_thumbnail_only(file, ext):
    """写真を一時ファイルに保存し、縮小版だけを uploads/conversations/ に作る。相対パスを返す"""
    rel = f'conversations/{uuid.uuid4().hex}.jpg'
    dest = os.path.join(current_app.config['UPLOAD_FOLDER'], rel)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, f'src.{ext}')
        file.stream.seek(0)
        if is_heif(file.stream):
            _save_heif_as_jpeg(file.stream, src)
        else:
            file.save(src)
        try:
            if not make_thumbnail(src, dest):  # GIF は最初のコマだけ縮小版にする
                with Image.open(src) as img:
                    img.seek(0)
                    img = img.convert('RGB')
                    img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    img.save(dest, format='JPEG', quality=85)
        except Exception:
            if os.path.exists(dest):
                os.remove(dest)
            raise
    return rel


def _store_images(conversation_id, uploads):
    """写真を保存し、読めなかったファイル名を返す（読めない写真で同期を止めない）"""
    skipped = []
    seen = set()
    for f in uploads:
        name = f.filename
        if name in seen or Conversation.has_image(conversation_id, name):
            continue
        seen.add(name)
        try:
            checked = check_image(f, 'images')
            rel = _save_thumbnail_only(f, checked.ext)
        except ApiError as e:
            if e.status not in (413, 415):
                raise
            skipped.append(name)
            continue
        except Exception:
            skipped.append(name)
            continue
        Conversation.add_image(conversation_id, name, rel)
    return skipped


@bp.post('/conversations')
def upload_conversation():
    payload, files = parse_request(('images',))
    errors = [detail(k, '未知の項目です。使える項目: session, messages')
              for k in payload if k not in ('session', 'messages')]
    session = None
    if 'session' in payload:
        session = _validate_session(payload['session'], errors)
    else:
        errors.append(detail('session', '必須です'))
    messages = []
    raw_messages = payload.get('messages')
    if 'messages' not in payload:
        errors.append(detail('messages', '必須です'))
    elif not isinstance(raw_messages, list):
        errors.append(detail('messages', '配列で指定してください'))
    elif len(raw_messages) > MAX_MESSAGES:
        errors.append(detail('messages', f'発言は1回のリクエストで{MAX_MESSAGES}件までです（{len(raw_messages)}件）'))
    else:
        for i, m in enumerate(raw_messages):
            parsed = _validate_message(m, i, errors)
            if parsed:
                messages.append(parsed)
    uploads = files['images']
    if len(uploads) > MAX_FILES_PER_REQUEST:
        errors.append(detail('images', f'画像は1回のリクエストで{MAX_FILES_PER_REQUEST}枚までです（{len(uploads)}枚）'))
    for f in uploads:
        if not _FILE_NAME_RE.fullmatch(f.filename):
            errors.append(detail('images', 'ファイル名は英数字と _ . - の100文字までです', f.filename))
    if errors:
        raise validation_error(errors)

    conversation_id, created = Conversation.upsert(session)
    Conversation.upsert_messages(conversation_id, messages)
    skipped = _store_images(conversation_id, uploads)
    Conversation.relink(conversation_id)
    g.api_target_id = conversation_id
    return ok({
        'id': conversation_id,
        'hermes_id': session['hermes_id'],
        'message_count': len(Conversation.get_messages(conversation_id, include_tools=True)),
        'image_count': len(Conversation.get_images(conversation_id)),
        'skipped_images': skipped,
    }, 201 if created else 200)
