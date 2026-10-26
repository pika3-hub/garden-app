-- Hermes との会話の履歴テーブル
-- Migration: 023_add_conversations
--
-- 起動のたびに実行されるので IF NOT EXISTS で何度実行しても同じ結果にする。
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hermes_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    title TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    last_activity_at TIMESTAMP,
    end_reason TEXT,
    parent_hermes_id TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    hermes_message_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    tool_call_id TEXT,
    tool_name TEXT,
    display_kind TEXT,
    timestamp TIMESTAMP,
    UNIQUE(conversation_id, hermes_message_id)
);

CREATE TABLE IF NOT EXISTS conversation_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    image_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    UNIQUE(conversation_id, file_name)
);

CREATE TABLE IF NOT EXISTS conversation_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('created', 'updated', 'viewed')),
    hermes_message_id INTEGER,
    UNIQUE(conversation_id, entity_type, entity_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_conversation_links_entity ON conversation_links(entity_type, entity_id);
