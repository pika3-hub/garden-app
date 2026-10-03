# 開発・検証の実務ノウハウ

AI アシスタント（Claude Code など）がこのリポジトリで作業するときに、過去のセッションでつまずいた点と、その回避策をまとめたもの。セッション終了時の振り返り（ルート `CLAUDE.md` の「セッション終了時の振り返り」）で得た知見は、ここに追記する。

## 改行コード（Windows 環境）

- リポジトリのファイルは **LF**（`core.autocrlf` は `false`）
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
- `load_dotenv()` を引数なしで呼ぶと、**呼び出し元スクリプトのディレクトリ** から `.env` を探す。リポジトリ外のスクリプトでは見つからないので、パスを明示する

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

## ツール・環境

- `gh` CLI は未インストール。プルリクエストは `git push` 後に表示される URL から手動で作成し、本文はアシスタントが用意する
- `node` は未インストール。JS の構文チェックはブラウザでの読み込み（コンソールエラー確認）で代用する
- テストは `uv run pytest`。`tests/conftest.py` のフィクスチャが tmp_path 上の使い捨て DB を使う
- 起動のたびに全マイグレーションが再実行され、適用済みのものは `Migration warning`（duplicate column 等）として出る。新しいマイグレーションの確認では、自分のファイル名の行だけを見る
