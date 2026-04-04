-- 補足情報テーブル
CREATE TABLE IF NOT EXISTS supplements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type VARCHAR(20) NOT NULL,
    entity_id INTEGER NOT NULL,
    supplement_type VARCHAR(20) NOT NULL,
    title VARCHAR(200),
    content TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

CREATE INDEX IF NOT EXISTS idx_supplements_entity ON supplements(entity_type, entity_id);
