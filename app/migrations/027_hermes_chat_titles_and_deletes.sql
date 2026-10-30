-- Hermes とのチャット画面: 会話の題名と、消した会話の記録
-- Migration: 027_hermes_chat_titles_and_deletes
--
-- hermes_chats.title = 最初の質問から自動で付ける題名、custom_title = ユーザーが変えた題名（NULL なら未変更）。
-- deleted_conversations = アプリから消した会話の Hermes の ID。取り込みで復活させないために覚える。
-- 起動のたびに実行されるので、CREATE を先に置く（ADD COLUMN は2回目以降「duplicate column」で止まる）。
CREATE TABLE IF NOT EXISTS deleted_conversations (
    hermes_id TEXT PRIMARY KEY,
    deleted_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

ALTER TABLE hermes_chats ADD COLUMN title TEXT;
ALTER TABLE hermes_chats ADD COLUMN custom_title TEXT;
