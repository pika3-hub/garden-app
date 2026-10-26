# 開発・検証の実務ノウハウ

AI アシスタント（Claude Code など）がこのリポジトリで作業するときに、過去のセッションでつまずいた点と、その回避策をまとめたもの。セッション終了時の振り返り（ルート `CLAUDE.md` の「セッション終了時の振り返り」）で得た知見は、ここに追記する。

## 改行コード（Windows 環境）

- リポジトリのファイルは原則 **LF**（`core.autocrlf` は `false`）。ただし一部 **CRLF のまま登録されているファイル** がある（`server.py`、`app/routes/` の一部など。`git ls-files --eol | grep i/crlf` で確認）。スクリプトで編集するときは元の改行コードを判定して保ち、勝手に統一しない
- Git Bash から `python` で文字列置換スクリプトを書く場合、`open(p, 'w')` のままだと Windows の Python が **CRLF で書き出し、ファイル全体が差分になる**。必ず `open(p, encoding='utf-8', newline='')` で読み書きする（または Edit ツールを使う）。`Path.write_text` も同じく CRLF になるので、`read_bytes().decode()` → `write_bytes(s.encode())` にする（2026-10-24 に `write_text` で `resource.py` 全体が差分になった。2026-10-25 にも `python - <<'EOF'` のヒアドキュメントで同じことをして、**新規ファイル4つが CRLF のままコミット**された。新規ファイルは `git diff --stat` に異常が出ないので気づきにくい。コミット前に `git diff --name-only main...HEAD | xargs git ls-files --eol | grep crlf` で確かめる）
- 改行コードの確認は `grep -c $'\r' <file>`（0 なら LF）。`od -c | grep '\\r'` は誤判定するので使わない
- 編集後は `git diff --stat` で差分行数が想定どおりかを必ず見る。行数が異常に多ければ改行コードの変化を疑う
- **サブエージェントに実装を任せるときは、指示に改行コードの注意を書く**（「`git ls-files --eol` で元の改行を確かめて保つ、新規は LF、Python のテキストモードで書かない、Edit ツールを使う」）。2026-10-26 は注意を書かなかった回で、修正のコミットがテンプレートとテストを CRLF に書き換えた。書いた回は起きなかった

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

## Windows のコンソール・文字コード

- Git Bash の `curl` で日本語のクエリ（`?q=トマト`）や JSON を送ると、引数の文字コードの都合で正しく届かないことがある（`/lookup?q=トマト` が空になった）。日本語を含む API の確認は、Python（`urllib`）のスクリプトで行う
- `curl ... | uv run python -c "...json.load(sys.stdin)..."` のようにパイプすると、Python 側が cp932 で読んで文字化けする。スクリプト側で `sys.stdout.reconfigure(encoding='utf-8')` し、HTTP の応答は `urllib` で直接読む
- `server.py` は `FLASK_ENV` 未設定だと本番設定（`ProductionConfig`、`SECRET_KEY` は `.env` から）で起動する。`run.py`（開発設定）では起きない不具合が出ることがある。以前は `SECRET_KEY` 未設定で、保存後の `flash()` が 500 になっていた（保存自体は済んでいる）。今は `create_app` が起動ごとのランダム値で補う。`server.py` を使う変更は、本番設定でも確認する
- `server.py` のログは、waitress が `serve()` のときにルートロガーへ `basicConfig()` するため、何もしないと Flask の既定ハンドラーと合わせて2重に出る。`server.py` ではアプリ生成より前に `logging.basicConfig()` している（これを消さない）
- Bash ツールのヒアドキュメントで Python にファイルを書き換えさせると、書き込む文字列の中の `\\x00` が本物の NUL 文字としてファイルに入った（`SyntaxError: source code string cannot contain null bytes`。Markdown でも起き、git diff で `Bin` と表示される。2026-10-12 に3回）。バックスラッシュを含む文字列（`b'\x00'`、ログの引用など）の編集は Edit ツールで行う
- Python スクリプトの日本語の出力は Git Bash で文字化けする。`PYTHONIOENCODING=utf-8 uv run python ...` で実行する。ただし `python -I`（隔離モード）では `PYTHON*` の環境変数が無視されて効かない。そのときはスクリプトで `open(..., encoding='utf-8')` のファイルに書き、Read で読む

## ツール・環境

- `gh` CLI は winget でインストール済み（`C:\Program Files\GitHub CLI\gh.exe`、自分の GitHub アカウントでログイン済み）。インストール直後のセッションなど PATH に無いときはフルパスで呼ぶ。プルリクエストは `gh pr create` で作成できる。`gh pr merge` は auto mode の権限チェックで止められる（レビューなしのマージ扱い）ので、マージはユーザーに GitHub の画面でしてもらう
- PowerShell で `gh pr view --json body -q .body` の結果は行ごとの配列になる。そのまま文字列として書き戻すと改行が消える（PR #48 の本文で発生）。`-join "`n"` してから書くか、本文の加工は Bash で行う。消えてしまったら GraphQL の `pullRequest.userContentEdits { editedAt diff }` に過去の本文が残っている
- `node` は未インストール。JS の構文チェックはブラウザでの読み込み（コンソールエラー確認）で代用する
- テストは `uv run pytest`。`tests/conftest.py` のフィクスチャが tmp_path 上の使い捨て DB を使う
- `uv run pytest` が Smart App Control に `pytest.exe` をブロックされる（os error 4551）ときは、`uv run python -m pytest` なら実行できる
- `.venv` は python.org の Python 3.12（winget `Python.Python.3.12`、`%LOCALAPPDATA%\Programs\Python\Python312`、PSF 署名付き）で作っている。uv が自動で入れる Python（`%APPDATA%\uv\python\...`）は署名が無く、Smart App Control に `python.exe` や `DLLs\libcrypto-3-x64.dll` を断続的にブロックされる（HTTPS を使う AI メモ・OGP 取得が失敗しうる）。`.venv` を作り直すときは `uv venv --python "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"` → `uv sync` とし、uv 管理の Python を使わない。ブロックされたファイルはイベントログ `Microsoft-Windows-CodeIntegrity/Operational` の ID 3077 で確認できる
- ネイティブ DLL を含むライブラリを追加するときは、設計を詰める前に `uv add` → import だけ試す。`pillow-heif` は以前、同梱の `libde265-0-*.dll`・`libwinpthread-1-*.dll` が Smart App Control に毎回止められたが、2026-10-12 に 1.8.1 を入れ直したら読み込めた。ところが同じ日のうちにまた止められた（同じ版でも、止められるかは時期で変わる。だめなら Ubuntu で試す）。メイン PC では HEIC のテストが `@requires_heif`（`tests/api/helpers.py`）でスキップされ、そのたびに Windows セキュリティの警告が出る。`pillow_heif` は DLL を読めなくても import は通るので、`pytest.importorskip` ではスキップされない。Smart App Control は一度オフにすると OS の再インストールまで戻せないので、オフにする案は出さない
- 本番サーバーの Python は uv が入れたもので SQLite 3.53、メイン PC の `.venv`（python.org 版）は SQLite 3.49。同じ SQL でも結果が変わることがある（ダッシュボードの `GROUP BY ... ORDER BY ... DESC LIMIT` が 3.53 で古い順になった）。並び順や集計に関わる SQL を変えたら、サーバーでも読み取り専用接続で結果を確かめる
- コミット前に `git status --short` で含まれるファイルを確かめ、`git add -A` に頼らない。`.gitignore` に足した行は、それを含まない古い main から切ったブランチでは効かない（git 管理外のはずの `docs/local-env.md` が PR #52 で公開リポジトリに入った）。git に上げないものはリポジトリの外の `../garden-app-private/` に置く。追跡を外すコミット（`git rm --cached`）を pull すると、各環境の作業フォルダからもそのファイルが消える
- 起動のたびに全マイグレーションが再実行され、適用済みのものは `Migration warning`（duplicate column 等）として出る。新しいマイグレーションの確認では、自分のファイル名の行だけを見る

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
- サーバーに `pika3`（Hermes の実行ユーザー）でログインして `curl http://127.0.0.1:5000/...` すると `000` になる。遮断のルールどおりで、異常ではない。Web 画面の確認はメイン PC かスマホのブラウザで行う（2026-10-26）
- `/var/backups/garden/` は `pika3` から読めない。中を見るときは `sudo ls -l /var/backups/garden/`（バックアップ自体は `sudo -u garden sqlite3 ...` で取れている）
- 再起動直後の `journalctl -u garden-app` に `Migration applied: ...` が出ないことがある（`print` の出力がバッファされる）。マイグレーションが入ったかは `sudo -u garden sqlite3 -readonly /opt/garden-app/instance/garden.db "SELECT name FROM sqlite_master WHERE ..."` で直接確かめる
- **Hermes の内部のデータの形（`state.db` の列、ツールの結果の形、写真のキャッシュの期限など）は、サーバーと同じ版の Hermes のソースで確かめる**。`git -C ~/.hermes/hermes-agent log -1 --format=%h` で版を聞き、メイン PC のスクラッチ領域に `git clone --filter=blob:none --no-checkout https://github.com/NousResearch/hermes-agent.git` → `git checkout <版>`（Web サイトの文書の一部が「Filename too long」で失敗するが本体は読める）。貼ってもらう往復が減る。2026-10-26 は terminal ツールの結果が `{"output": "...", "exit_code": 0, ...}` で包まれていることを確かめずに設計し、最終レビューで初めて気づいた（`tools/terminal_tool_result.py`）。外から渡ってくるデータの形は、設計の段階で1件実物かソースを見る
