-- 作物テーブル
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    crop_type VARCHAR(50) NOT NULL,
    variety VARCHAR(100),
    characteristics TEXT,
    planting_season VARCHAR(50),
    harvest_season VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

-- 場所テーブル
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    location_type VARCHAR(50) NOT NULL,
    area_size DECIMAL(10, 2),
    sun_exposure VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

-- 場所-作物関連テーブル
CREATE TABLE IF NOT EXISTS location_crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    crop_id INTEGER NOT NULL,
    planted_date DATE,
    quantity INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE CASCADE
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_location_crops_location ON location_crops(location_id);
CREATE INDEX IF NOT EXISTS idx_location_crops_crop ON location_crops(crop_id);
CREATE INDEX IF NOT EXISTS idx_location_crops_status ON location_crops(status);
