CREATE TABLE IF NOT EXISTS growth_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_crop_id INTEGER NOT NULL,
    recorded_at DATE NOT NULL,
    notes TEXT,
    image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (location_crop_id) REFERENCES location_crops(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_growth_records_location_crop ON growth_records(location_crop_id);
CREATE INDEX IF NOT EXISTS idx_growth_records_date ON growth_records(recorded_at DESC);
