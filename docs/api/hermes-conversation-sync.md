# Hermes の会話をアプリに送る（会話の履歴）

Hermes と Matrix（Element X）でした会話を、アプリの「Hermes との会話」画面（`/conversations/`）と各データの詳細画面で見られるようにするための、同期スクリプトの配置と運用の手順。設計は [`../superpowers/specs/2026-10-26-hermes-conversations-design.md`](../superpowers/specs/2026-10-26-hermes-conversations-design.md)、API の仕様は [`README.md`](README.md) の「会話の履歴（同期スクリプト専用）」。

固有値は記号で書く（`<サーバーのIP>`、`<user>` = Hermes の実行ユーザー）。実際の値はリポジトリ外の `local-env.md`。サーバーの操作は、手順を示してユーザーが実行する。

## 役割と流れ

```
[サーバー: Hermes の実行ユーザー]                    [サーバー: アプリ（garden）]
systemd ユーザータイマー（15分おき）
  → ~/hermes_conversation_sync.py
      ~/.hermes/state.db を読み取り専用で開く
      Matrix の会話のうち、前回から増えた・変わったもの
      写真の印があれば ~/.hermes/cache/images のファイル
  → POST $GARDEN_API_URL/conversations  ──────→  API（127.0.0.1:API_PORT）
                                                  会話・発言を Hermes の ID で上書き保存
                                                  写真は縮小版だけ保存
                                                  データとの結び付けを作り直す
                                                Web 画面: 一覧・詳細・各詳細画面の欄
```

- データの流れは Hermes → API だけ。アプリは `~/.hermes` を読まず、Hermes にも接続しない（サーバーの遮断を崩さない）
- スクリプトは標準ライブラリだけの Python（サーバーの `python3`）。`state.db` は読み取り専用（`mode=ro`）で開く。取り込むのは `source` が `matrix`（Element X）と `api_server`（アプリの「Hermes に聞く」パネル）の会話だけ（`cli` などは取り込まない）。API Server の会話は圧縮でセッション ID が変わることがあるので、ID での絞り込みはしない。このスクリプトを変えたら、下の「配置」の手順でサーバーに送り直す
- 接続先とトークンは `~/.config/garden-api.env`（`GARDEN_API_URL` と `GARDEN_API_TOKEN`）。Hermes の gateway と同じファイルで、ログにはトークンも発言の本文も出さない
- 送った状態は `~/.local/state/garden-conversation-sync.json` に持つ（会話ごとの指紋と送り済みの写真名）。前回から変わっていない会話は送らない
- 写真は 1 リクエスト 20 枚まで。残りがあれば次の回に続きを送る
- **写真は Hermes が 24 時間で消す**（`~/.hermes/cache/images/` の掃除）。タイマーを 15 分おきにしているのはそのため。止めて 24 時間以上あくと、その間に撮った写真はアプリに届かず、会話の画面では「写真あり」の表示になる

## 配置

メイン PC から、リポジトリの版をサーバーのホームに送る。

```bash
scp tools/hermes_conversation_sync.py <user>@<サーバーのIP>:~/
```

サーバー（`<user>` でログインして）で、まず送らずに対象を確かめる。

```bash
python3 ~/hermes_conversation_sync.py --dry-run
```

`[dry-run] <会話ID> 発言 <件数> 写真 <枚数>` の行が Matrix の会話の数だけ出ればよい（`state.db` の列が足りないときは `エラー: state.db に必要な列がありません…` で止まる）。次に最初の取り込みを実行する。

```bash
python3 ~/hermes_conversation_sync.py
```

会話ごとに `<会話ID> 発言 <件数> 写真 <枚数> HTTP 201`（更新は 200）が出れば成功。終了コードは、失敗した会話があれば 1、なければ 0。アプリの `/conversations/` に並ぶことを確かめる。

主な引数（既定は `~` 基準）: `--db`（`~/.hermes/state.db`）、`--state`（`~/.local/state/garden-conversation-sync.json`）、`--env`（`~/.config/garden-api.env`）、`--cache-dir`（`~/.hermes/cache/images`）、`--dry-run`。

## タイマー（systemd ユーザーサービス）

`~/.config/systemd/user/garden-conversation-sync.service`:

```ini
[Unit]
Description=Hermes の会話をアプリに送る

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 %h/hermes_conversation_sync.py
```

`~/.config/systemd/user/garden-conversation-sync.timer`:

```ini
[Unit]
Description=Hermes の会話をアプリに送る（15分おき）

[Timer]
OnCalendar=*:0/15
Persistent=true

[Install]
WantedBy=timers.target
```

有効にする。

```bash
systemctl --user daemon-reload && systemctl --user enable --now garden-conversation-sync.timer
```

確認する。

```bash
systemctl --user list-timers garden-conversation-sync.timer   # NEXT が15分以内になっている
journalctl --user -u garden-conversation-sync -n 20           # 直近の実行のログ（HTTP 200/201）
```

ユーザーサービスは、ログインしていなくても動かすためにユーザーの lingering が要る。Hermes の gateway（`hermes-gateway.service`）も同じユーザーサービスなので有効なはずだが、次で確かめられる。

```bash
loginctl show-user <user> -p Linger   # Linger=yes ならよい
```

`no` なら `sudo loginctl enable-linger <user>`。

## 止め方・やり直し

- 止める: `systemctl --user disable --now garden-conversation-sync.timer`。アプリに入った会話は残る（アプリからは消せない）
- 全件送り直す: タイマーを止めて `~/.local/state/garden-conversation-sync.json` を消し、手で `python3 ~/hermes_conversation_sync.py` を実行してからタイマーを戻す。アプリ側は会話・発言・写真を Hermes の ID とファイル名で上書きするので、二重にならない。ただし古い写真は Hermes がすでに消しているので、新しく届く写真は増えない
- スクリプトを直したとき: 配置の `scp` をやり直すだけでよい（次の実行から新しい版になる）

## Hermes を更新したときの確認

`hermes update` の後、`state.db` の構造が変わっていないかを確かめる。

```bash
python3 ~/hermes_conversation_sync.py --dry-run
```

`エラー: state.db に必要な列がありません…`（`SchemaError`）にならず、`[dry-run]` の行が出ればよい。エラーになったら何も送られないので、Hermes の `state.db` の列（`sessions` / `messages`）を見て、スクリプトの `REQUIRED_COLUMNS` と取り込みの作りを直す。

## 結び付けの解析を直したとき

各データの詳細画面に出す「このデータが出てきた会話」は、保存した発言の curl のコマンドから、作った・変えた・見たデータを解析して作る（`app/utils/conversation_links.py`）。解析の規則を直したら、保存済みの全会話を作り直す。

本番はアプリのサーバーで `garden` ユーザーとして（他の保守コマンドと同じ流し方。[`migration-to-ubuntu.md`](migration-to-ubuntu.md)）:

```bash
sudo -u garden -H bash -c 'cd /opt/garden-app && ~/.local/bin/uv run flask --app app relink-conversations'
```

`<件数>件の会話から結び付けを<件数>件作り直しました` と出れば成功。開発 PC では `uv run flask --app app relink-conversations`。本番では事前に [`migration-to-ubuntu.md`](migration-to-ubuntu.md) の手でバックアップを取る（`sudo -u garden sqlite3 /opt/garden-app/instance/garden.db ".backup '/var/backups/garden/garden-before-update-$(date +%Y%m%d-%H%M).db'"`）。開発 PC では [`../db-validation-safety.md`](../db-validation-safety.md) に従う。

## うまくいかないとき

| 症状 | 確認すること |
|---|---|
| `エラー: env ファイルを読めません` | `~/.config/garden-api.env` があるか、`GARDEN_API_URL` と `GARDEN_API_TOKEN` が入っているか |
| `HTTP 401` | トークンが `.env` の `API_TOKEN` と同じか |
| `HTTP 422` | まず表示される `code` / `message` を見る（型の不一致、`session.id` の形、発言が 5000 件超など）。`--dry-run` は送る内容の型を確かめないので、最初の取り込みで初めて 422 が出ることがある |
| `失敗 URLError` など | アプリ（`garden-app.service`）が動いているか、`GARDEN_API_URL` の API ポートが合っているか |
| `エラー: state.db を読めません` | `--db` のパス、Hermes が書き込み中でロックが長引いていないか（10 秒待つ。次の回に再試行される） |
