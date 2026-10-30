# Hermes に聞くパネル

植え付け・作物・品種の詳細画面で、右から開くパネルから Hermes に質問できる。ブラウザはアプリの中継（`/hermes/ask`、`app/routes/hermes_ask_routes.py`）だけに話し、Hermes にも `HERMES_API_KEY` にも触れない。

## 部品

- `app/templates/_hermes_ask_panel.html`: 右下の固定ボタン「Hermes に聞く」と Bootstrap 5 の `offcanvas offcanvas-end`（`data-bs-scroll="true" data-bs-backdrop="false"`＝開いたまま画面をスクロールできる）。中で `hermes_ask_enabled()`（ログイン中かつキー設定済み）を判定するので、呼ぶ側は `is_owner()` で囲まなくてよい
- `app/static/js/hermes-ask.js` / `app/static/css/hermes-ask.css`: 部品の中で読み込む（`extra_js` に手を入れない）。Bootstrap の JS は body の最後で読まれるため、`DOMContentLoaded` を待ってから動く
- 呼び方（各詳細画面の `content` ブロックの末尾）:

```html
{% set hermes_ask_target = ('planting', location_crop.id) %}{% include '_hermes_ask_panel.html' %}
```

作物は `('crop', crop.id)`、品種は `('variety', variety.id)`。対象はパネルの `data-entity-type` / `data-entity-id` に出る。

### data 属性（パネル以外でも使える）

`hermes-ask.js` は `[data-hermes-ask]` の要素ごとに動く（中に `data-hermes-messages` / `-input` / `-send` / `-error` / `-context` / `-new` を持つこと）。URL は要素の data 属性で受け取る:

- `data-history-url`: 履歴の取得先。無ければ履歴を読まず、すぐ送れる（新しい会話）。返る `target` が null のときは対象の行を空にする。`kind_label` が null（対象が消えたパネルの会話をチャット画面で開いた）なら `label`（「（削除済み）」）だけを出す
- `data-runs-url`: 送る先
- `data-new-url`: 「新しく始める」の送り先。無ければ `data-hermes-new` のボタンを探さない
- `data-autoload`: あればすぐ履歴を読む。無ければ `show.bs.offcanvas`（パネルを開いたとき）に読む
- 承認・events は常に `/hermes/ask/runs/<run_id>/…`
- 送った応答に `chat_id` があれば（新しい会話）、以後の送り先を `/hermes/ask/chats/<chat_id>/runs` に変え、`history.replaceState` で URL を `chat_url` にし、要素に `hermes:chat-created`（`detail`: `chat_id` / `chat_url` / `title`、`bubbles`）を投げる
- `done` / `failed` のあとに `hermes:run-finished`（`bubbles`）を投げる（一覧の時刻の更新用）

パネルは `data-history-url` / `data-runs-url` / `data-new-url` を `/hermes/ask/<type>/<id>/…` で出す（`id="hermes-ask-panel"` と `data-entity-*` も残す）。

## 振る舞い

- 初めて開いたときだけ `GET /hermes/ask/<type>/<id>/history` で吹き出しを並べる。`running_run_id` があれば events につなぐ。履歴を読み込み終わるまで「送る」は押せない（先に送ると、後から届いた履歴が吹き出しを消すため）。履歴の取得に失敗したらエラーを出したうえで送れるようにする
- 「― 今日 ―」の区切りは、最後の区切りが今日でないときだけ足す
- 送る: `POST .../runs`（`request_key` は `crypto.randomUUID()`）→ `EventSource` で `/hermes/ask/runs/<run_id>/events`。イベントは `tool`（灰色の1行、最後の1行だけ残す）・`delta`（答えの吹き出しに `textContent` で足す）・`approval`（「許可する」`once`／「しない」`deny` だけ。コマンドは `textContent`。`request_id` ごとに1つの塊にし、同じものが流れ直しても二重に出さない）・`approval_done`（その `request_id` の塊のボタンを消して「返事済み」にする。Hermes はつなぎ直すと event を最初から流し直すため、画面を移って戻っても返事済みのボタンを出し直さない）・`done`（吹き出しをサーバーが作った `html` に置き換え、`links`（作った・変えた・見たデータ）を付ける。履歴（`/history`）の各回の最後の答えにも `links` が付き、開き直しても同じリンクを出す）・`failed`（赤い文字）
- 失敗（503 など）は入力欄の上に `error` を出し、入力した文は消さない
- 「新しく始める」は確認なしで `POST .../new` し、吹き出しを空にする
- `done` / `failed` のあとは必ず `EventSource` を閉じる（閉じないと自動で再接続して同じ run をもう一度流す）

## 守ること

- `innerHTML` に入れてよいのは `history` / `done` の `html`（サーバーで Markdown を変換したもの）だけ。`delta`・コマンド・エラー文は `textContent`
- キー（`HERMES_API_KEY`）を HTML・JS・JSON に出さない（テストで確認している）
- fetch の `X-CSRFToken` は `csrf.js` が自動で付ける（`EventSource` は GET なので不要）
- パネルの幅は `width` ではなく `--bs-offcanvas-width` で指定する（Bootstrap の `.offcanvas.offcanvas-end { width: var(--bs-offcanvas-width) }` のほうが強く、`width` は効かない）
- 新しい CDN は足さない
