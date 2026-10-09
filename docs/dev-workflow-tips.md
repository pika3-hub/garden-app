# 開発・検証の実務ノウハウ

AI アシスタント（Claude Code など）がこのリポジトリで作業するときに、過去のセッションでつまずいた点と、その回避策をまとめたもの。セッション終了時の振り返り（ルート `CLAUDE.md` の「セッション終了時の振り返り」）で得た知見は、ここに追記する。

## 改行コード（Windows 環境）

- リポジトリのファイルは原則 **LF**（`core.autocrlf` は `false`）。ただし一部 **CRLF のまま登録されているファイル** がある（`server.py`、`app/routes/` の一部など。`git ls-files --eol | grep i/crlf` で確認）。スクリプトで編集するときは元の改行コードを判定して保ち、勝手に統一しない
- Git Bash から `python` で文字列置換スクリプトを書く場合、`open(p, 'w')` のままだと Windows の Python が **CRLF で書き出し、ファイル全体が差分になる**。必ず `open(p, encoding='utf-8', newline='')` で読み書きする（または Edit ツールを使う）
- 改行コードの確認は `grep -c $'\r' <file>`（0 なら LF）。`od -c | grep '\\r'` は誤判定するので使わない
- 編集後は `git diff --stat` で差分行数が想定どおりかを必ず見る。行数が異常に多ければ改行コードの変化を疑う

## 実データ DB を汚さないブラウザ確認

`instance/garden.db` は実データ（[`db-validation-safety.md`](db-validation-safety.md) 参照）。画面の動作確認は **DB のコピーに向けたサーバー** で行う。マイグレーションも実データには適用されない。

スクラッチ領域（リポジトリ外）に次のスクリプトを置き、`uv run python <path>/run_copy.py` で起動する:

```python
import os, sys
ROOT = r'D:\workspace\garden-app'
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))   # リポジトリ外のスクリプトはパスを明示
from app.config import config, DevelopmentConfig

class CopyConfig(DevelopmentConfig):
    DATABASE = r'<scratch>/garden_copy.db'   # 事前に instance/garden.db をコピー

config['copy'] = CopyConfig
from app import create_app
create_app('copy').run(host='127.0.0.1', port=int(os.environ.get('PORT', '5055')), debug=False)
```

- 環境変数を変えた複数の状態（例: APIキー無し / ダミーキー）を比べたいときは、`PORT` を変えて同時に起動するとよい（例: `ANTHROPIC_API_KEY=sk-ant-dummy PORT=5056 ...`）
- `debug=False` なので、コードを変えたら再起動が必要
- 以前のセッションのサーバーが同じポートで動いたままだと、**新しいサーバーも起動に成功したように見えるが、リクエストは古いプロセスが受けて古いコードの画面が返る**（Windows では同じポートに複数のプロセスが LISTEN できる）。起動前に `netstat -ano | grep LISTEN | grep :5055` で空きを確認し、埋まっていれば `PORT` を変える。自分のサーバーのログにアクセスが記録されているかでも見分けられる
- `load_dotenv()` を引数なしで呼ぶと、**呼び出し元スクリプトのディレクトリ** から `.env` を探す。リポジトリ外のスクリプトでは見つからないので、パスを明示する

## 外部API の手動確認

API（`app/api/`）を実際のデータで確かめるときも、**コピー DB に `DATABASE` を向けて `server.py` を起動**する（`run.py` では API は起動しない）。

```bash
cp instance/garden.db <scratch>/garden_copy.db
HOST=127.0.0.1 API_HOST=127.0.0.1 DATABASE=<scratch>/garden_copy.db   API_TOKEN=<40文字程度のテスト用トークン> API_PORT=5061 uv run python server.py
```

- `.env` に `HOST=0.0.0.0` があっても、環境変数で `HOST=127.0.0.1` を渡せば LAN に公開しない（`load_dotenv` は既存の環境変数を上書きしない）
- Web 側のポートは 5000 固定なので、既に 5000 でサーバーが動いていると起動できない。先に `netstat -ano | grep LISTEN | grep :5000` で確認する
- アップロード先は実際の `app/static/uploads/` になる。確認で作った画像は、作成したパスを控えておいて後で消す
- waitress は stdout をバッファするので、ログファイルが空でも起動していることがある。`curl` で応答を確かめる
- curl の書き方は `docs/api/curl-examples.md`（`gapi` 関数）

## ドキュメントとコードの照合

CLAUDE.md や `docs/frontend/*.md` の記述がコードとずれていないか確かめるときは、記述を読むより実物を出力して比べる方が速く確実。

- **URL 一覧**: `create_app('testing')`（`DATABASE=':memory:'`）で作ったアプリの `app.url_map.iter_rules()` を出力する。`run.py` を import したり `create_app()` を引数なしで呼んだりすると、**実データ DB にマイグレーションが走る** ので使わない
- **実際のスキーマ**: `sqlite3.connect('file:instance/garden.db?mode=ro', uri=True)` の読み取り専用接続で `PRAGMA table_info` を見る。`schema.sql` には初期テーブルしか無く、残りはマイグレーションで作られるため、`schema.sql` だけ見ても型は分からない
- **ずれやすい箇所**: 「対象画面」「利用画面」などの列挙（機能追加時に追記漏れが起きる）、他ドキュメントへの参照先（`app/templates/CLAUDE.md` を `docs/frontend/` に分割した後も古い参照が残っていた）

## 外部 API を使う機能

- 外部 API のレスポンス構造に依存する設計（例: 引用情報の有無、ブロックの種類）は、**設計の段階で最小リクエスト（数円程度）を1回実際に投げて確認する**。ドキュメントや SDK の型だけで判断しない
  - 実例: Claude の `web_search_20260209` は動的フィルタリング（コード実行経由で結果を読む）のため、本文に citations が付かなかった。citations 前提で作った「参考URL」が実 API 確認まで出ず、手戻りになった（現在は `web_search_tool_result` から補完している）
- 課金が発生する確認は、金額の目安を伝えてユーザーの了承を得てから行う。課金なしで確認できる部分（無効なダミーキーでの認証エラー表示など）は先に済ませる
- 自動テストは SDK クライアントを差し替えて実 API を呼ばない（`tests/test_ai_notes.py` の `FakeClient` 参照）。ただしフェイクは型を検査しないので、SDK の引数名・フィールド名は `inspect.signature(...)` や `Model.model_fields` で別途確認する
- Anthropic Python SDK は既定で `max_retries=2`（タイムアウトも再試行）。長時間・高コストのリクエストでは待ち時間と課金が倍増するので、`max_retries=0` にして全体の期限を自前で管理する

## ブラウザ自動操作（Claude in Chrome）

- `javascript_tool` の実行は **約45秒でタイムアウト** する。長い処理（AI 生成など）を JS 内で待たない。開始だけして、`wait` → 状態確認の短い呼び出しを繰り返す
- フォームの入力チェックやモーダルの状態確認は、クリック＋スクリーンショットより、JS で要素の class・値を読む方が速く確実
- 反映処理などの確認では `window.fetch` を一時的に差し替えると、課金や外部通信なしで UI の分岐を確認できる（終わったら必ず元に戻す）

## Windows のコンソール・文字コード

- Git Bash の `curl` で日本語のクエリ（`?q=トマト`）や JSON を送ると、引数の文字コードの都合で正しく届かないことがある（`/lookup?q=トマト` が空になった）。日本語を含む API の確認は、Python（`urllib`）のスクリプトで行う
- `curl ... | uv run python -c "...json.load(sys.stdin)..."` のようにパイプすると、Python 側が cp932 で読んで文字化けする。スクリプト側で `sys.stdout.reconfigure(encoding='utf-8')` し、HTTP の応答は `urllib` で直接読む
- `server.py` のログは、waitress が `serve()` のときにルートロガーへ `basicConfig()` するため、何もしないと Flask の既定ハンドラーと合わせて2重に出る。`server.py` ではアプリ生成より前に `logging.basicConfig()` している（これを消さない）

## ツール・環境

- `gh` CLI は winget でインストール済み（`C:\Program Files\GitHub CLI\gh.exe`、pika3-hub でログイン済み）。インストール直後のセッションなど PATH に無いときはフルパスで呼ぶ。プルリクエストは `gh pr create` で作成できる
- `node` は未インストール。JS の構文チェックはブラウザでの読み込み（コンソールエラー確認）で代用する
- テストは `uv run pytest`。`tests/conftest.py` のフィクスチャが tmp_path 上の使い捨て DB を使う
- `uv run pytest` が Smart App Control に `pytest.exe` をブロックされる（os error 4551）ときは、`uv run python -m pytest` なら実行できる
- `.venv` は python.org の Python 3.12（winget `Python.Python.3.12`、`%LOCALAPPDATA%\Programs\Python\Python312`、PSF 署名付き）で作っている。uv が自動で入れる Python（`%APPDATA%\uv\python\...`）は署名が無く、Smart App Control に `python.exe` や `DLLs\libcrypto-3-x64.dll` を断続的にブロックされる（HTTPS を使う AI メモ・OGP 取得が失敗しうる）。`.venv` を作り直すときは `uv venv --python "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"` → `uv sync` とし、uv 管理の Python を使わない。ブロックされたファイルはイベントログ `Microsoft-Windows-CodeIntegrity/Operational` の ID 3077 で確認できる
- 起動のたびに全マイグレーションが再実行され、適用済みのものは `Migration warning`（duplicate column 等）として出る。新しいマイグレーションの確認では、自分のファイル名の行だけを見る
