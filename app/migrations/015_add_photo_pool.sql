-- 写真プール機能
-- モバイルから撮った複数写真を一括アップロードし、後から任意のエンティティ登録で使い回すためのテーブル

CREATE TABLE IF NOT EXISTS photo_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_size INTEGER,
    notes TEXT,
    taken_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

CREATE INDEX IF NOT EXISTS idx_photo_pool_created ON photo_pool(created_at DESC);

CREATE TABLE IF NOT EXISTS photo_pool_usages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_pool_id INTEGER NOT NULL,
    entity_type VARCHAR(20) NOT NULL,
    entity_id INTEGER NOT NULL,
    copied_image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (photo_pool_id) REFERENCES photo_pool(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_photo_pool_usages_pool ON photo_pool_usages(photo_pool_id);
CREATE INDEX IF NOT EXISTS idx_photo_pool_usages_entity ON photo_pool_usages(entity_type, entity_id);
