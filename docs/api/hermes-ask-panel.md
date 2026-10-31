# Hermes に聞くパネル（本番の設定と運用）

植え付け・作物・品種の詳細画面から Hermes に質問するパネルを、本番で動かすための設定と確かめ方。設計は [`../superpowers/specs/2026-10-29-hermes-ask-panel-design.md`](../../../garden-app-private/docs/superpowers/specs/2026-10-29-hermes-ask-panel-design.md)、画面の部品は [`../frontend/hermes-ask-panel.md`](../frontend/hermes-ask-panel.md)。

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

アプリ本体の反映（パネルの画面とマイグレーション 026）は、ほかの変更と同じく [`migration-to-ubuntu.md`](migration-to-ubuntu.md) の「9. 更新の手順」で行う。ここではそれに加える Hermes 側とキーの設定を書く。

### 1. Hermes の API Server を有効にする（<Hermes の実行ユーザー> で）

2026-10-29 に実施済み。やり直すときの手順。`.env` を変える前に控えを取る。やり直すときは、先に `~/.hermes/.env` の既存の `API_SERVER_ENABLED` と `API_SERVER_KEY` の行を消しておく（下のスクリプトは行を足すだけなので、そのままだと二重になる）。

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

「アプリのパネルからの相談」の節を足したので、Hermes のスキルを入れ替える。送る前にサーバーの版を取ってきて比べ、Hermes の追記を取り込んでから送る（手順は [`hermes-telegram.md`](../../../garden-app-private/docs/api/hermes-telegram.md) の「Hermes の自己改善（SKILL.md と USER.md の書き換え）」。Telegram 時代の記録だが Matrix でも同じ）。送ったら Element X で `/new` してから試す（Hermes は SKILL.md をセッションの最初に読むので、続いている会話は古い内容のまま。[`hermes-local-chat.md`](hermes-local-chat.md) の「使い方」）。

## 確かめ方

```bash
ss -ltnp | grep 8642                                    # 127.0.0.1:8642 だけ（0.0.0.0 や LAN の IP が出たら失敗）
sudo -u garden curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8642/health   # 200
sudo -u garden curl -sS -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8642/v1/runs   # 401（キー無し）
```

- Element X に話しかけて、今までどおり返事が来る
- ログインして植え付けの詳細を開き、右下の「Hermes に聞く」から質問して答えが出る。キーを設定していない／未ログインではボタンが出ない
- しばらくして `/conversations/` に「アプリ」の印付きで並ぶ（同期は15分おき）
- 「新しく始める」で止まるか: 時間のかかる依頼を送り、**灰色の「⚙ …」の行が出ている間に**押す。答えの文字が流れ始めたころには、Hermes は登録などの作業を済ませて答えを書いているだけなので、止めても取り消せるものが無く、確かめにもならない（2026-10-31 は最初の2回とも答えが出始めてから押し、run は止める前に completed になっていた）。止まったかは `gateway.log` には出ない（stop の要求は INFO で記録されない）ので、run の状態を聞く（終わった run の状態は1時間で消える）:

  ```bash
  RUN=$(sudo -u garden sqlite3 -readonly /opt/garden-app/instance/garden.db "SELECT last_run_id FROM hermes_chats WHERE active = 0 AND entity_type IS NOT NULL ORDER BY id DESC LIMIT 1"); echo "$RUN"; KEY=$(grep '^API_SERVER_KEY=' ~/.hermes/.env | cut -d= -f2-); curl -s -H "Authorization: Bearer $KEY" "http://127.0.0.1:8642/v1/runs/$RUN" | grep -oE '"(status|interrupted|completed)": "?[a-z]+"?|"(created_at|updated_at)": [0-9.]+'
  ```

  `"status": "cancelled"` と `"interrupted": true` なら止まっている。`hermes_chats.last_used_at` は答えを受け取ったとき（`run.completed`）にも更新されるので、切り替えた時刻（次の会話の行の `created_at`）より前なら、止める前に終わっていた

## 注意

- **パスキーでログインした人は、Hermes にできることを何でも頼める**（ターミナルを含む道具は Element X の経路と同じ。承認待ちはパネルで「許可する」「しない」を返せる）。自分だけがログインできることが前提なので、パスキーの管理（設定画面）を今までどおり丁寧に行う
- **8642 番を LAN に開けない**。`127.0.0.1` だけで待ち受ける状態を保つ。ufw にも許可を足さない
- `NOPASSWD` を足さない、Hermes の遮断（Hermes の実行ユーザーから 5000・443 番）を外さない、Caddy の転送先を増やさない（[`migration-to-ubuntu.md`](migration-to-ubuntu.md)）
- キーが漏れた疑いがあるときは、`API_SERVER_KEY` と `HERMES_API_KEY` を作り直して gateway とアプリを再起動する
- 同時に動く run は最大 10（超えると 429）
- Hermes を更新（`hermes update`）したあとは、上の確かめ方と Element X の返事を確かめる

## 取りやめるとき

- **パネルだけ消す**: アプリの `/opt/garden-app/.env` から `HERMES_API_KEY` の行を消し、`sudo systemctl restart garden-app`。キーが無いとパネルのボタンは出ず、`/hermes/ask` も 503 を返す
- **Hermes の API Server も止める**: 上に加えて、<Hermes の実行ユーザー> で `~/.hermes/.env` の `API_SERVER_ENABLED` を `false` にし（または `API_SERVER_ENABLED` と `API_SERVER_KEY` の行を消し）、`systemctl --user restart hermes-gateway.service`。`ss -ltnp | grep 8642` で何も出ないこと、Element X で返事が来ることを確かめる

## チャット画面（`/hermes/chat/`）

チャット画面も同じ API Server と同じ `HERMES_API_URL` / `HERMES_API_KEY` を使う。本番の設定は増えず、変わりも無い（`.env` も ufw も Caddy もそのまま）。`HERMES_API_KEY` を消せばパネルと一緒にチャット画面も使えなくなる。画面の部品は `docs/frontend/hermes-chat.md`。

## うまくいかないとき

| 症状 | 確認すること |
|---|---|
| パネルのボタンが出ない | ログインしているか、`/opt/garden-app/.env` の `HERMES_API_KEY`、アプリの再起動 |
| 「Hermes に届きません」 | `systemctl --user status hermes-gateway.service`、`ss -ltnp \| grep 8642`、`HERMES_API_URL` |
| 401 が続く | 2 つの `.env` のキーが一致しているか（前後の空白・改行）、変えたあとに両方再起動したか |
| 「前の質問はいつ？」に答えられない | Hermes に渡る会話の履歴には発言の日時が無い（2026-10-30 に確認）ので、2回目以降の質問では、アプリが Hermes の記録（`get_session_messages`）から「これまでの質問」（新しい方から 10 件、書き出し 40 文字、日本時間）を取り出して指示の最後に添えている（`hermes_context.earlier_questions`）。記録を読めなかったときは添えずに送る。答えられないときは、送った指示に「この会話のこれまでの質問」が入っているかを見る |
| 一覧に「アプリ」の会話が出ない | 同期スクリプトを送り直したか、`python3 ~/hermes_conversation_sync.py --dry-run` に `api_server` の会話が出るか |
