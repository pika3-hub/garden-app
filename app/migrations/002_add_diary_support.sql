-- 管理日記機能のテーブル追加
-- Migration: 002_add_diary_support

-- 日記エントリテーブル
CREATE TABLE IF NOT EXISTS diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    entry_date DATE NOT NULL,
    weather VARCHAR(50),
    status VARCHAR(20) DEFAULT 'published',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 日記の関連テーブル（作物・場所・植え付け場所との多対多関連）
CREATE TABLE IF NOT EXISTS diary_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diary_id INTEGER NOT NULL,
    relation_type VARCHAR(20) NOT NULL,
    crop_id INTEGER,
    location_id INTEGER,
    location_crop_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (diary_id) REFERENCES diary_entries(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (location_crop_id) REFERENCES location_crops(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_diary_relations_diary ON diary_relations(diary_id);
CREATE INDEX IF NOT EXISTS idx_diary_entries_date ON diary_entries(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_diary_relations_crop ON diary_relations(crop_id);
CREATE INDEX IF NOT EXISTS idx_diary_relations_location ON diary_relations(location_id);
