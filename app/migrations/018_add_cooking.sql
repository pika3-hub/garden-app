-- 料理テーブル
CREATE TABLE IF NOT EXISTS cooking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    notes TEXT,
    image_path TEXT,
    cooked_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

-- 料理関連テーブル（作物・品種・植え付け・収穫との多対多）
CREATE TABLE IF NOT EXISTS cooking_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cooking_id INTEGER NOT NULL REFERENCES cooking(id) ON DELETE CASCADE,
    relation_type VARCHAR(20) NOT NULL,
    crop_id INTEGER REFERENCES crops(id) ON DELETE CASCADE,
    variety_id INTEGER REFERENCES varieties(id) ON DELETE CASCADE,
    location_crop_id INTEGER REFERENCES plantings(id) ON DELETE CASCADE,
    harvest_id INTEGER REFERENCES harvests(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

CREATE INDEX IF NOT EXISTS idx_cooking_cooked_date ON cooking(cooked_date DESC);
CREATE INDEX IF NOT EXISTS idx_cooking_relations_cooking ON cooking_relations(cooking_id);
CREATE INDEX IF NOT EXISTS idx_cooking_relations_crop ON cooking_relations(crop_id);
CREATE INDEX IF NOT EXISTS idx_cooking_relations_variety ON cooking_relations(variety_id);
CREATE INDEX IF NOT EXISTS idx_cooking_relations_harvest ON cooking_relations(harvest_id);
