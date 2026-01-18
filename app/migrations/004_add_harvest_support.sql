-- 収穫記録機能のテーブル追加
-- Migration: 004_add_harvest_support

-- 収穫記録テーブル
CREATE TABLE IF NOT EXISTS harvests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_crop_id INTEGER NOT NULL,
    harvest_date DATE NOT NULL,
    quantity DECIMAL(10, 2),
    unit VARCHAR(20),
    notes TEXT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (location_crop_id) REFERENCES location_crops(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_harvests_location_crop ON harvests(location_crop_id);
CREATE INDEX IF NOT EXISTS idx_harvests_date ON harvests(harvest_date DESC);
