#!/usr/bin/env python3
"""Hermes の会話（~/.hermes/state.db）をアプリの API（POST /conversations）に送る同期スクリプト。

サーバーで Hermes の実行ユーザーとして、systemd のタイマーから15分おきに動かす。
標準ライブラリだけで動く。接続先とトークンは env ファイル
（GARDEN_API_URL / GARDEN_API_TOKEN）から読む。トークンも発言の本文もログには出さない。
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

DB_TIMEOUT = 10  # state.db を開いて待つ秒数（Hermes が書き込み中でも読めるが、ロック時は待つ）
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif')
MAX_IMAGES_PER_REQUEST = 20  # アプリの MAX_FILES_PER_REQUEST に合わせる
_IMAGE_NAME_RE = re.compile(r'[A-Za-z0-9_.-]{1,100}')
_IMAGE_MARKER_RE = re.compile(r'\[Image attached at: ([^\]\r\n]+)\]')

REQUIRED_COLUMNS = {
    'sessions': {'id', 'source', 'title', 'started_at', 'ended_at', 'last_activity_at',
                 'end_reason', 'parent_session_id'},
    'messages': {'id', 'session_id', 'role', 'content', 'tool_calls', 'tool_call_id',
                 'tool_name', 'timestamp', 'display_kind'},
}


class SchemaError(Exception):
    pass


def open_db(path, timeout=None):
    if timeout is None:
        timeout = DB_TIMEOUT
    uri = 'file:' + path.replace('%', '%25').replace('?', '%3f').replace('#', '%23') + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def check_schema(conn):
    problems = []
    for table, needed in REQUIRED_COLUMNS.items():
        have = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
        missing = sorted(needed - have)
        if missing:
            problems.append(f'{table}: {", ".join(missing)}')
    if problems:
        raise SchemaError('state.db に必要な列がありません（' + ' / '.join(problems) + '）')


def fingerprint(conn, session_row):
    row = conn.execute('SELECT MAX(id) FROM messages WHERE session_id = ?',
                       (session_row['id'],)).fetchone()
    return [row[0], session_row['title'], session_row['ended_at'], session_row['end_reason']]


def select_sessions(conn, state):
    known = (state or {}).get('sessions', {})
    rows = conn.execute("SELECT * FROM sessions WHERE source = 'matrix' "
                        "ORDER BY started_at, id").fetchall()
    selected = []
    for row in rows:
        saved = known.get(row['id'], {}).get('fingerprint')
        if saved is None or list(saved) != fingerprint(conn, row):
            selected.append(row)
    return selected


def _slim_tool_calls(raw):
    if not raw:
        return None
    try:
        calls = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(calls, list):
        return None
    slim = []
    for c in calls:
        if not isinstance(c, dict):
            continue
        fn = c.get('function')
        if not isinstance(fn, dict) or fn.get('name') != 'terminal':
            continue
        slim.append({'id': c.get('id'), 'call_id': c.get('call_id'),
                     'function': {'name': fn.get('name'), 'arguments': fn.get('arguments')}})
    return slim or None


def build_payload(conn, session_row, tool_limit=20000):
    session = {k: session_row[k] for k in REQUIRED_COLUMNS['sessions']}
    messages = []
    rows = conn.execute('SELECT * FROM messages WHERE session_id = ? ORDER BY id',
                        (session_row['id'],)).fetchall()
    for r in rows:
        role = r['role']
        if role not in ('user', 'assistant', 'tool'):
            continue
        content = r['content']
        tool_calls = None
        if role == 'tool':
            if r['tool_name'] != 'terminal':
                continue
            if isinstance(content, str) and len(content) > tool_limit:
                content = content[:tool_limit]
        elif role == 'assistant':
            tool_calls = _slim_tool_calls(r['tool_calls'])
        messages.append({
            'id': r['id'], 'role': role, 'content': content, 'tool_calls': tool_calls,
            'tool_call_id': r['tool_call_id'], 'tool_name': r['tool_name'],
            'timestamp': r['timestamp'], 'display_kind': r['display_kind'],
        })
    return {'session': session, 'messages': messages}


def image_refs(payload, cache_dir):
    """user の本文の写真の印のうち、cache_dir の直下にある実在の画像だけを返す"""
    base = os.path.realpath(cache_dir)
    found = []
    for m in payload.get('messages', []):
        if m.get('role') != 'user' or not isinstance(m.get('content'), str):
            continue
        for path in _IMAGE_MARKER_RE.findall(m['content']):
            real = os.path.realpath(path.strip())
            if os.path.dirname(real) != base:
                continue
            if not real.lower().endswith(IMAGE_EXTENSIONS) or not os.path.isfile(real):
                continue
            if real not in found:
                found.append(real)
    return found


def _default_transport(url, headers, body):
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(url, token, payload, image_paths, transport=None):
    boundary = uuid.uuid4().hex
    parts = []

    def add(name, data, filename=None, ctype=None):
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename:
            head += f'; filename="{filename}"'
        head += '\r\n'
        if ctype:
            head += f'Content-Type: {ctype}\r\n'
        parts.append(head.encode() + b'\r\n' + data + b'\r\n')

    add('data', json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        ctype='application/json; charset=utf-8')
    for p in image_paths:
        with open(p, 'rb') as f:
            add('images', f.read(), filename=os.path.basename(p),
                ctype='application/octet-stream')
    body = b''.join(parts) + f'--{boundary}--\r\n'.encode()
    headers = {'Authorization': f'Bearer {token}',
               'Content-Type': f'multipart/form-data; boundary={boundary}',
               'Accept': 'application/json'}
    status, raw = (transport or _default_transport)(url.rstrip('/') + '/conversations', headers, body)
    if isinstance(raw, (bytes, str)):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    return status, raw if isinstance(raw, dict) else {}


def read_env(path):
    env = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            if line.startswith('export '):
                line = line[len('export '):].lstrip()
            key, value = line.split('=', 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                value = value[1:-1]
            env[key.strip()] = value
    return env


def load_state(path):
    try:
        with open(path, encoding='utf-8') as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {'sessions': {}}
    if not isinstance(state, dict) or not isinstance(state.get('sessions'), dict):
        return {'sessions': {}}
    return state


def save_state(path, state):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.sync-state-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None, transport=None):
    home = os.path.expanduser('~')
    ap = argparse.ArgumentParser(description='Hermes の会話をアプリに送る')
    ap.add_argument('--db', default=os.path.join(home, '.hermes', 'state.db'))
    ap.add_argument('--state', default=os.path.join(home, '.local', 'state',
                                                     'garden-conversation-sync.json'))
    ap.add_argument('--env', default=os.path.join(home, '.config', 'garden-api.env'))
    ap.add_argument('--cache-dir', default=os.path.join(home, '.hermes', 'cache', 'images'))
    ap.add_argument('--dry-run', action='store_true', help='送らずに対象の会話と件数を表示する')
    args = ap.parse_args(argv)

    try:
        conn = open_db(args.db)
        check_schema(conn)
    except SchemaError as e:
        print(f'エラー: {e}', file=sys.stderr)
        return 1
    except sqlite3.Error as e:
        print(f'エラー: state.db を読めません（{type(e).__name__}: {e}）', file=sys.stderr)
        return 1

    url = token = None
    if not args.dry_run:
        try:
            env = read_env(args.env)
        except (OSError, UnicodeDecodeError) as e:
            print(f'エラー: env ファイルを読めません（{type(e).__name__}）', file=sys.stderr)
            return 1
        url, token = env.get('GARDEN_API_URL'), env.get('GARDEN_API_TOKEN')
        if not url or not token:
            print('エラー: env ファイルに GARDEN_API_URL と GARDEN_API_TOKEN が必要です',
                  file=sys.stderr)
            return 1

    state = load_state(args.state)
    failed = 0
    try:
        sessions = select_sessions(conn, state)
        for row in sessions:
            sid = row['id']
            fp = fingerprint(conn, row)
            payload = build_payload(conn, row)
            sent = set(state['sessions'].get(sid, {}).get('sent_images', []))
            candidates = [p for p in image_refs(payload, args.cache_dir)
                          if os.path.basename(p) not in sent]
            valid = [p for p in candidates if _IMAGE_NAME_RE.fullmatch(os.path.basename(p))]
            bad_names = len(candidates) - len(valid)
            images = valid[:MAX_IMAGES_PER_REQUEST]
            more = len(valid) > len(images)
            n_msg, n_img = len(payload['messages']), len(images)
            if args.dry_run:
                print(f'[dry-run] {sid} 発言 {n_msg} 写真 {n_img}')
                continue
            try:
                status, _body = post(url, token, payload, images, transport)
            except Exception as e:
                print(f'{sid} 発言 {n_msg} 写真 {n_img} 失敗 {type(e).__name__}', file=sys.stderr)
                failed += 1
                continue
            line = f'{sid} 発言 {n_msg} 写真 {n_img} HTTP {status}'
            if bad_names:
                line += f' 不正な名前の写真 {bad_names} 件は送らない'
            print(line)
            if 200 <= status < 300:
                skipped = (_body.get('data') or {}).get('skipped_images')
                if skipped:
                    print(f'{sid} 縮小できずアプリが読み飛ばした写真 {len(skipped)} 件')
                prev = state['sessions'].get(sid, {})
                new = {'fingerprint': prev.get('fingerprint') if more else fp,
                       'sent_images': sorted(sent | {os.path.basename(p) for p in images})}
                if more:
                    print(f'{sid} 写真が残っているので次の回に続きを送る')
                if new['fingerprint'] is None:
                    new['fingerprint'] = []  # 未送信のままにして次の回も選ばれるようにする
                state['sessions'][sid] = new
            else:
                if status == 422:
                    err = _body.get('error') if isinstance(_body.get('error'), dict) else {}
                    print(f'{sid} HTTP 422: アプリが内容を受け付けません'
                          f'（code={err.get("code")} message={err.get("message")}）。'
                          'code / message を見て原因を確認してください（型の不一致、session.id の形、発言が5000件超など）', file=sys.stderr)
                failed += 1
    except sqlite3.Error as e:
        print(f'エラー: state.db の読み取りに失敗しました（{type(e).__name__}: {e}）', file=sys.stderr)
        failed += 1
    finally:
        conn.close()

    if not args.dry_run:
        save_state(args.state, state)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
