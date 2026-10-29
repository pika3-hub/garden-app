-- Hermes に聞くパネルの会話（対象ごとの Hermes セッション）の対応表
-- Migration: 026_add_hermes_chats
--
-- entity_type は planting / crop / variety。対象なし（自由な質問）は entity_type / entity_id が NULL。
-- 1対象につき active=1 の行は1つ（「新しい会話」で古い行を active=0 にして新しい行を作る）。
-- 起動のたびに実行されるので IF NOT EXISTS で何度実行しても同じ結果にする。
CREATE TABLE IF NOT EXISTS hermes_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT,
    entity_id INTEGER,
    session_id TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    last_run_id TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    last_used_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

CREATE INDEX IF NOT EXISTS idx_hermes_chats_entity
    ON hermes_chats (entity_type, entity_id, active);
