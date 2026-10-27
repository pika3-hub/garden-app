# 既知の課題・改善候補

見つかったが、その場では対応を見送った課題の一覧。対応したら行を削除する。セッション終了時の振り返りで新たに見つかったものはここに追記する。

| 発見日 | 箇所 | 内容 | 影響 | 対応案 |
|---|---|---|---|---|
| 2026-10-27 | `advice_relations`（`app/models/advice.py`、`app/api/advices.py`） | `PRAGMA foreign_keys` が無効で CASCADE が動かないため、作物・植え付けなどを消すとアドバイスの関連行が孤立して残る（品種の削除だけはトリガーで付け替える）。API の読み取りは削除済みの対象の id を返し、`display_name` は null になる。他の多対多の関連テーブルも同じ | 画面には出ない。API の利用側が存在しない id を見ることがある | 対象の削除時に関連行を消す（モデルの `delete` かトリガー）、または外部キーを有効にする |
| 2026-10-26 | `app/utils/conversation_links.py`（`_tokenize`） | 引用符の閉じ忘れなどで shlex が失敗すると空白で分割し直すため、改行で区切った複数の curl が1つにまとまる。`--json` の値を飛ばさないので、本文に API の URL があると拾うことがある | 壊れたコマンドでまれに結び付けを取りこぼす・誤る（例外は出ない） | 分割し直すときも改行で区切る、`--json` を値を取る引数に加える |
| 2026-10-26 | `app/api/conversations.py`（`POST /conversations`） | 単独のサロゲート（`"\ud800"`）を含む文字列で SQLite が失敗して 500。縮小版を保存した後に `add_image` で失敗するとファイルが残る。`parent_session_id` の形を検査しない | 送り手は同期スクリプトだけなので、まず起きない | 文字列を `encode('utf-8')` で検査して 422、失敗時にファイルを消す、`parent_session_id` にも `_ID_RE` |
| 2026-10-27 | `tools/hermes_conversation_sync.py`（送信後の `sent_images`） | アプリが `skipped_images` で返した写真も送信済みに入れるので、二度と送らない。413・415（大きすぎる・形式が違う）は送り直しても同じなので設計どおりだが、`_store_images` の `except Exception`（縮小版の保存の一時的な失敗など）も同じ扱いになる（Codex のレビューで発見） | 一時的な失敗のときだけ、その写真が会話の履歴に出ない（まれ） | API が読み飛ばしの理由（恒久・一時）を返し、一時的なものは `sent_images` に入れず次の回に送り直す |
| 2026-10-26 | `tools/hermes_conversation_sync.py` | 発言が 5000 件を超えた会話は毎回 422 になり送れない。状態のファイルの保存（`save_state`）の OSError を捕まえない | Matrix の会話は数百件規模なので当面起きない。保存の失敗は次の回に送り直すだけ | 古い発言から分けて送る（API 側も分割を受け付ける）、保存の失敗をエラーとして終了コード 1 にする |
| 2026-10-25 | `app/routes/photo_sort_routes.py`（`_save_planting` / `_save_planting_record` / `_save_harvest` / 料理・日記の関連の保存） | 複数件を作る保存の途中で失敗すると、前半だけ登録済みのまま同じ写真の入力画面に戻る（各 `create` が個別に commit する） | 保存し直すと前半が二重登録になる（ディスク不足・DB ロックなど、まれな場合のみ） | 1つのトランザクションにまとめるか、登録済みの件数を表示して次へ進める |
| 2026-10-25 | `app/static/js/photo-sort.js` ほか関連付けのチップ表示（`diary/form.html` 等の badgeRenderer も同じ） | 作物名・場所名などをエスケープせずに `innerHTML` に入れる | 名前に HTML を書くとチップでスクリプトが動く（自分のデータ・LAN 内なので実害は小さい） | 共通のエスケープ関数を作り、各 badgeRenderer で使う |
| 2026-10-25 | `app/routes/photo_sort_routes.py`（`_save_harvest`、`ai_draft`） | 収穫量に `nan` / `inf` を入れると通る。AI 下書きの `photo_id` に JSON の `true` を送ると写真 1 として扱われる。「選んだ植え付けで収穫量を入力」の再描画でメモも URL（ブラウザの履歴）に載る | 画面の通常の操作ではほぼ起きない | `math.isfinite` で判定、`photo_id` は `bool` を除外、再描画は POST にする |
| 2026-10-25 | 検索全般（API の `q`・`/lookup`、画面のキーワード検索） | ひらがなとカタカナを区別する（`LIKE`）。`じゃがいも` で `ジャガイモ`、`白カブ` で `白かぶ` が見つからない | Hermes が0件と判断して「未登録」と答えたり、引き直しに手間がかかる（SKILL.md で表記を変えて引き直すよう指示済み。2026-10-10〜22 の Hermes の自己改善の提案に何度も出ていた） | 検索する側と検索される側をひらがな（またはカタカナ）にそろえて比べる（SQLite の自作関数か、検索用の列を持つ） |
| 2026-10-10 | `app/api/resource.py`（`create_item` / `patch_item`） | 本体の保存後（関連の保存・追加画像の添付）で失敗すると、データは保存済みなのに 500 を返す | エージェントが再送すると二重登録になる（ディスク不足など、まれな場合のみ。SKILL.md で再送前の確認を指示済み） | 保存後の失敗は 201 ＋ `warnings` で返す |
| 2026-10-10 | `app/api/payload.py` | multipart のファイルパートのファイル名が空だと、黙って無視される | 写真を付けたつもりで画像なしで登録される（通常の curl では起きない） | 空のファイル名は 422 にする |
| 2026-10-10 | `app/api/plantings.py` | 終了日が植え付け日より前でも受け付ける。removed の植え付けへの end_date 変更のメッセージが「栽培中」になる | 画面も同じ挙動。表示上の日数がおかしくなる程度 | `/end` と PATCH で日付の前後を検証、メッセージを status 別に |
| 2026-10-10 | `app/api/validation.py` / `payload.py` | 数値に `"1_000"` を受け付ける。`-F data=@x.json`（ファイルとして送った data）が「未知のパーツ」と分かりにくいメッセージになる | 実害は小さい | `_to_number` で `_` を拒否、data のファイル送信は受け付けるか専用メッセージ |
| 2026-10-10 | `server.py`（`create_app` と `create_api_app` の両方で `init_db`） | 起動時にスキーマとマイグレーションが2回走る | ログが増えるだけ | API アプリではマイグレーションを省く |
| 2026-10-03 | `app/database.py`（`detect_types=sqlite3.PARSE_DECLTYPES`） | Python 3.12 で既定のタイムスタンプ変換が非推奨になり、テスト実行時に DeprecationWarning が出る | 将来の Python で動作が変わる可能性 | 変換関数を明示的に登録するか、`PARSE_DECLTYPES` をやめて文字列で扱う |
| 2026-10-03 | `app/routes/settings_routes.py`（`ai_notes_draft`） | 手作りの JSON で巨大な `crop_id` や文字列でない `crop_name` を送ると 500。`use_web_search: "false"` が ON 扱い | 画面からは送られない値なので通常は起きない | `crop_id` の範囲チェック、文字列以外は空扱い、`use_web_search is True` で判定 |
| 2026-10-03 | `app/utils/ai_notes.py`（`_call_api`） | 拒否時のフォールバックが働いた応答の後に `pause_turn` が続くと、ドキュメント上は省くべきブロックもそのまま送り返す | まれに 400 エラー（「生成に失敗しました」と表示） | フォールバックブロック以前の thinking / tool_use 等を除いて送り返す |
