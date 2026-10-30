# Hermes とのチャット画面

ログイン中の自分が、対象のない会話をいくつでも Hermes と続けられる画面（`/hermes/chat/`）。詳細画面の「Hermes に聞く」パネルでした会話も一覧に並び、ここから続けられる。設計は `docs/superpowers/specs/2026-10-30-hermes-chat-design.md`。

## 部品

- ルート: `app/routes/hermes_chat_routes.py`（Blueprint `hermes_chat`）
  - `GET /hermes/chat/` → `hermes_chat.index`: 右は新しい会話（`data-runs-url="/hermes/ask/chats/runs"`、`data-history-url` なし）
  - `GET /hermes/chat/<chat_id>` → `hermes_chat.show`: 右はその会話（`data-history-url` / `data-runs-url` は `/hermes/ask/chats/<id>/…`、`data-autoload`）。無い id は 404
  - `POST /hermes/chat/<chat_id>/rename`（`title`、前後の空白・改行を詰めて1〜200文字。外れたら flash でエラー）→ `show` へ戻る
  - `POST /hermes/chat/<chat_id>/delete` → `HermesChat.delete` が返した写真を `delete_image` で消し、flash「会話を削除しました」→ `index`。写真が消せなくても（`OSError`）警告のログだけで成功にする（会話はコミット済み）。無い id は 404
- テンプレート: `app/templates/hermes_chat/index.html`（`index` と `show` で共用。`chat` が None なら新しい会話）
- JS: 吹き出し・入力欄は `hermes-ask.js`（`[data-hermes-ask]`、data 属性は `docs/frontend/hermes-ask-panel.md`）。一覧への差し込みなど画面だけの動きは `app/static/js/hermes-chat.js`
- CSS: 吹き出しは `hermes-ask.css`、画面の並びは `app/static/css/hermes-chat.css`

## 画面

- 上に `_hermes_tabs.html`（`hermes_tab = 'chat'`）。タブの先頭の「チャット」は `hermes_ask_enabled()`（ログイン中かつ `HERMES_API_KEY` 設定済み）のときだけ出す
- 左（`col-md-3`）: 「＋ 新しい会話」と `HermesChat.list_for_chat()` の行（最後に使った順）。1行に題名（`display_title`）・最後の時刻（`MM/DD HH:MM`）・パネルの会話なら対象の印（`植え付け: …`、対象が消えていれば「（削除済み）」）。選んでいる行は `active`
- 右（`col-md-9`）: 見出しに題名、鉛筆のボタンで見出しの下に題名変更のフォーム（Bootstrap の collapse）、ごみ箱で削除（`confirm` で確かめる）。下はパネルと同じ吹き出しと入力欄
- ナビの「Hermes」は `hermes_ask_enabled()` ならチャット画面、そうでなければ会話の一覧へ。`hermes_chat.` も active にする
- キー未設定のときは画面は開けるが、右に「Hermes への接続が設定されていません」と出し、入力欄と JS を出さない
- スマホ幅（`md` 未満）: 一覧を上（高さ 30vh でスクロール）、会話を下に積む。会話の欄は `calc(100vh - …)` で画面に収め、吹き出しの欄だけスクロールする

## 振る舞い

- 新しい会話で最初に送ると、`hermes-ask.js` が URL を `chat_url` にして `hermes:chat-created` を投げる。`hermes-chat.js` はそれを受けて、一覧の先頭に新しい行を差し込んで選んだ状態にし、見出しの題名を入れ、題名変更・削除のフォームの送り先を `chat_url + '/rename'` / `'/delete'` にして出す
- `hermes:run-finished` で、選んでいる行の時刻を今にして一覧の先頭へ移す
- 二重に送らない: 送る道は `hermes-ask.js` の `send()` だけ（`busy` の間は送れない）。新しい会話の最初の送信が `chat_id` を返すまで次は送れないので、対象なしの会話が2つできない。この画面に別の送る道を足さない

## 守ること

- 題名はユーザーの入力から作られる。JS では `textContent` で入れる（テンプレートは Jinja の自動エスケープ）
- GET の endpoint は `OWNER_ONLY_GET_ENDPOINTS` に入れる。名前に `list` / `detail` を使わない（`tests/test_auth_gate.py` の閲覧用の形に当たる）
- キー（`HERMES_API_KEY`）を HTML・JS に出さない（テストで確認している）
- 削除で消えるのはアプリの会話の行と会話の履歴（写真を含む）だけ。Hermes の中の記録とアドバイスは残る（確認の文言もそう書いている）
