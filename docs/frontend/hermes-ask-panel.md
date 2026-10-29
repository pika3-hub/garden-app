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

## 振る舞い

- 初めて開いたときだけ `GET /hermes/ask/<type>/<id>/history` で吹き出しを並べる。`running_run_id` があれば events につなぐ
- 送る: `POST .../runs`（`request_key` は `crypto.randomUUID()`）→ `EventSource` で `/hermes/ask/runs/<run_id>/events`。イベントは `tool`（灰色の1行、最後の1行だけ残す）・`delta`（答えの吹き出しに `textContent` で足す）・`approval`（「許可する」`once`／「しない」`deny` だけ。コマンドは `textContent`）・`done`（吹き出しをサーバーが作った `html` に置き換え、`links` を付ける）・`failed`（赤い文字）
- 失敗（503 など）は入力欄の上に `error` を出し、入力した文は消さない
- 「新しく始める」は確認なしで `POST .../new` し、吹き出しを空にする
- `done` / `failed` のあとは必ず `EventSource` を閉じる（閉じないと自動で再接続して同じ run をもう一度流す）

## 守ること

- `innerHTML` に入れてよいのは `history` / `done` の `html`（サーバーで Markdown を変換したもの）だけ。`delta`・コマンド・エラー文は `textContent`
- キー（`HERMES_API_KEY`）を HTML・JS・JSON に出さない（テストで確認している）
- fetch の `X-CSRFToken` は `csrf.js` が自動で付ける（`EventSource` は GET なので不要）
- パネルの幅は `width` ではなく `--bs-offcanvas-width` で指定する（Bootstrap の `.offcanvas.offcanvas-end { width: var(--bs-offcanvas-width) }` のほうが強く、`width` は効かない）
- 新しい CDN は足さない
