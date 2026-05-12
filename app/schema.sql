-- 作物テーブル
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    crop_type VARCHAR(50) NOT NULL,
    notes TEXT,
    icon_path TEXT,
    image_color TEXT DEFAULT '#4CAF50',
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

-- 品種テーブル（作物:品種 = 1:多）
CREATE TABLE IF NOT EXISTS varieties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    notes TEXT,
    icon_path TEXT,
    image_color TEXT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_varieties_crop ON varieties(crop_id);

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

-- 植え付けテーブル（場所-作物-品種関連）
-- crop_id と variety_id は排他関係（どちらか一方のみセット）
--   - 作物として植えた場合: crop_id=X, variety_id=NULL
--   - 品種として植えた場合: crop_id=NULL, variety_id=Y
CREATE TABLE IF NOT EXISTS plantings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    crop_id INTEGER DEFAULT NULL,
    variety_id INTEGER DEFAULT NULL,
    planted_date DATE,
    quantity INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    position_x DECIMAL(10, 2) DEFAULT NULL,
    position_y DECIMAL(10, 2) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    CHECK (
        (crop_id IS NOT NULL AND variety_id IS NULL) OR
        (crop_id IS NULL AND variety_id IS NOT NULL)
    ),
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id)     REFERENCES crops(id)     ON DELETE CASCADE,
    FOREIGN KEY (variety_id)  REFERENCES varieties(id) ON DELETE CASCADE
);

-- 品種削除時に親作物の植え付けへ昇格させるトリガー
-- （variety_id で参照されている plantings を crop_id = OLD.crop_id に付け替えて残す）
CREATE TRIGGER IF NOT EXISTS trg_promote_variety_plantings_before_delete
BEFORE DELETE ON varieties
FOR EACH ROW
BEGIN
    UPDATE plantings
       SET crop_id = OLD.crop_id, variety_id = NULL
     WHERE variety_id = OLD.id;
END;

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_plantings_location ON plantings(location_id);
CREATE INDEX IF NOT EXISTS idx_plantings_crop ON plantings(crop_id);
CREATE INDEX IF NOT EXISTS idx_plantings_variety ON plantings(variety_id);
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

-- 作物×品種ビュー
-- plantings は (crop_id=X, variety_id=NULL) または (crop_id=NULL, variety_id=Y) の排他形式
-- VIEW は両方にマッチするよう、品種行は crop_id=NULL、作物行は variety_id=NULL で提供
-- effective_crop_id は常に作物ID（集計・「作物Xの植え付け一覧」用）
-- 使用例: JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(p.crop_id, -1)
--                                   AND IFNULL(cv.variety_id, -1) = IFNULL(p.variety_id, -1)
-- 注意: SELECT cv.* は使わず、必要カラムを明示する（SQLite Row の重複カラム名対策）
CREATE VIEW IF NOT EXISTS crop_variety_view AS
SELECT
    NULL AS crop_id,
    v.id AS variety_id,
    c.id AS effective_crop_id,
    c.name AS crop_name,
    c.crop_type,
    v.name AS variety,
    COALESCE(v.notes, c.notes) AS notes,
    COALESCE(v.icon_path, c.icon_path) AS icon_path,
    COALESCE(v.image_color, c.image_color) AS image_color,
    COALESCE(v.image_path, c.image_path) AS image_path
FROM varieties v
JOIN crops c ON v.crop_id = c.id
UNION ALL
SELECT
    c.id AS crop_id,
    NULL AS variety_id,
    c.id AS effective_crop_id,
    c.name AS crop_name,
    c.crop_type,
    NULL AS variety,
    c.notes,
    c.icon_path,
    c.image_color,
    c.image_path
FROM crops c;
