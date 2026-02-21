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
    image_path VARCHAR(255),
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
    image_path VARCHAR(255),
    canvas_data TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

-- 植え付けテーブル（場所-作物関連）
CREATE TABLE IF NOT EXISTS plantings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    crop_id INTEGER NOT NULL,
    planted_date DATE,
    quantity INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    position_x DECIMAL(10, 2) DEFAULT NULL,
    position_y DECIMAL(10, 2) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE CASCADE
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_plantings_location ON plantings(location_id);
CREATE INDEX IF NOT EXISTS idx_plantings_crop ON plantings(crop_id);
CREATE INDEX IF NOT EXISTS idx_plantings_status ON plantings(status);

-- 栽培観察記録テーブル
CREATE TABLE IF NOT EXISTS planting_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_crop_id INTEGER NOT NULL,
    recorded_at DATE NOT NULL,
    notes TEXT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (location_crop_id) REFERENCES plantings(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_planting_records_location_crop ON planting_records(location_crop_id);
CREATE INDEX IF NOT EXISTS idx_planting_records_date ON planting_records(recorded_at DESC);
