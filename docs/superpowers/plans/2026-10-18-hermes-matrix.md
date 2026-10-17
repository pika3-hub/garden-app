# Hermes の LAN 内チャット（Matrix＋Element X）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** iPhone・iPad の Element X から、Telegram を通らずに LAN 内だけで Hermes に写真付きの登録を頼めるようにする。

**Architecture:** 今の Ubuntu サーバーに Tuwunel（Matrix サーバー、127.0.0.1:8008）と Caddy（`<サーバーのIP>:8448` で HTTPS を受けて転送）を入れ、ufw で LAN からだけ 8448 を許可する。Hermes の gateway は Matrix の Bot として 127.0.0.1:8008 に直接つなぐ。Telegram は並行して残す。

**Tech Stack:** Tuwunel（公式 apt リポジトリ）、Caddy（公式 apt リポジトリ、`tls internal`）、ufw、Hermes Agent の Matrix アダプター（`mautrix`）、Element X（iOS）、補助スクリプト（Python 標準ライブラリのみ）

**Spec:** [`docs/superpowers/specs/2026-10-18-hermes-matrix-design.md`](../specs/2026-10-18-hermes-matrix-design.md)

## 進め方（この計画に固有）

- Task 1 だけがメイン PC での作業（補助スクリプトとテスト）。Task 2 以降はサーバーの作業で、**Claude はサーバーに入れない**。Claude がコマンドを1ステップずつ示し、ユーザーが実行して結果を貼り、Claude が「期待する出力」と照合する
- sudo を含むステップは先頭で `sudo -v`
- メイン PC でユーザーに実行してもらうコマンドは PowerShell の書き方（`curl.exe`、`scp`）
- **秘密の値（パスワード、登録用トークン、アクセストークン）はチャットに貼らない**。それらが画面に出るステップは「貼らないでください」と明記し、結果は「成功した／エラー文」だけ教えてもらう
- 各 Task の最後の「確認」が済むまで次の Task に進まない。失敗したら、その Task の「失敗したとき」に従う

## Global Constraints

- Matrix のサーバー名は `garden.home.arpa`（後から変えられない）
- スマホからの接続先は `https://<サーバーのIP>:8448`。Tuwunel の待ち受けは `127.0.0.1:8008` だけ
- フェデレーションはしない（`allow_federation = false`、`trusted_servers = []`）
- 新規登録は閉じる。アカウントは `@<user>:garden.home.arpa`（1番目・管理者）と `@hermes:garden.home.arpa`（2番目）の2つだけ
- 第1段階では E2EE を使わない（`MATRIX_E2EE_MODE=off`、部屋は暗号化なし）
- Caddy の管理用 API は止める（`admin off`）。設定の反映は `systemctl restart caddy`
- `/opt/garden-app` と garden-app のコード、ufw の既存ルール（22・5000 の許可、`<user>` → 5000 の遮断）は変えない
- Telegram は並行して残す（Hermes の `.env` の Telegram の行に触れない）
- 公開リポジトリの文書には固有値を書かず `<サーバーのIP>`・`<LANの範囲>`・`<user>` の記号で書く。実際の値は `../garden-app-private/local-env.md`

## Review Focus

1. **iPhone の写真が HEIC のまま届く** → gateway の形式チェックで断られ、黙って登録されない。Task 8 で gateway のログの受け取り形式を見る
2. **サーバーを再起動した後** → Tuwunel・Caddy・Hermes の Matrix 接続が自動で戻ってほしい（ユーザーはサーバーをよく止める）。Task 9 で再起動して確かめる
3. **Hermes の実行ユーザーが Caddy 経由で 5000番に届く** → 届いてはいけない。Task 4 で `localhost:2019` に届かないこと、Task 9 で `<user>` からの 5000 の遮断が残っていることを確かめる
4. **フェデレーション・外向き接続** → 他の Matrix サーバーとやりとりしないこと。Task 3 で federation の入り口が無効なことを確かめる
5. **許可していない部屋・ユーザーからの依頼** → Hermes が応答しないこと。Task 6 で `MATRIX_ALLOWED_USERS`・`MATRIX_ALLOWED_ROOMS` を設定し、設定値をログで確かめる

---

### Task 1: 補助スクリプト `tools/matrix_helper.py`（メイン PC）

アカウントの登録、ログイン（トークンの取得）、部屋の作成、文字・画像の送信、メッセージの確認を、サーバー上で curl を組み立てずにできるようにする。パスワード・トークンを画面やシェルの履歴に残さない（`getpass` で入力、トークンはファイルにだけ書く）。Synapse に切り替えたときもそのまま使える。

**Files:**
- Create: `tools/matrix_helper.py`
- Test: `tests/test_matrix_helper.py`

**Interfaces:**
- Produces（Task 5・6 でサーバー上で使うコマンド。既定の接続先は `--hs http://127.0.0.1:8008`）:
  - `python3 matrix_helper.py register <username>` … 登録用トークンとパスワードを聞いて登録し、`user_id` を表示する
  - `python3 matrix_helper.py login <username>` … パスワードを聞いてログインし、標準出力に `MATRIX_ACCESS_TOKEN=<token>` の1行だけを出す（`>>` でファイルに足す。`user_id`・`device_id` は標準エラーに出す）
  - `python3 matrix_helper.py --token-file <path> whoami`
  - `python3 matrix_helper.py --token-file <path> create-dm <invitee_user_id>` … 暗号化なしの1対1の部屋を作って招待し、`room_id` を表示する
  - `python3 matrix_helper.py --token-file <path> join <room_id>`
  - `python3 matrix_helper.py --token-file <path> send-text <room_id> <text>`
  - `python3 matrix_helper.py --token-file <path> send-image <room_id> <path> [--caption <text>]`
  - `python3 matrix_helper.py --token-file <path> messages <room_id> [--limit N]`
  - `python3 matrix_helper.py --token-file <path> logout`
  - `--token-file` は `MATRIX_ACCESS_TOKEN=` で始まる行を読む（`~/.hermes/.env` をそのまま渡せる）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_matrix_helper.py`:

```python
"""tools/matrix_helper.py のテスト。HTTP は偽物に差し替え、実サーバーには接続しない。"""
import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / 'tools' / 'matrix_helper.py'
_spec = importlib.util.spec_from_file_location('matrix_helper', _PATH)
mh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mh)


class FakeTransport:
    """(method, path) ごとに用意した応答を順に返し、受けた呼び出しを記録する"""

    def __init__(self, responses):
        self.responses = {k: list(v) for k, v in responses.items()}
        self.calls = []

    def __call__(self, method, url, body=None, headers=None):
        path = url.split('?', 1)[0].split('127.0.0.1:8008', 1)[1]
        self.calls.append({'method': method, 'path': path, 'url': url,
                           'body': body, 'headers': headers or {}})
        return self.responses[(method, path)].pop(0)


def _json(call):
    return json.loads(call['body'])


def test_register_completes_registration_token_stage():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/register'): [
            (401, {'session': 's1', 'flows': [{'stages': ['m.login.registration_token']}]}),
            (200, {'user_id': '@alice:garden.home.arpa'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    user_id = client.register('alice', 'pw', 'tok')

    assert user_id == '@alice:garden.home.arpa'
    first, second = (_json(c) for c in fake.calls)
    assert first['username'] == 'alice' and 'auth' not in first
    assert second['auth'] == {'type': 'm.login.registration_token',
                              'token': 'tok', 'session': 's1'}
    assert second['inhibit_login'] is True


def test_register_completes_dummy_stage_after_token():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/register'): [
            (401, {'session': 's1',
                   'flows': [{'stages': ['m.login.registration_token', 'm.login.dummy']}]}),
            (401, {'session': 's1', 'completed': ['m.login.registration_token'],
                   'flows': [{'stages': ['m.login.registration_token', 'm.login.dummy']}]}),
            (200, {'user_id': '@alice:garden.home.arpa'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    client.register('alice', 'pw', 'tok')

    assert _json(fake.calls[2])['auth'] == {'type': 'm.login.dummy', 'session': 's1'}


def test_register_raises_on_error():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/register'): [
            (403, {'errcode': 'M_FORBIDDEN', 'error': 'Registration is disabled'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    with pytest.raises(mh.MatrixError, match='M_FORBIDDEN'):
        client.register('alice', 'pw', 'tok')


def test_login_returns_token_and_sends_password_identifier():
    fake = FakeTransport({
        ('POST', '/_matrix/client/v3/login'): [
            (200, {'access_token': 'AT', 'user_id': '@hermes:garden.home.arpa',
                   'device_id': 'DEV'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', transport=fake)

    result = client.login('hermes', 'pw')

    assert result['access_token'] == 'AT'
    body = _json(fake.calls[0])
    assert body['type'] == 'm.login.password'
    assert body['identifier'] == {'type': 'm.id.user', 'user': 'hermes'}


def test_create_dm_is_unencrypted_and_marks_direct():
    fake = FakeTransport({
        ('GET', '/_matrix/client/v3/account/whoami'): [
            (200, {'user_id': '@me:garden.home.arpa'}),
        ],
        ('POST', '/_matrix/client/v3/createRoom'): [(200, {'room_id': '!r:garden.home.arpa'})],
        ('GET', '/_matrix/client/v3/user/%40me%3Agarden.home.arpa/account_data/m.direct'): [
            (404, {'errcode': 'M_NOT_FOUND'}),
        ],
        ('PUT', '/_matrix/client/v3/user/%40me%3Agarden.home.arpa/account_data/m.direct'): [
            (200, {}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake)

    room_id = client.create_dm('@hermes:garden.home.arpa')

    assert room_id == '!r:garden.home.arpa'
    create = _json(fake.calls[1])
    assert create['is_direct'] is True
    assert create['invite'] == ['@hermes:garden.home.arpa']
    assert create['preset'] == 'private_chat'  # trusted_private_chat だと Hermes も部屋の管理者になる
    assert all(ev['type'] != 'm.room.encryption' for ev in create.get('initial_state', []))
    assert _json(fake.calls[3]) == {'@hermes:garden.home.arpa': ['!r:garden.home.arpa']}
    assert fake.calls[1]['headers']['Authorization'] == 'Bearer AT'


def test_send_image_uploads_then_sends_m_image(tmp_path):
    img = tmp_path / 'leaf.jpg'
    img.write_bytes(b'ÿØÿàjpegdata')
    fake = FakeTransport({
        ('POST', '/_matrix/media/v3/upload'): [(200, {'content_uri': 'mxc://garden.home.arpa/abc'})],
        ('PUT', '/_matrix/client/v3/rooms/%21r%3Agarden.home.arpa/send/m.room.message/t1'): [
            (200, {'event_id': '$e'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake,
                       txn_ids=iter(['t1']))

    client.send_image('!r:garden.home.arpa', img)

    upload, send = fake.calls
    assert upload['body'] == img.read_bytes()
    assert upload['headers']['Content-Type'] == 'image/jpeg'
    assert 'filename=leaf.jpg' in upload['url']
    event = _json(send)
    assert event['msgtype'] == 'm.image'
    assert event['url'] == 'mxc://garden.home.arpa/abc'
    assert event['body'] == 'leaf.jpg'
    assert event['info'] == {'mimetype': 'image/jpeg', 'size': len(img.read_bytes())}
    assert event['filename'] == 'leaf.jpg'


def test_send_image_caption_goes_to_body_and_filename_is_kept(tmp_path):
    img = tmp_path / 'leaf.jpg'
    img.write_bytes(b'\xff\xd8\xff\xe0jpegdata')
    fake = FakeTransport({
        ('POST', '/_matrix/media/v3/upload'): [(200, {'content_uri': 'mxc://garden.home.arpa/abc'})],
        ('PUT', '/_matrix/client/v3/rooms/%21r%3Agarden.home.arpa/send/m.room.message/t1'): [
            (200, {'event_id': '$e'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake,
                       txn_ids=iter(['t1']))

    client.send_image('!r:garden.home.arpa', img, caption='葉の写真')

    event = _json(fake.calls[1])
    assert event['body'] == '葉の写真'
    assert event['filename'] == 'leaf.jpg'


def test_send_image_without_caption_uses_filename_as_body(tmp_path):
    img = tmp_path / 'leaf.png'
    img.write_bytes(b'\x89PNGdata')
    fake = FakeTransport({
        ('POST', '/_matrix/media/v3/upload'): [(200, {'content_uri': 'mxc://garden.home.arpa/p'})],
        ('PUT', '/_matrix/client/v3/rooms/%21r%3Agarden.home.arpa/send/m.room.message/t1'): [
            (200, {'event_id': '$e'}),
        ],
    })
    client = mh.Client('http://127.0.0.1:8008', token='AT', transport=fake,
                       txn_ids=iter(['t1']))

    client.send_image('!r:garden.home.arpa', img)

    event = _json(fake.calls[1])
    assert event['body'] == 'leaf.png'
    assert fake.calls[0]['headers']['Content-Type'] == 'image/png'


def test_read_token_file_finds_matrix_access_token_line(tmp_path):
    env = tmp_path / '.env'
    env.write_text('TELEGRAM_BOT_TOKEN=x\nMATRIX_ACCESS_TOKEN=abc123\n', encoding='utf-8')

    assert mh.read_token_file(env) == 'abc123'


def test_read_token_file_without_line_raises(tmp_path):
    env = tmp_path / '.env'
    env.write_text('TELEGRAM_BOT_TOKEN=x\n', encoding='utf-8')

    with pytest.raises(mh.MatrixError, match='MATRIX_ACCESS_TOKEN'):
        mh.read_token_file(env)
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run python -m pytest tests/test_matrix_helper.py -v`
Expected: FAIL（`tools/matrix_helper.py` が無いので `FileNotFoundError`）

- [ ] **Step 3: 実装を書く**

`tools/matrix_helper.py`:

```python
"""Matrix サーバー（Tuwunel / Synapse）の初期設定とテスト送信の補助スクリプト。

サーバー上で Hermes の実行ユーザーが使う。Python 標準ライブラリだけで動く。
パスワード・登録用トークンは getpass で聞き、アクセストークンは標準出力の
`MATRIX_ACCESS_TOKEN=...` の1行だけに出す（`>>` でファイルに足す想定）。

使い方は `python3 matrix_helper.py --help`。手順は
docs/superpowers/plans/2026-10-18-hermes-matrix.md と docs/api/hermes-local-chat.md。
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

    def create_dm(self, invitee):
        """暗号化なしの1対1の部屋を作り、自分の m.direct にも登録する（Element X で DM として出る）"""
        me = self.whoami()
        _, data = self._request('POST', '/_matrix/client/v3/createRoom', {
            'preset': 'private_chat',
            'is_direct': True,
            'invite': [invitee],
            'name': 'Hermes',
        })
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
    sub.add_parser('create-dm').add_argument('invitee')
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
            print(client.create_dm(args.invitee))
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
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run python -m pytest tests/test_matrix_helper.py -v`
Expected: PASS（10件）。続けて `uv run python -m pytest -q` で全体も通ること（HEIC の6件はメイン PC ではスキップされる）

- [ ] **Step 5: コミット**

```bash
git add tools/matrix_helper.py tests/test_matrix_helper.py
git status --short
git commit -m "Matrix の初期設定とテスト送信の補助スクリプトを追加する"
```

---

### Task 2: 段階0 下調べ（サーバー）

Hermes の版・仮想環境・Matrix 用の部品の入れ方と、サーバーの空きを調べる。**何も変えない。**

- [ ] **Step 1: OS・空き・使用中のポート**

```bash
lsb_release -ds; uname -m
free -h; nproc; df -h /
sudo -v
sudo ss -ltnp | grep -E ':(80|443|2019|6167|8008|8448) ' || echo "使用中のポートなし"
```

Expected: Ubuntu の版、`x86_64`、メモリ・空きの表示、最後に `使用中のポートなし`（何か出たら、そのプロセスを見てポートを見直す）

- [ ] **Step 2: Hermes の版・起動方法・仮想環境**

```bash
hermes --version
systemctl --user cat hermes-gateway.service | grep -E '^(ExecStart|Environment|WorkingDirectory)'
H="$(readlink -f "$(command -v hermes)")"; echo "$H"; head -1 "$H"
```

Expected: 版（調査時は v0.21.6）、`ExecStart=` の行、`hermes` の実体と、1行目の `#!...python`（これが Hermes の仮想環境の Python。以下 `<HPY>` と書く）

- [ ] **Step 3: Matrix の部品があるか、`.env` に Matrix の設定が既にあるか**

```bash
<HPY> -c "import mautrix, sys; print('mautrix', mautrix.__version__, sys.version)" || echo "mautrix なし"
<HPY> -c "import pm; print(pm.__file__)" || echo "pm なし"
grep -c '^MATRIX_' ~/.hermes/.env || true
python3 --version
```

Expected: `mautrix なし`（調査時は未導入）、`pm` の場所（公式文書の `pm.sync_venv(['matrix'], explicit=True)` が使えるか）、`0`、システムの Python（補助スクリプト用。3.10 以上）

- [ ] **Step 4: 入れ方を決める（Claude）**

結果から、Task 6 Step 1 で使う導入コマンドを決める。

- `pm` が読み込めた → `<HPY> -c "import pm; pm.sync_venv(['matrix'], explicit=True)"`
- `pm` が無い → `hermes gateway setup` の Matrix の項目が部品を入れるかを Hermes の文書・ソースで確かめる。それも無ければ `<HPY> -m pip install 'mautrix'`（仮想環境に pip があるか `<HPY> -m pip --version` で確認）

**失敗したとき:** どの方法でも入らない見込みなら、ここで止めて設計を見直す（Tuwunel・Caddy はまだ入れていないので、戻す作業は無い）

---

### Task 3: 段階1 Tuwunel を入れて起動する（サーバー）

- [ ] **Step 1: 公式 apt リポジトリを足して入れる**

```bash
sudo -v
sudo curl -fsSL -o /usr/share/keyrings/tuwunel-archive-keyring.gpg https://apt.f.dog/tuwunel-archive-keyring.gpg
sudo tee /etc/apt/sources.list.d/tuwunel.sources >/dev/null <<'EOF'
Types: deb
URIs: https://apt.f.dog
Suites: stable
Components: main
Signed-By: /usr/share/keyrings/tuwunel-archive-keyring.gpg
EOF
sudo apt update
sudo apt install tuwunel
apt-cache policy tuwunel | head -3
```

Expected: `Installed: 1.9.4-1` 以上（1.9.3 未満なら Element X の既知の不具合があるので止める）。インストール直後は `server_name` が無いので起動に失敗していてもよい

- [ ] **Step 2: 元の設定を残し、設定を書く**

```bash
sudo cp -n /etc/tuwunel/tuwunel.toml /etc/tuwunel/tuwunel.toml.orig
sudo tee /etc/tuwunel/tuwunel.toml >/dev/null <<'EOF'
# garden-app の Hermes 用（LAN 内だけ・フェデレーションなし）
# 元の設定例は tuwunel.toml.orig。項目の説明は https://matrix-construct.github.io/tuwunel/configuration/examples.html
[global]
server_name = "garden.home.arpa"
database_path = "/var/lib/tuwunel"
address = ["127.0.0.1"]
port = 8008

# 他の Matrix サーバーとやりとりしない
allow_federation = false
trusted_servers = []
allow_outgoing_presence = false

# 新規登録は閉じる（アカウントを作るときだけ Task 5 で開ける）
allow_registration = false

new_user_displayname_suffix = ""
EOF
sudo chown root:tuwunel /etc/tuwunel/tuwunel.toml
sudo chmod 640 /etc/tuwunel/tuwunel.toml
sudo ls -l /etc/tuwunel/
```

Expected: `-rw-r----- 1 root tuwunel ... tuwunel.toml`（Task 5 で登録用トークンを書くので、`<user>` に読ませない）。`tuwunel.toml.orig` も残っている

- [ ] **Step 3: 起動して自動起動を有効にする**

```bash
sudo systemctl enable --now tuwunel.service
sudo systemctl restart tuwunel.service
systemctl is-active tuwunel.service; systemctl is-enabled tuwunel.service
sudo journalctl -u tuwunel.service -n 30 --no-pager
```

Expected: `active`・`enabled`。ログに起動完了の行（`Listening on 127.0.0.1:8008` に当たるもの）があり、`ERROR` が無い。初回起動で管理用の部屋が作られる旨の行が出てもよい

- [ ] **Step 4: 確認**

```bash
curl -s http://127.0.0.1:8008/_matrix/client/versions | head -c 300; echo
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8008/_matrix/federation/v1/version
sudo ss -ltnp | grep 8008
```

Expected:
- 1行目: `{"versions":["r0.0.1",...` のような JSON
- 2行目: `200` 以外（フェデレーションを切っているので 403/404 など）。`200` なら `allow_federation` が効いていないので設定を見直す
- 3行目: `127.0.0.1:8008` だけ（`0.0.0.0` や `*` なら `address` を見直す）

**失敗したとき:** `journalctl -u tuwunel` のエラーを Claude が読み、設定の項目名を Tuwunel の設定例（`/etc/tuwunel/tuwunel.toml.orig`）と照らして直す

---

### Task 4: 段階2 Caddy と ufw（サーバー、確認はメイン PC）

- [ ] **Step 1: 公式 apt リポジトリから Caddy を入れる**

```bash
sudo -v
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
caddy version
```

Expected: `v2.` で始まる版。入れた直後は既定の Caddyfile で 80番の待ち受けが始まっているが、Step 2 で置き換える

- [ ] **Step 2: Caddyfile を書く**

`<サーバーのIP>` は実際の IP に置き換えて実行する（Claude が local-env.md の値を入れたコマンドを示す）。

```bash
sudo cp -n /etc/caddy/Caddyfile /etc/caddy/Caddyfile.orig
sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
# garden-app の Hermes 用 Matrix（Tuwunel）への HTTPS の入り口
{
	# 管理用 API を止める（サーバー内の誰からも設定を書き換えられないように）。
	# 設定の反映は systemctl restart caddy で行う
	admin off
	# IP で接続するスマホは SNI を送らない
	default_sni <サーバーのIP>
	# 80番の HTTP→HTTPS 転送を作らない
	auto_https disable_redirects
	# 発行元の証明書を OS に入れようとしない（スマホに手で入れる）
	skip_install_trust
}

https://<サーバーのIP>:8448 {
	tls internal
	reverse_proxy 127.0.0.1:8008
}
EOF
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Expected: 最後に `Valid configuration`

- [ ] **Step 3: 再起動して待ち受けを確かめる**

```bash
sudo systemctl restart caddy
systemctl is-active caddy; systemctl is-enabled caddy
sudo journalctl -u caddy -n 30 --no-pager
sudo ss -ltnp | grep caddy
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:2019/config/ || true
```

Expected: `active`・`enabled`。ログに証明書を発行した行があり、`error` が無い。`ss` は `:8448` だけ（`:80`・`:2019` が無い）。最後の行は `000`（管理用 API につながらない）

- [ ] **Step 4: ufw で LAN から 8448 を許可する**

```bash
sudo ufw allow from <LANの範囲> to any port 8448 proto tcp comment 'Matrix (Caddy)'
sudo ufw status numbered
```

Expected: 既存の 22・5000 のルールに加えて `8448/tcp ALLOW IN <LANの範囲>` が増えている。既存のルールが変わっていない

- [ ] **Step 5: 確認（メイン PC の PowerShell）**

```powershell
curl.exe -sk https://<サーバーのIP>:8448/_matrix/client/versions
curl.exe -s -o NUL -w "%{http_code}`n" --connect-timeout 5 http://<サーバーのIP>:8008/
```

Expected: 1行目は Task 3 Step 4 と同じ JSON。2行目は `000`（8008 は LAN から届かない）

**失敗したとき:** 1行目が `000` なら ufw のルールと `ss` の待ち受けを見る。TLS のエラーなら `journalctl -u caddy` の証明書の行を Claude が読む

---

### Task 5: 段階3 アカウントを作る（サーバー）

自分 → Hermes の順に作る（先に作ったほうが管理者）。登録はこの Task の間だけ開ける。

- [ ] **Step 1: 補助スクリプトをサーバーに送る（メイン PC の PowerShell）**

```powershell
scp D:\workspace\garden-app\tools\matrix_helper.py <user>@<サーバーのIP>:~/matrix_helper.py
```

サーバーで:

```bash
python3 ~/matrix_helper.py --help | head -5
```

Expected: 使い方の表示

- [ ] **Step 2: 登録用トークンを作って登録を開ける**

```bash
sudo -v
TOKEN="$(openssl rand -hex 24)"
sudo sed -i 's/^allow_registration = false$/allow_registration = true\nregistration_token = "'"$TOKEN"'"/' /etc/tuwunel/tuwunel.toml
sudo grep -E '^(allow_registration|registration_token)' /etc/tuwunel/tuwunel.toml | sed 's/"[0-9a-f]*"/"(隠す)"/'
sudo systemctl restart tuwunel.service; systemctl is-active tuwunel.service
echo "登録用トークン: $TOKEN"
```

Expected: `allow_registration = true` と `registration_token = "(隠す)"`、`active`。最後の行にトークンが出る。**この行はチャットに貼らないでください**（次の Step で入力に使う）

- [ ] **Step 3: 2つのアカウントを作る**

パスワードはパスワード管理アプリで作り、そこに保存してから入力する（自分と Hermes で別のもの）。

```bash
python3 ~/matrix_helper.py register <user>
python3 ~/matrix_helper.py register hermes
```

Expected: それぞれ `@<user>:garden.home.arpa`、`@hermes:garden.home.arpa` が表示される

- [ ] **Step 4: 登録を閉じる**

```bash
sudo -v
sudo sed -i -e 's/^allow_registration = true$/allow_registration = false/' -e '/^registration_token = /d' /etc/tuwunel/tuwunel.toml
sudo grep -E '^(allow_registration|registration_token)' /etc/tuwunel/tuwunel.toml
sudo systemctl restart tuwunel.service; systemctl is-active tuwunel.service
unset TOKEN
```

Expected: `allow_registration = false` だけが出て、`registration_token` の行は無い。`active`

- [ ] **Step 5: 確認**

```bash
python3 ~/matrix_helper.py register testuser
sudo journalctl -u tuwunel.service --since "-10 min" --no-pager | grep -i -E 'admin|registered' | head
```

トークンを聞かれたら何でもよいので入力する。Expected: `エラー: 403 M_FORBIDDEN ...` のような拒否。ログに `<user>` が管理者の部屋に入った（管理者になった）旨の行がある

**失敗したとき:** 登録の段階が違うと `対応していない登録の段階: ...` と出る。その段階名を Claude が見て補助スクリプトを直す（Task 1 に戻ってテストを足す）。`<user>` が管理者になっていなければ、Tuwunel の管理コマンドで付ける方法を Claude が調べる

---

### Task 6: 段階4 Hermes をつなぎ、サーバーの中だけで相性を確かめる（サーバー）

Tuwunel と Hermes（`mautrix`）の相性、画像の受け渡しを、スマホに触る前に確かめる。

- [ ] **Step 1: Matrix の部品を入れる**

Task 2 Step 4 で決めたコマンドを実行する。続けて:

```bash
<HPY> -c "import mautrix; print('mautrix', mautrix.__version__)"
```

Expected: `mautrix` の版

- [ ] **Step 2: Hermes のトークンを取って `.env` に書く**

```bash
cp -p ~/.hermes/.env ~/.hermes/.env.bak-before-matrix
python3 ~/matrix_helper.py login hermes >> ~/.hermes/.env
cat >> ~/.hermes/.env <<'EOF'
MATRIX_HOMESERVER=http://127.0.0.1:8008
MATRIX_USER_ID=@hermes:garden.home.arpa
MATRIX_ALLOWED_USERS=@<user>:garden.home.arpa
MATRIX_E2EE_MODE=off
EOF
grep '^MATRIX_' ~/.hermes/.env | sed 's/^\(MATRIX_ACCESS_TOKEN=\).*/\1(隠す)/'
ls -l ~/.hermes/.env
```

Expected: `user_id=@hermes:garden.home.arpa device_id=...` が表示され、MATRIX_ の5行（トークンは `(隠す)`）が出る。`.env` は `-rw-------`（違えば `chmod 600 ~/.hermes/.env`）

- [ ] **Step 3: 自分のトークンを一時ファイルに取り、部屋を作る**

```bash
umask 077
python3 ~/matrix_helper.py login <user> > ~/.config/matrix-test-user.env
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env whoami
ROOM="$(python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env create-dm @hermes:garden.home.arpa)"; echo "$ROOM"
echo "MATRIX_ALLOWED_ROOMS=$ROOM" >> ~/.hermes/.env
```

Expected: `@<user>:garden.home.arpa`、続いて `!...:garden.home.arpa` の部屋 ID

- [ ] **Step 4: gateway を再起動して、Matrix と Telegram の両方が接続中か見る**

```bash
systemctl --user restart hermes-gateway.service
sleep 10
systemctl --user is-active hermes-gateway.service
journalctl --user -u hermes-gateway.service --since "-2 min" --no-pager | grep -i -E 'matrix|telegram|error|warn' | head -40
```

Expected: `active`。ログに Matrix の接続（`@hermes:garden.home.arpa` としてログインした・同期を始めた）と Telegram の接続の両方の行がある。招待を受けて部屋に入った行もあるとよい

- [ ] **Step 5: Hermes が招待を受けたか確かめ、受けていなければ入れる**

```bash
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env messages "$ROOM" --limit 20
journalctl --user -u hermes-gateway.service --since "-3 min" --no-pager | grep -i -E 'invite|join' | head
```

Hermes が入っていない（ログに join が無い）ときだけ:

```bash
python3 ~/matrix_helper.py --token-file ~/.hermes/.env join "$ROOM"
```

Expected: 部屋 ID が表示される

- [ ] **Step 6: 文字だけで頼む**

```bash
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env send-text "$ROOM" "garden-app の API の health を確認して、結果だけ教えて"
sleep 60
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env messages "$ROOM" --limit 5
```

Expected: `@hermes:garden.home.arpa: ...` の返信があり、health が正常だと言っている（返信がまだなら、もう一度 `messages` を実行する）

- [ ] **Step 7: 画像付きで頼む**

メイン PC からテスト用の写真（JPEG）を1枚送る（PowerShell。ファイル名は例）:

```powershell
scp C:\path\to\test-leaf.jpg <user>@<サーバーのIP>:~/test-leaf.jpg
```

サーバーで:

```bash
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env send-image "$ROOM" ~/test-leaf.jpg --caption "この写真を写真プールに登録して。登録したら写真プールの ID を教えて"
sleep 90
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env messages "$ROOM" --limit 5
journalctl --user -u hermes-gateway.service --since "-3 min" --no-pager | grep -i -E 'image|media|cache|error' | head -20
```

Expected: Hermes の返信に写真プールの ID がある。ログに画像を受け取ってファイルに保存した行があり、エラーが無い。Web 画面の写真プール（`http://<サーバーのIP>:5000/photo_pool/`）にその写真がある（確認後、Web 画面から削除してよい）

- [ ] **Step 8: 後片付け**

```bash
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env logout
rm ~/.config/matrix-test-user.env ~/test-leaf.jpg
grep '^MATRIX_ALLOWED_ROOMS' ~/.hermes/.env
```

Expected: `ログアウトした`。部屋 ID の行が残っている（Task 7 で使う）

**失敗したとき:**
- Step 4 で Matrix に接続できない → gateway のログのエラーを Claude が読む。Tuwunel 側の拒否（`M_UNKNOWN_TOKEN`、未対応のエンドポイントの 404 など）なら、Tuwunel の版と既知の問題を調べる
- Step 7 で画像を取れない（認証付きメディアの 404/401）→ Tuwunel の `allow_legacy_media` などで直るか調べる
- 直らなければ Synapse に切り替える（設計書の「Tuwunel では動かないと分かりうる段階」）。いったん戻すときは `cp -p ~/.hermes/.env.bak-before-matrix ~/.hermes/.env` → `systemctl --user restart hermes-gateway.service` で Telegram だけの状態に戻る

---

### Task 7: 段階5 iPhone に証明書を入れ、Element X でログインする

- [ ] **Step 1: 発行元の証明書をメイン PC に取ってくる**

サーバーで:

```bash
sudo -v
sudo cp /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/garden-ca.crt
sudo chown "$USER": ~/garden-ca.crt
openssl x509 -in ~/garden-ca.crt -noout -subject -enddate -fingerprint -sha256
```

Expected: `subject=CN = Caddy Local Authority - 20xx ECC Root`、有効期限が約10年後、SHA-256 の指紋（Step 3 で iPhone の表示と見比べる）。これは公開してよい証明書で、秘密鍵ではない

メイン PC の PowerShell:

```powershell
scp <user>@<サーバーのIP>:~/garden-ca.crt $env:USERPROFILE\Downloads\garden-ca.crt
```

- [ ] **Step 2: iPhone に届ける**

メイン PC から iPhone に `garden-ca.crt` を送る（自分宛てのメールの添付、または iCloud Drive の Web 画面にアップロード）。iPhone で開くと「プロファイルがダウンロードされました」と出る

- [ ] **Step 3: iPhone で入れて信頼する**

1. 設定 → 一般 → VPN とデバイス管理 → ダウンロード済みプロファイル → インストール
2. 「詳細」で SHA-256 の指紋が Step 1 と同じことを確かめる
3. 設定 → 一般 → 情報 → 証明書信頼設定 → 「Caddy Local Authority ...」をオンにする

確認: iPhone の Safari で `https://<サーバーのIP>:8448/_matrix/client/versions` を開くと、警告なしで JSON が表示される

- [ ] **Step 4: Element X でログインする**

1. App Store から Element X を入れる
2. サインイン → アカウントのサーバーを変更 → `https://<サーバーのIP>:8448`
3. `<user>` と、Task 5 で作ったパスワードでログインする

Expected: ログインでき、部屋の一覧に Task 6 の部屋（Hermes）が出て、Task 6 のやりとりが見える

- [ ] **Step 5: 文字で話す**

Element X の Hermes の部屋で「作物の一覧を3件だけ教えて」と送る。Expected: Hermes が返信する

**失敗したとき:**
- サーバーを変更する画面で弾かれる → Tuwunel の `[global.well_known]` の `client = "https://<サーバーのIP>:8448"` を足して再起動し、もう一度試す
- ログインはできたが一覧が出ない・読み込みが終わらない（Sliding Sync の問題）→ `journalctl -u tuwunel` のエラーを Claude が読む。直らなければ Synapse に切り替える

---

### Task 8: 段階6 iPhone から写真付きで頼む

- [ ] **Step 1: 写真付きで栽培記録の登録を頼む**

Element X の Hermes の部屋で、カメラロールの写真を1枚選び、「この写真で〈栽培中の植え付けの名前〉の栽培記録を今日の日付で登録して。メモは『Matrix からのテスト』」と送る（写真の送信設定は既定のまま）

- [ ] **Step 2: 受け取った形式を見る（サーバー）**

```bash
journalctl --user -u hermes-gateway.service --since "-5 min" --no-pager | grep -i -E 'image|media|mime|heic|jpeg|cache|error|reject' | head -30
```

Expected: 画像を受け取ってファイルに保存した行があり、形式は JPEG（`image/jpeg`）。Hermes の返信に登録した栽培記録の ID がある

- [ ] **Step 3: アプリで確かめる**

Web 画面の植え付けの詳細で、写真付きの栽培記録が増えていることを確かめる（テストなので、確認後に削除してよい）

**失敗したとき:** HEIC のまま届いて断られた場合は、Element X の写真送信の設定（画像の最適化・圧縮）を変えて試す。それでもだめなら、Hermes の Matrix アダプターの形式チェック（`adapter.py` の画像の受け取り）を Claude が調べ、別の作業として扱う

---

### Task 9: 段階7 仕上げ（サーバー・iPad・文書）

- [ ] **Step 1: セッションの区切り方を確かめる**

Element X の Hermes の部屋で `/new` を送る。Element X に弾かれる・効かない場合は `!new` を送る。Expected: Hermes が新しいセッションを始めた旨を返す。gateway のログで、新しいセッションになったことを確かめる

- [ ] **Step 2: iPad にも入れる**

Task 7 Step 2〜4 を iPad で行う（同じ `<user>` でログイン）。Expected: iPad からも Hermes と話せる

- [ ] **Step 3: 発行元の鍵を root だけが読める場所にコピーする**

```bash
sudo -v
sudo tar -C /var/lib/caddy/.local/share/caddy -czf /root/caddy-pki-backup-$(date +%Y%m%d).tgz pki
sudo chmod 600 /root/caddy-pki-backup-*.tgz
sudo ls -l /root/caddy-pki-backup-*.tgz
rm ~/garden-ca.crt
```

Expected: `-rw------- 1 root root ...` のファイルが1つ

- [ ] **Step 4: 再起動して戻ることを確かめる**

```bash
sudo reboot
```

起動後（数分待って入り直す）:

```bash
systemctl is-active tuwunel caddy garden-app; systemctl --user is-active hermes-gateway
journalctl --user -u hermes-gateway.service -b --no-pager | grep -i -E 'matrix|telegram' | head -10
curl -s -o /dev/null -w '%{http_code}\n' --connect-timeout 5 http://127.0.0.1:5000/ || true
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:2019/config/ || true
```

Expected: `active` が4つ。gateway のログで Matrix と Telegram の両方が接続している。`<user>` からの 5000 は `000`（遮断が残っている）。2019 も `000`。iPhone の Element X から送ると Hermes が返信する

- [ ] **Step 5: 文書を更新する（メイン PC）**

- `docs/api/hermes-local-chat.md`: 「調査と方針」から、構成・構築手順（Task 3〜7 のコマンドを記号で）・更新の手順・戻し方の文書に書き換える。Synapse に切り替えた場合はそれを書く
- `CLAUDE.md`: 外部API の段落の Hermes の説明に「スマホからは Telegram と、LAN 内の Matrix（Tuwunel＋Element X、`docs/api/hermes-local-chat.md`）の両方で依頼できる」を足す
- `docs/api/hermes-skill/SKILL.md`: Task 8・9 で Matrix 固有の注意（形式・`/new` の書き方など）が見つかったときだけ足す
- `docs/wishlist.md`: 「Telegram を使わず…」の行を「Matrix の部屋で E2EE を試す」に書き換える
- `docs/known-issues.md`: 「cron のバックアップはサーバーが 3:15 に止まっているとその日の分が抜ける（対応案: systemd タイマーの `Persistent=true`）」を足す
- `docs/dev-workflow-tips.md`: 作業中に分かった進め方のノウハウがあれば足す
- コミット前に local-env.md の固有値（IP・ユーザー名）で `grep` して出てこないことと、`git diff --stat` で改行コードが変わっていないことを確かめる

```bash
git add docs/api/hermes-local-chat.md CLAUDE.md docs/wishlist.md docs/known-issues.md
git status --short
git commit -m "LAN 内の Matrix で Hermes に依頼できるようにした構成と手順を記録する"
```

- [ ] **Step 6: 非公開の記録を更新する**

- `../garden-app-private/local-env.md`: Tuwunel（`tuwunel.service`、`/etc/tuwunel/tuwunel.toml`、`/var/lib/tuwunel`、127.0.0.1:8008）、Caddy（`/etc/caddy/Caddyfile`、8448、管理 API なし、発行元の鍵のバックアップの場所）、ufw の 8448、Matrix のアカウント、Hermes の `.env` の MATRIX_ の項目名、`.env.bak-before-matrix`
- `../garden-app-private/worklog/2026-10-18-hermes-matrix.md` を書き、`next.md` を更新してコミットする

- [ ] **Step 7: PR を作る**

ブランチ `docs/hermes-matrix-design` を push して PR を作る。マージはユーザーに頼む
