# 開発・検証の実務ノウハウ

AI アシスタント（Claude Code など）がこのリポジトリで作業するときに、過去のセッションでつまずいた点と、その回避策をまとめたもの。セッション終了時の振り返り（ルート `CLAUDE.md` の「セッション終了時の振り返り」）で得た知見は、ここに追記する。

## 改行コード（Windows 環境）

- リポジトリのファイルは原則 **LF**（`core.autocrlf` は `false`）。ただし一部 **CRLF のまま登録されているファイル** がある（`server.py`、`app/routes/` の一部など。`git ls-files --eol | grep i/crlf` で確認）。スクリプトで編集するときは元の改行コードを判定して保ち、勝手に統一しない
- Git Bash から `python` で文字列置換スクリプトを書く場合、`open(p, 'w')` のままだと Windows の Python が **CRLF で書き出し、ファイル全体が差分になる**。必ず `open(p, encoding='utf-8', newline='')` で読み書きする（または Edit ツールを使う）。`Path.write_text` も同じく CRLF になるので、`read_bytes().decode()` → `write_bytes(s.encode())` にする（2026-10-24 に `write_text` で `resource.py` 全体が差分になった。2026-10-25 にも `python - <<'EOF'` のヒアドキュメントで同じことをして、**新規ファイル4つが CRLF のままコミット**された。新規ファイルは `git diff --stat` に異常が出ないので気づきにくい。コミット前に `git diff --name-only main...HEAD | xargs git ls-files --eol | grep crlf` で確かめる）
- 改行コードの確認は `grep -c $'\r' <file>`（0 なら LF）。`od -c | grep '\\r'` は誤判定するので使わない
- 編集後は `git diff --stat` で差分行数が想定どおりかを必ず見る。行数が異常に多ければ改行コードの変化を疑う
- **サブエージェントに実装を任せるときは、指示に改行コードの注意を書く**（「`git ls-files --eol` で元の改行を確かめて保つ、新規は LF、Python のテキストモードで書かない、Edit ツールを使う」）。2026-10-26 は注意を書かなかった回で、修正のコミットがテンプレートとテストを CRLF に書き換えた。書いた回は起きなかった。2026-10-27 は注意を書いた回でも、LF のファイル2つに CR が1行ずつ混ざった（タスクレビューで発見）。レビューでは変更前後の CR の数を比べる: `git show <base>:<file> | tr -cd '\r' | wc -c` と `git show HEAD:<file> | ...`。**`git show ... | grep -c $'\r'` は Git Bash では混ざった CR を数えず 0 になった**ので使わない

## 実データ DB を汚さないブラウザ確認

`instance/garden.db` は実データ（[`db-validation-safety.md`](db-validation-safety.md) 参照）。画面の動作確認は **DB のコピーに向けたサーバー** で行う。マイグレーションも実データには適用されない。

本番をサーバーへ移した後（2026-10-11〜）は、開発 PC に `instance/garden.db` が無い。コピー元は移設時点の退避 `instance/garden.db.moved-to-ubuntu` を使う（以下の手順の `instance/garden.db` は読み替える）。表示の確認ならこれで足りる。

スクラッチ領域（リポジトリ外）に次のスクリプトを置き、`uv run python <path>/run_copy.py` で起動する:

```python
import os, sys
ROOT = r'<リポジトリのフォルダ>'
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
- **ログインが要る画面・Hermes を使う画面をコピー DB で見るとき**（2026-10-30、チャット画面）: パスキーの顔認証は自動操作できないので、上のスクリプトに確認用のログインを足す。`create_app` のあとに `@app.route('/_dev_login')` を足し、コピー DB の `passkeys` に名前 `dev-check` の行（`credential_id` / `public_key` は適当な文字列）を入れて `app.auth.login_owner(その id)` する。設定は `SESSION_COOKIE_SECURE = False`（`http://localhost`）と、ダミーの `HERMES_API_KEY`。手元には Hermes が無いので、`app.utils.hermes_client` の `start_run` / `get_run` / `iter_events` / `get_session_messages` を、決まった答えを流す偽物に差し替える（`iter_events` は `tool.started` → `message.delta` を数回 → `run.completed` の辞書を順に返す）。送った指示（instructions）を `print` しておくと、どの指示が Hermes に渡るかも確かめられる。このスクリプトはスクラッチ領域に置き、リポジトリに入れない

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
  - 実例: Claude の `web_search_20260209` は動的フィルタリング（コード実行経由で結果を読む）のため、本文に citations が付かなかった。citations 前提で作った「参考URL」が実 API 確認まで出ず、手戻りになった（現在は AI に参考URLを書かせ、`web_search_tool_result` の検索結果と照合して実在するものだけ残している）
- **許可するモデルを増やすときは、モデルごとに実 API で確かめる**。同じ指示でもモデルで振る舞いが違う。AI メモ下書きでは、Sonnet が「Webで調べる」なのに検索せずに書いた回があり、Haiku は自分で `## 参考URL` を書いた上に citations も付けて見出しが2重になった（2026-10-24）。また Haiku 5.5 は、claude-api スキルの対応表に無い `web_search_20260209` を送っても 400 にならなかった。「受け付けるか」ではなく公式の対応表で選ぶ（Haiku は `web_search_20250305`、サーバー側フォールバックも無い）
- Hermes の `SKILL.md` に書く curl の例には、**具体的な日付など、毎回変わる値を入れない**（省略できる項目は省き、入れるなら `<date +%F の結果>` のような置き場所にする）。エージェントは例をそのまま写しやすい。2026-10-27 にアドバイスの例へ `"advised_on": "2026-10-27"` を書き、最終レビューで「保存されるすべてのアドバイスがこの日付になりうる」と指摘された
- 課金が発生する確認は、金額の目安を伝えてユーザーの了承を得てから行う。課金なしで確認できる部分（無効なダミーキーでの認証エラー表示など）は先に済ませる
- 自動テストは SDK クライアントを差し替えて実 API を呼ばない（`tests/test_ai_notes.py` の `FakeClient` 参照）。ただしフェイクは型を検査しないので、SDK の引数名・フィールド名は `inspect.signature(...)` や `Model.model_fields` で別途確認する
- Anthropic Python SDK は既定で `max_retries=2`（タイムアウトも再試行）。長時間・高コストのリクエストでは待ち時間と課金が倍増するので、`max_retries=0` にして全体の期限を自前で管理する

## 外部 API（`app/api/`）の実機確認

- 画面でできない操作が、ボタンの表示条件や選択肢の絞り込み（例: 収穫・栽培記録の登録先は栽培中の植え付けだけ表示）だけで防がれていることがある。API で同じ操作を作るときは、ルートだけでなくテンプレートの表示条件まで確認し、API 側ではサーバーで検査する。実例: 終了済みの植え付けに API からだけ収穫を登録できた
- 画像の確認は実際のスマホ写真で行う。スマホの写真は MPO（複数画像入りの JPEG）のことが多く、Pillow で作ったテスト画像だけでは気づけなかった（写真プール `app/static/uploads/photo_pool/` に実物がある）
- `.env` に `API_HOST=0.0.0.0` を書き込むなど、サービスを LAN に公開する操作は Claude Code の自動許可で止められる。ユーザーに実行してもらうスクリプトを用意する
- ユーザーに実行してもらうコマンドには `cd <リポジトリのフォルダ>` を含める（管理者の PowerShell は `C:\windows\system32` で開くため、相対パスの `.env` が見つからず、uv 版の Python が使われた）。トークンなど秘密の値をファイルに書いてもらったら、値を出さずに確認するコマンド（文字数の表示など）を添える
- メイン PC でユーザーに実行してもらうコマンドは PowerShell の書き方で示す（ユーザーは VS Code の PowerShell で実行する）。Git Bash 用の `/tmp`・`/d/...` のパスや `diff` を渡したら、scp が失敗し、`diff`（PowerShell では `Compare-Object` の別名）はパスの文字列を比べるだけだった。一時ファイルは `$env:TEMP`、ファイルの比較は `git diff --no-index`
- Hermes の回答は、件数などを DB の読み取り専用接続（`sqlite3.connect('file:instance/garden.db?mode=ro', uri=True)`）で突き合わせる。見た目がもっともらしくても、一覧の既定件数（50件）で切れた結果を総数として答えていた。SKILL.md を直したら scp でサーバーに送り、ターミナルの `hermes` は起動し直す。Telegram（gateway）で試すときは `systemctl --user restart hermes-gateway.service` もする（再起動中に送ったメッセージは捨てられる）
- SKILL.md の対応表に書いていない組み合わせを、Hermes は「できない」と判断しがち。収穫の行に `image` が無かったため、写真付きの依頼でも収穫に添付しなかった（API は対応済み）。対応表の各行には使えるパラメータを省かずに書く
- **依頼のあとに続けてやらせたい手順は、対応表のその行に「→ 続けて○○（下の「…」の節）」と書く**。別の節の途中に1行書いただけでは、Hermes が飛ばす（2026-10-24、作物の登録後の YouTube を付け忘れた。対応表に作物の新規登録の行が無く、必須の `crop_type` も入れ忘れた）。依頼の種類を足したら、対応表に行があるかも確かめる
- Hermes が何を送って何で失敗したかは `gateway.log` に残らない（API 側は `journalctl -u garden-app` の `app.api` の行で、メソッド・パス・ステータスだけ分かる）。理由は、同じ会話のまま（`/new` せずに）Hermes 本人に「送った項目と error.details、〜しなかった理由を教えて。データは変更しないで」と聞くと分かる

## ブラウザ自動操作（Claude in Chrome）

- `javascript_tool` の実行は **約45秒でタイムアウト** する。長い処理（AI 生成など）を JS 内で待たない。開始だけして、`wait` → 状態確認の短い呼び出しを繰り返す
- フォームの入力チェックやモーダルの状態確認は、クリック＋スクリーンショットより、JS で要素の class・値を読む方が速く確実
- 反映処理などの確認では `window.fetch` を一時的に差し替えると、課金や外部通信なしで UI の分岐を確認できる（終わったら必ず元に戻す）
- `resize_window` で幅を変えても、ウィンドウが最大化されていると効かない（`innerWidth` が変わらない）。スマホ幅の確認は、同じ URL を幅 375px の `iframe` に読み込み、`contentDocument.documentElement.scrollWidth` と、右端がはみ出す要素を数えて測る（2026-10-25）
- 植え付けの詳細（見取り図のある重い画面）は、スクロール後のスクリーンショットが CDP のタイムアウトで失敗することがある。表示された文字を確かめるだけなら `get_page_text` を使う（2026-10-26）
- brainstorming スキルの画面モック用サーバー（visual companion）は `node` が無いので起動できない。モックは HTML ファイルをスクラッチ領域に書き、`Start-Process` でブラウザに開いて見てもらう
- **ログイン・CSRF が関わる画面の確認は Chrome・Edge・Safari で行う**。VS Code の内蔵ブラウザ（ページを iframe に入れる）で保存したら、Cookie の扱いの違いで CSRF の照合が合わず 400 になった（2026-10-28。Chrome では通った）
- `http://localhost:…` で起動した確認用のサーバーは、メイン PC のブラウザでしか開けない（iPhone・iPad の `localhost` はその端末自身）。スマホでも試してもらう確認は、最初からそう伝える。パスキーはスマホでは HTTPS（Caddy の `https://<サーバーのホスト名>.local`）でしか試せない
- パスキー（WebAuthn）の確認で、ユーザーの顔認証が要る手順はサブエージェントにはできない。実装担当には飛ばさせ、コントローラーがコピー DB のサーバーを起動して頼む。非常口の URL はサーバーの起動スクリプトの中で `Passkey.issue_registration_token()` を呼んでファイルに書くと、CLI（実データの DB を見る）を使わずに出せる

## Windows のコンソール・文字コード

- Git Bash の `curl` で日本語のクエリ（`?q=トマト`）や JSON を送ると、引数の文字コードの都合で正しく届かないことがある（`/lookup?q=トマト` が空になった）。日本語を含む API の確認は、Python（`urllib`）のスクリプトで行う。POST・PATCH の本文なら、Write で UTF-8 のファイルに JSON を書き、`curl --data-binary @<ファイル>` で送れば正しく届く。2026-10-27 はこの項目を読まずに日本語の JSON を引数に書き、2件が**エラーにならず文字化けしたまま登録された**（`〜` を含む1件は `Invalid \escape` で弾かれた）
- `curl ... | uv run python -c "...json.load(sys.stdin)..."` のようにパイプすると、Python 側が cp932 で読んで文字化けする。スクリプト側で `sys.stdout.reconfigure(encoding='utf-8')` し、HTTP の応答は `urllib` で直接読む
- `server.py` は `FLASK_ENV` 未設定だと本番設定（`ProductionConfig`、`SECRET_KEY` は `.env` から）で起動する。`run.py`（開発設定）では起きない不具合が出ることがある。以前は `SECRET_KEY` 未設定で、保存後の `flash()` が 500 になっていた（保存自体は済んでいる）。今は `create_app` が起動ごとのランダム値で補う。`server.py` を使う変更は、本番設定でも確認する
- `server.py` のログは、waitress が `serve()` のときにルートロガーへ `basicConfig()` するため、何もしないと Flask の既定ハンドラーと合わせて2重に出る。`server.py` ではアプリ生成より前に `logging.basicConfig()` している（これを消さない）
- Bash ツールのヒアドキュメントで Python にファイルを書き換えさせると、書き込む文字列の中の `\\x00` が本物の NUL 文字としてファイルに入った（`SyntaxError: source code string cannot contain null bytes`。Markdown でも起き、git diff で `Bin` と表示される。2026-10-12 に3回）。バックスラッシュを含む文字列（`b'\x00'`、ログの引用など）の編集は Edit ツールで行う
- Python スクリプトの日本語の出力は Git Bash で文字化けする。`PYTHONIOENCODING=utf-8 uv run python ...` で実行する。ただし `python -I`（隔離モード）では `PYTHON*` の環境変数が無視されて効かない。そのときはスクリプトで `open(..., encoding='utf-8')` のファイルに書き、Read で読む
- ユーザーの PowerShell は **Windows PowerShell 5.1** で、`Out-File -Encoding utf8NoBOM` は使えない（7 以降だけ）。代わりの `>` は UTF-16 で書き出すので、`git diff --no-index` が「Bin」と出して比べられなかった（2026-10-29、サーバーの SKILL.md と main の版の比較）。ファイルの比較は、ユーザーには取ってくる（`scp`）ところまでを頼み、比べるのは Claude が Bash（`tr -d '\r'` してから `diff`）で行う

## ツール・環境

- `gh` CLI は winget でインストール済み（`C:\Program Files\GitHub CLI\gh.exe`、自分の GitHub アカウントでログイン済み）。インストール直後のセッションなど PATH に無いときはフルパスで呼ぶ。プルリクエストは `gh pr create` で作成できる。`gh pr merge` は auto mode の権限チェックで止められる（レビューなしのマージ扱い）ので、マージはユーザーに GitHub の画面でしてもらう
- GitHub の画面のマージで「Merge error: The server is currently unable to perform this operation. Please try again later.」と出たら、GitHub 側の一時的な失敗。`gh pr view <番号> --json mergeable,mergeStateStatus` が `MERGEABLE` / `CLEAN` なら PR に問題は無いので、少し待って押し直す（2026-10-30 の PR #98 はそれで通った）
- PowerShell で `gh pr view --json body -q .body` の結果は行ごとの配列になる。そのまま文字列として書き戻すと改行が消える（PR #48 の本文で発生）。`-join "`n"` してから書くか、本文の加工は Bash で行う。消えてしまったら GraphQL の `pullRequest.userContentEdits { editedAt diff }` に過去の本文が残っている
- `node` は未インストール。JS の構文チェックはブラウザでの読み込み（コンソールエラー確認）で代用する
- テストは `uv run pytest`。`tests/conftest.py` のフィクスチャが tmp_path 上の使い捨て DB を使う
- `uv run pytest` が Smart App Control に `pytest.exe` をブロックされる（os error 4551）ときは、`uv run python -m pytest` なら実行できる
- `.venv` は python.org の Python 3.12（winget `Python.Python.3.12`、`%LOCALAPPDATA%\Programs\Python\Python312`、PSF 署名付き）で作っている。uv が自動で入れる Python（`%APPDATA%\uv\python\...`）は署名が無く、Smart App Control に `python.exe` や `DLLs\libcrypto-3-x64.dll` を断続的にブロックされる（HTTPS を使う AI メモ・OGP 取得が失敗しうる）。`.venv` を作り直すときは `uv venv --python "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"` → `uv sync` とし、uv 管理の Python を使わない。ブロックされたファイルはイベントログ `Microsoft-Windows-CodeIntegrity/Operational` の ID 3077 で確認できる
- ネイティブ DLL を含むライブラリを追加するときは、設計を詰める前に `uv add` → import だけ試す。`pillow-heif` は以前、同梱の `libde265-0-*.dll`・`libwinpthread-1-*.dll` が Smart App Control に毎回止められたが、2026-10-12 に 1.8.1 を入れ直したら読み込めた。ところが同じ日のうちにまた止められた（同じ版でも、止められるかは時期で変わる。だめなら Ubuntu で試す）。メイン PC では HEIC のテストが `@requires_heif`（`tests/api/helpers.py`）でスキップされ、そのたびに Windows セキュリティの警告が出る。`pillow_heif` は DLL を読めなくても import は通るので、`pytest.importorskip` ではスキップされない。Smart App Control は一度オフにすると OS の再インストールまで戻せないので、オフにする案は出さない
- 本番サーバーの Python は uv が入れたもので SQLite 3.53、メイン PC の `.venv`（python.org 版）は SQLite 3.49。同じ SQL でも結果が変わることがある（ダッシュボードの `GROUP BY ... ORDER BY ... DESC LIMIT` が 3.53 で古い順になった）。並び順や集計に関わる SQL を変えたら、サーバーでも読み取り専用接続で結果を確かめる
- コミット前に `git status --short` で含まれるファイルを確かめ、`git add -A` に頼らない。`.gitignore` に足した行は、それを含まない古い main から切ったブランチでは効かない（git 管理外のはずの `docs/local-env.md` が PR #52 で公開リポジトリに入った）。git に上げないものはリポジトリの外の `../garden-app-private/` に置く。追跡を外すコミット（`git rm --cached`）を pull すると、各環境の作業フォルダからもそのファイルが消える
- 起動のたびに全マイグレーションが再実行され、適用済みのものは `Migration warning`（duplicate column 等）として出る。新しいマイグレーションの確認では、自分のファイル名の行だけを見る

## Codex をもう一人のレビュー役にする

Codex（ChatGPT Plus の枠）の `codex review` で、Claude のレビューとは別の目でコードを見てもらえる（2026-10-27 に検証）。CLI はデスクトップアプリ同梱の `codex.exe` を使う（探し方は [`image-generation.md`](image-generation.md) の「Codex で作る」）。

- 使い方: PR を作る前に `& $cx review --base main`（ブランチの差分）。コミット1つなら `--commit <SHA>`、未コミットなら `--uncommitted`。読み取りだけで、ファイルは変えない
- 2026-10-27 に同期スクリプトの最初のコミット（5620dcc）で試したら、約1分で2件。1件は当時のレビューで見つけて直した問題（写真20枚の上限）、もう1件は見落としていた点（`skipped_images` を送信済みにする。[`known-issues.md`](known-issues.md)）。費用は5時間枠の約5%、週の枠の約1%（Hermes のふだんのモデルと同じ枠）
- **`--commit` / `--base` / `--uncommitted` と独自の指示（`[PROMPT]`）は一緒に使えない**（`cannot be used with '[PROMPT]'`）。結果は英語で返ってくる
- **過去のコミットを見せても、ファイルは今の作業ツリーを読む**。行番号やコードの引用が後の修正を含むことがあるので、指摘はそのコミットの時点か今かを確かめる
- 指摘は鵜呑みにせず、コードで確かめてから直す（5620dcc の2件目は、413・415 で読み飛ばすのは設計どおりで、当たるのは一時的な失敗のときだけだった）
- 進行の様子は標準エラーに出る（長い）。結論は標準出力の最後の `Full review comments:` 以下
- 2026-10-29 は Claude Code の PowerShell から `review --base main` を呼んだら、Codex のサンドボックスが起動できず（`helper_unknown_error`）、リポジトリを読めないまま「レビューできない」と返ってきた。タスクごとのレビューと最終レビューが済んでいたので、その PR は Codex なしで進めた。原因は未調査（次に使うときに、ユーザーの PowerShell から直接実行して切り分ける）

## サーバー（Ubuntu、本番）の操作

- 2026-10-11 から本番はサーバー（Ubuntu）。Claude は直接操作できないので、コマンドを示して結果を貼ってもらう。変更の前に読み取り専用の確認コマンドで現状を見る
- sudo を含む複数行を貼ってもらうときは、先頭に `sudo -v` を置く。途中で sudo がパスワードを聞くと、後ろの行が入力に吸い込まれて結果が欠ける（移設時に確認結果が2行分出ていなかった）
- 「成功ならこう出る」を必ず添え、返ってきた結果と照合する。ufw の遮断ルールは置いただけでは効いておらず（`lo` の ACCEPT の後ろだった）、照合で気づけた
- `/etc/ufw/*.rules` は root しか読めないので `sudo grep` にする。大きなファイルの受け渡しは `~/garden-transfer`（`/tmp` は tmpfs）
- **順番に意味がある複数のコマンドは `&&` でつなぐ**。Matrix のアカウント作成で、1つ目（自分）がパスワードの打ち間違いで失敗したのに2つ目（Bot）が実行され、Bot が管理者になって DB を作り直した
- **root しか読めない場所の `*` は `sudo bash -c '...'` の中に書く**。`sudo chmod /root/x-*.tgz` は、`*` を一般ユーザーのシェルが展開できず失敗する
- `scp` など、メイン PC 側で実行する手順は結果も貼ってもらう。サーバー側の結果だけ見て「送ったはずのファイルが無い」と後で気づいた
- Hermes の gateway のログは `~/.hermes/logs/gateway.log` を見る。`journalctl --user -u hermes-gateway` には WARNING 以上しか出ず、Matrix の接続などの INFO が見えない（「つながっていない」と誤解した）
- 暗号ライブラリ（mautrix）など Hermes 本体以外のログは `gateway.log` に出ず、`~/.hermes/logs/errors.log` に出る。E2EE の復号の失敗はそこにしか無かった
- Hermes の部品は仮想環境ではなく `hermes pm`（`~/.hermes/tools/` の専用 Python）で管理されている。`~/.local/bin/hermes` は sh のラッパーなので、1行目から Python の場所は分からない。部品の import を試すときは `find ~ -type d -name mautrix` で `~/.hermes/installs/.../venv` を探し、その `bin/python` を使う
- **Hermes が古い値（移設前の IP など）を使ったら、Hermes 自身の記憶 `~/.hermes/memories/MEMORY.md` を疑う**。環境変数は正しく渡っていたのに、移設前に覚えた「API は <メインPCのIP>:5001」を信じていた（2026-10-24）。直したら Element X で `/new`。サーバーの構成を変えたときは、記憶に古い値が無いか `grep` する
- iPhone のアプリから LAN 内のサーバーにつながらず Safari では開けるときは、iOS の「ローカルネットワーク」の許可を疑う
- **Element X で Hermes の返事が来ないときは、まず `gateway.log` に `[Matrix] Sending response` と `sent event` があるかを見る**。2026-10-30 は `/new` に反応が無いように見えたが、Hermes は返事を送っていて、iPhone の Element X に表示されるのが遅れていただけだった（しばらくして2件届いた）。送っていればサーバー側は正常で、端末の表示の問題
- **Hermes の答えがおかしい理由を推測で直さない。直す前に、Hermes に条件を付けた質問を1回送って切り分ける**。2026-10-30、パネルの会話で「前の質問はいつ？」に答えられなかったとき、「API を見に行くせい」と推測して SKILL.md とアプリの指示を2回直したが、どちらも効かなかった。「アプリは調べずに、この会話の履歴だけで答えて」と聞くと前の依頼は答えられ、「日時は表示されていません」と返ってきて、本当の原因（Hermes に渡る会話の履歴には日時が無い）が分かった。Hermes 本人に、何が見えていて何が見えていないかを聞くと速い（上の「Hermes が何を送って何で失敗したか」と同じ考え方）
- サーバーに `pika3`（Hermes の実行ユーザー）でログインして `curl http://127.0.0.1:5000/...` すると `000` になる。遮断のルールどおりで、異常ではない。Web 画面の確認はメイン PC かスマホのブラウザで行う（2026-10-26）
- **サーバーでの確認の `curl` は `sudo curl` にする**。ログイン用のユーザーは Hermes の実行ユーザーと同じなので、そのまま実行すると 5000 番・443 番の遮断のルールに当たって失敗する（最終レビューで、確認の手順がそのままでは失敗すると指摘された）
- **Caddy で入口を足したら、Hermes の遮断は TCP と UDP（HTTP/3）の両方に入れる**。Caddy は既定で UDP の 443 番でも待ち受け、ループバックの UDP は `-o lo -j ACCEPT` で通る。また 443 番の遮断は `-o lo` を付けて自ホスト宛てだけにする（付けないと Hermes の外への HTTPS が全部止まる）。2026-10-28 は TCP だけの手順を書き、最終レビューで見つかった
- 遮断を入れる順番: **Hermes の拒否のルールを先に入れてから、Caddy で入口を開く**（逆だと、一瞬でも Hermes が届く隙間ができる）
- サーバーの名前（`<サーバーのホスト名>.local`）は avahi で LAN に流している（2026-10-28〜）。**iPhone・iPad は「セキュリティ Wi-Fi」の SSID では `.local` を引けない**（2026-10-28 からどちらもふだんの接続先を 5G の SSID にした）（サーバーの mDNS の答えのマルチキャストが届かない）。名前が引けないときは `sudo tcpdump -ni any 'udp port 5353'` で、問い合わせが来ているか・答えが出ているか・端末が問い合わせを繰り返していないかを見ると切り分けられる
- `/var/backups/garden/` は `pika3` から読めない。中を見るときは `sudo ls -l /var/backups/garden/`（バックアップ自体は `sudo -u garden sqlite3 ...` で取れている）
- 再起動直後の `journalctl -u garden-app` に `Migration applied: ...` が出ないことがある（`print` の出力がバッファされる）。マイグレーションが入ったかは `sudo -u garden sqlite3 -readonly /opt/garden-app/instance/garden.db "SELECT name FROM sqlite_master WHERE ..."` で直接確かめる
- **Hermes の内部のデータの形（`state.db` の列、ツールの結果の形、写真のキャッシュの期限など）は、サーバーと同じ版の Hermes のソースで確かめる**。`git -C ~/.hermes/hermes-agent log -1 --format=%h` で版を聞き、メイン PC のスクラッチ領域に `git clone --filter=blob:none --no-checkout https://github.com/NousResearch/hermes-agent.git` → `git checkout <版>`。Windows ではパスの長い Web サイトの文書で「Filename too long」になり、checkout 全体が止まることもある（2026-10-29）ので、clone した直後に `git -C <フォルダ> config core.longpaths true` をしてから checkout する。貼ってもらう往復が減る。2026-10-26 は terminal ツールの結果が `{"output": "...", "exit_code": 0, ...}` で包まれていることを確かめずに設計し、最終レビューで初めて気づいた（`tools/terminal_tool_result.py`）。外から渡ってくるデータの形は、設計の段階で1件実物かソースを見る
