# 既知の課題・改善候補

見つかったが、その場では対応を見送った課題の一覧。対応したら行を削除する。セッション終了時の振り返りで新たに見つかったものはここに追記する。

| 発見日 | 箇所 | 内容 | 影響 | 対応案 |
|---|---|---|---|---|
| 2026-10-10 | `app/api/resource.py`（`create_item` / `patch_item`） | 本体の保存後（関連の保存・追加画像の添付）で失敗すると、データは保存済みなのに 500 を返す | エージェントが再送すると二重登録になる（ディスク不足など、まれな場合のみ。SKILL.md で再送前の確認を指示済み） | 保存後の失敗は 201 ＋ `warnings` で返す |
| 2026-10-10 | `app/api/payload.py` | multipart のファイルパートのファイル名が空だと、黙って無視される | 写真を付けたつもりで画像なしで登録される（通常の curl では起きない） | 空のファイル名は 422 にする |
| 2026-10-10 | `app/api/plantings.py` | 終了日が植え付け日より前でも受け付ける。removed の植え付けへの end_date 変更のメッセージが「栽培中」になる | 画面も同じ挙動。表示上の日数がおかしくなる程度 | `/end` と PATCH で日付の前後を検証、メッセージを status 別に |
| 2026-10-10 | `app/api/validation.py` / `payload.py` | 数値に `"1_000"` を受け付ける。`-F data=@x.json`（ファイルとして送った data）が「未知のパーツ」と分かりにくいメッセージになる | 実害は小さい | `_to_number` で `_` を拒否、data のファイル送信は受け付けるか専用メッセージ |
| 2026-10-10 | `server.py`（`create_app` と `create_api_app` の両方で `init_db`） | 起動時にスキーマとマイグレーションが2回走る | ログが増えるだけ | API アプリではマイグレーションを省く |
| 2026-10-03 | `app/database.py`（`detect_types=sqlite3.PARSE_DECLTYPES`） | Python 3.12 で既定のタイムスタンプ変換が非推奨になり、テスト実行時に DeprecationWarning が出る | 将来の Python で動作が変わる可能性 | 変換関数を明示的に登録するか、`PARSE_DECLTYPES` をやめて文字列で扱う |
| 2026-10-03 | `app/routes/settings_routes.py`（`ai_notes_draft`） | 手作りの JSON で巨大な `crop_id` や文字列でない `crop_name` を送ると 500。`use_web_search: "false"` が ON 扱い | 画面からは送られない値なので通常は起きない | `crop_id` の範囲チェック、文字列以外は空扱い、`use_web_search is True` で判定 |
| 2026-10-03 | `app/utils/ai_notes.py`（`_call_api`） | 拒否時のフォールバックが働いた応答の後に `pause_turn` が続くと、ドキュメント上は省くべきブロックもそのまま送り返す | まれに 400 エラー（「生成に失敗しました」と表示） | フォールバックブロック以前の thinking / tool_use 等を除いて送り返す |
