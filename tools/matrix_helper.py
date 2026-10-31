"""Matrix サーバー（Tuwunel / Synapse）の初期設定とテスト送信の補助スクリプト。

サーバー上で Hermes の実行ユーザーが使う。Python 標準ライブラリだけで動く。
パスワード・登録用トークンは getpass で聞き、アクセストークンは標準出力の
`MATRIX_ACCESS_TOKEN=...` の1行だけに出す（`>>` でファイルに足す想定）。

使い方は `python3 matrix_helper.py --help`。手順は
../garden-app-private/docs/superpowers/plans/2026-10-18-hermes-matrix.md と docs/api/hermes-local-chat.md。
"""
import argparse
import getpass
import json
import mimetypes
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

DEFAULT_HS = 'http://127.0.0.1:8008'


class MatrixError(Exception):
    pass


def _urllib_transport(method, url, body=None, headers=None):
    """(status, JSON の dict) を返す。テストでは偽物に差し替える"""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read() or b'{}')
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b'{}')
        except ValueError:
            return e.code, {'error': raw.decode('utf-8', 'replace')[:200]}


def _q(value):
    return urllib.parse.quote(value, safe='')


class Client:
    def __init__(self, hs, token=None, transport=None, txn_ids=None):
        self.hs = hs.rstrip('/')
        self.token = token
        self.transport = transport or _urllib_transport
        self.txn_ids = txn_ids

    def _request(self, method, path, payload=None, raw=None, content_type=None,
                 ok=(200,)):
        headers = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        body = raw
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif content_type:
            headers['Content-Type'] = content_type
        status, data = self.transport(method, self.hs + path, body, headers)
        if status not in ok:
            raise MatrixError(f"{status} {data.get('errcode', '')} {data.get('error', '')}".strip())
        return status, data

    def _next_txn(self):
        return next(self.txn_ids) if self.txn_ids else uuid.uuid4().hex

    def register(self, username, password, registration_token):
        """登録用トークンの段階（と、求められれば m.login.dummy）を済ませて登録する"""
        payload = {'username': username, 'password': password,
                   'initial_device_display_name': 'matrix_helper', 'inhibit_login': True}
        _, data = self._request('POST', '/_matrix/client/v3/register', payload, ok=(200, 401))
        for _ in range(5):
            if 'user_id' in data:
                return data['user_id']
            completed = set(data.get('completed', []))
            stages = [s for flow in data.get('flows', []) for s in flow.get('stages', [])]
            pending = [s for s in stages if s not in completed]
            if not pending:
                raise MatrixError(f'登録の段階が分からない: {data}')
            stage = pending[0]
            if stage == 'm.login.registration_token':
                auth = {'type': stage, 'token': registration_token, 'session': data['session']}
            elif stage == 'm.login.dummy':
                auth = {'type': stage, 'session': data['session']}
            else:
                raise MatrixError(f'対応していない登録の段階: {stage}')
            _, data = self._request('POST', '/_matrix/client/v3/register',
                                    {**payload, 'auth': auth}, ok=(200, 401))
        raise MatrixError(f'登録が終わらない: {data}')

    def login(self, username, password):
        _, data = self._request('POST', '/_matrix/client/v3/login', {
            'type': 'm.login.password',
            'identifier': {'type': 'm.id.user', 'user': username},
            'password': password,
            'initial_device_display_name': 'matrix_helper',
        })
        return data

    def whoami(self):
        return self._request('GET', '/_matrix/client/v3/account/whoami')[1]['user_id']

    def create_dm(self, invitee, encrypted=False):
        """1対1の部屋を作り、自分の m.direct にも登録する（Element X で DM として出る）。
        既定は暗号化なし。encrypted=True で E2EE の部屋にする（後から暗号化を外すことはできない）"""
        me = self.whoami()
        body = {
            'preset': 'private_chat',
            'is_direct': True,
            'invite': [invitee],
            'name': 'Hermes',
        }
        if encrypted:
            body['name'] = 'Hermes（暗号化）'
            body['initial_state'] = [{
                'type': 'm.room.encryption', 'state_key': '',
                'content': {'algorithm': 'm.megolm.v1.aes-sha2'},
            }]
        _, data = self._request('POST', '/_matrix/client/v3/createRoom', body)
        room_id = data['room_id']
        path = f'/_matrix/client/v3/user/{_q(me)}/account_data/m.direct'
        status, direct = self._request('GET', path, ok=(200, 404))
        if status == 404:
            direct = {}
        direct.setdefault(invitee, [])
        if room_id not in direct[invitee]:
            direct[invitee].append(room_id)
        self._request('PUT', path, direct)
        return room_id

    def join(self, room_id):
        return self._request('POST', f'/_matrix/client/v3/join/{_q(room_id)}', {})[1]['room_id']

    def _send(self, room_id, content):
        path = (f'/_matrix/client/v3/rooms/{_q(room_id)}/send/m.room.message/'
                f'{_q(self._next_txn())}')
        return self._request('PUT', path, content)[1]['event_id']

    def send_text(self, room_id, text):
        return self._send(room_id, {'msgtype': 'm.text', 'body': text})

    def send_image(self, room_id, path, caption=None):
        path = Path(path)
        data = path.read_bytes()
        mimetype = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        _, up = self._request('POST', f'/_matrix/media/v3/upload?filename={_q(path.name)}',
                              raw=data, content_type=mimetype)
        return self._send(room_id, {
            'msgtype': 'm.image',
            'body': caption or path.name,
            'filename': path.name,
            'url': up['content_uri'],
            'info': {'mimetype': mimetype, 'size': len(data)},
        })

    def messages(self, room_id, limit=10):
        path = f'/_matrix/client/v3/rooms/{_q(room_id)}/messages?dir=b&limit={int(limit)}'
        return self._request('GET', path)[1].get('chunk', [])

    def logout(self):
        self._request('POST', '/_matrix/client/v3/logout', {})


def read_token_file(path):
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('MATRIX_ACCESS_TOKEN='):
            return line.split('=', 1)[1].strip()
    raise MatrixError(f'{path} に MATRIX_ACCESS_TOKEN= の行が無い')


def _print_messages(chunk):
    for ev in reversed(chunk):
        if ev.get('type') != 'm.room.message':
            continue
        c = ev.get('content', {})
        text = c.get('body', '')
        if c.get('msgtype') != 'm.text':
            text = f"[{c.get('msgtype')}] {text}"
        print(f"{ev.get('sender')}: {text}")


def main(argv=None):
    p = argparse.ArgumentParser(description='Matrix の初期設定とテスト送信の補助')
    p.add_argument('--hs', default=DEFAULT_HS, help=f'Matrix サーバーの URL（既定 {DEFAULT_HS}）')
    p.add_argument('--token-file', help='MATRIX_ACCESS_TOKEN= の行があるファイル')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('register').add_argument('username')
    sub.add_parser('login').add_argument('username')
    sub.add_parser('whoami')
    cd = sub.add_parser('create-dm')
    cd.add_argument('invitee')
    cd.add_argument('--encrypted', action='store_true', help='暗号化（E2EE）ありの部屋にする')
    sub.add_parser('join').add_argument('room_id')
    st = sub.add_parser('send-text')
    st.add_argument('room_id')
    st.add_argument('text')
    si = sub.add_parser('send-image')
    si.add_argument('room_id')
    si.add_argument('path')
    si.add_argument('--caption')
    ms = sub.add_parser('messages')
    ms.add_argument('room_id')
    ms.add_argument('--limit', type=int, default=10)
    sub.add_parser('logout')
    args = p.parse_args(argv)

    try:
        if args.cmd == 'register':
            token = getpass.getpass('登録用トークン: ')
            pw = getpass.getpass(f'{args.username} のパスワード: ')
            if pw != getpass.getpass('もう一度: '):
                raise MatrixError('パスワードが一致しない')
            print(Client(args.hs).register(args.username, pw, token))
            return 0
        if args.cmd == 'login':
            data = Client(args.hs).login(args.username, getpass.getpass(f'{args.username} のパスワード: '))
            print(f"user_id={data['user_id']} device_id={data.get('device_id')}", file=sys.stderr)
            print(f"MATRIX_ACCESS_TOKEN={data['access_token']}")
            return 0
        if not args.token_file:
            raise MatrixError('--token-file が必要')
        client = Client(args.hs, token=read_token_file(args.token_file))
        if args.cmd == 'whoami':
            print(client.whoami())
        elif args.cmd == 'create-dm':
            print(client.create_dm(args.invitee, encrypted=args.encrypted))
        elif args.cmd == 'join':
            print(client.join(args.room_id))
        elif args.cmd == 'send-text':
            print(client.send_text(args.room_id, args.text))
        elif args.cmd == 'send-image':
            print(client.send_image(args.room_id, args.path, caption=args.caption))
        elif args.cmd == 'messages':
            _print_messages(client.messages(args.room_id, args.limit))
        elif args.cmd == 'logout':
            client.logout()
            print('ログアウトした')
        return 0
    except (MatrixError, OSError) as e:
        print(f'エラー: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
