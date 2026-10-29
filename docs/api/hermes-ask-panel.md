# Hermes に聞くパネル（本番の設定と運用）

植え付け・作物・品種の詳細画面から Hermes に質問するパネルを、本番で動かすための設定と確かめ方。設計は [`../superpowers/specs/2026-10-29-hermes-ask-panel-design.md`](../superpowers/specs/2026-10-29-hermes-ask-panel-design.md)、画面の部品は [`../frontend/hermes-ask-panel.md`](../frontend/hermes-ask-panel.md)。

固有値は記号で書く（`<サーバーのIP>`、`<Hermes の実行ユーザー>`）。実際の値はリポジトリ外の `local-env.md`。サーバーの操作は、手順を示してユーザーが実行する。

## 仕組み

```
ブラウザ（パスキーでログイン中）
  → アプリ（Flask、garden ユーザー）  /hermes/ask/...（ログイン必須・CSRF 照合）
  → Hermes の API Server（127.0.0.1:8642、Hermes の実行ユーザーの gateway と同じプロセス）
  → Hermes が curl でアプリの API（Bearer トークン）を読む・書く
```

- アプリが Hermes の events（SSE）を中継してブラウザに流す。キー（`HERMES_API_KEY`）はアプリのサーバーの `.env` にだけ置き、ブラウザには渡さない
- 追加で増えるデータの流れは「アプリ → Hermes の API Server」だけ。「Hermes → アプリ」は今までの API と会話の同期のまま
- パネルでの会話は、会話の同期（[`hermes-conversation-sync.md`](hermes-conversation-sync.md)）が `source = 'api_server'` として `/conversations/` に取り込む

## 設定

| どこ | 項目 | 値 |
|---|---|---|
| Hermes の `~/.hermes/.env` | `API_SERVER_ENABLED` | `true` |
| 同上 | `API_SERVER_KEY` | ランダムな値（32文字以上） |
| アプリの `/opt/garden-app/.env` | `HERMES_API_KEY` | `API_SERVER_KEY` と同じ値。未設定ならパネルを出さない |
| 同上 | `HERMES_API_URL` | 既定 `http://127.0.0.1:8642`（変えない） |

## 手順

### 1. Hermes の API Server を有効にする（<Hermes の実行ユーザー> で）

2026-10-29 に実施済み。やり直すときの手順。`.env` を変える前に控えを取る。

```bash
cp ~/.hermes/.env ~/.hermes/.env.bak-before-api-server
```

キーを作って足す。画面に出さずに書き込む（シェルの履歴にも残さない）。

```bash
python3 - <<'PY'
import os, secrets
with open(os.path.expanduser('~/.hermes/.env'), 'a') as f:
    f.write('\nAPI_SERVER_ENABLED=true\nAPI_SERVER_KEY=' + secrets.token_urlsafe(32) + '\n')
PY
systemctl --user restart hermes-gateway.service
```

キーの値は `~/.hermes/.env` から読んで、次の 2 の `HERMES_API_KEY` に同じ値を入れる（チャットや文書に貼らない）。

### 2. アプリに同じキーを入れる（アプリのサーバーで）

`/opt/garden-app/.env` に `HERMES_API_KEY=<1 と同じ値>` を足し、アプリを再起動する。

```bash
sudo systemctl restart garden-app
```

### 3. 同期スクリプトを送り直す

`api_server` の会話も取り込むよう変えたので、メイン PC から送り直す（[`hermes-conversation-sync.md`](hermes-conversation-sync.md) の「配置」）。

```bash
scp tools/hermes_conversation_sync.py <Hermes の実行ユーザー>@<サーバーのIP>:~/
```

### 4. SKILL.md を送り直す

「アプリのパネルからの相談」の節を足したので、Hermes のスキルを入れ替える（手順は既存のスキルの更新と同じ）。

## 確かめ方

```bash
ss -ltnp | grep 8642                                    # 127.0.0.1:8642 だけ（0.0.0.0 や LAN の IP が出たら失敗）
sudo -u garden curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8642/health   # 200
sudo -u garden curl -sS -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8642/v1/runs   # 401（キー無し）
```

- Element X に話しかけて、今までどおり返事が来る
- ログインして植え付けの詳細を開き、右下の「Hermes に聞く」から質問して答えが出る。キーを設定していない／未ログインではボタンが出ない
- しばらくして `/conversations/` に「アプリ」の印付きで並ぶ（同期は15分おき）

## 注意

- **パスキーでログインした人は、Hermes にできることを何でも頼める**（ターミナルを含む道具は Element X の経路と同じ。承認待ちはパネルで「許可する」「しない」を返せる）。自分だけがログインできることが前提なので、パスキーの管理（設定画面）を今までどおり丁寧に行う
- **8642 番を LAN に開けない**。`127.0.0.1` だけで待ち受ける状態を保つ。ufw にも許可を足さない
- `NOPASSWD` を足さない、Hermes の遮断（Hermes の実行ユーザーから 5000・443 番）を外さない、Caddy の転送先を増やさない（[`migration-to-ubuntu.md`](migration-to-ubuntu.md)）
- キーが漏れた疑いがあるときは、`API_SERVER_KEY` と `HERMES_API_KEY` を作り直して gateway とアプリを再起動する
- 同時に動く run は最大 10（超えると 429）
- Hermes を更新（`hermes update`）したあとは、上の確かめ方と Element X の返事を確かめる

## うまくいかないとき

| 症状 | 確認すること |
|---|---|
| パネルのボタンが出ない | ログインしているか、`/opt/garden-app/.env` の `HERMES_API_KEY`、アプリの再起動 |
| 「Hermes に届きません」 | `systemctl --user status hermes-gateway.service`、`ss -ltnp \| grep 8642`、`HERMES_API_URL` |
| 401 が続く | 2 つの `.env` のキーが一致しているか（前後の空白・改行）、変えたあとに両方再起動したか |
| 一覧に「アプリ」の会話が出ない | 同期スクリプトを送り直したか、`python3 ~/hermes_conversation_sync.py --dry-run` に `api_server` の会話が出るか |
