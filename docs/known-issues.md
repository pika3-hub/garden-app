# 既知の課題・改善候補

見つかったが、その場では対応を見送った課題の一覧。対応したら行を削除する。セッション終了時の振り返りで新たに見つかったものはここに追記する。

| 発見日 | 箇所 | 内容 | 影響 | 対応案 |
|---|---|---|---|---|
| 2026-10-03 | `app/database.py`（`detect_types=sqlite3.PARSE_DECLTYPES`） | Python 3.12 で既定のタイムスタンプ変換が非推奨になり、テスト実行時に DeprecationWarning が出る | 将来の Python で動作が変わる可能性 | 変換関数を明示的に登録するか、`PARSE_DECLTYPES` をやめて文字列で扱う |
| 2026-10-03 | `app/routes/settings_routes.py`（`ai_notes_draft`） | 手作りの JSON で巨大な `crop_id` や文字列でない `crop_name` を送ると 500。`use_web_search: "false"` が ON 扱い | 画面からは送られない値なので通常は起きない | `crop_id` の範囲チェック、文字列以外は空扱い、`use_web_search is True` で判定 |
| 2026-10-03 | `app/utils/ai_notes.py`（`_call_api`） | 拒否時のフォールバックが働いた応答の後に `pause_turn` が続くと、ドキュメント上は省くべきブロックもそのまま送り返す | まれに 400 エラー（「生成に失敗しました」と表示） | フォールバックブロック以前の thinking / tool_use 等を除いて送り返す |
