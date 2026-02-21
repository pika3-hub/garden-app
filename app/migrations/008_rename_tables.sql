-- location_crops → plantings テーブルリネーム
ALTER TABLE location_crops RENAME TO plantings;

-- growth_records → planting_records テーブルリネーム
ALTER TABLE growth_records RENAME TO planting_records;

-- インデックス名を新テーブル名に合わせて整理
DROP INDEX IF EXISTS idx_location_crops_location;
DROP INDEX IF EXISTS idx_location_crops_crop;
DROP INDEX IF EXISTS idx_location_crops_status;
CREATE INDEX IF NOT EXISTS idx_plantings_location ON plantings(location_id);
CREATE INDEX IF NOT EXISTS idx_plantings_crop ON plantings(crop_id);
CREATE INDEX IF NOT EXISTS idx_plantings_status ON plantings(status);

DROP INDEX IF EXISTS idx_growth_records_location_crop;
DROP INDEX IF EXISTS idx_growth_records_date;
CREATE INDEX IF NOT EXISTS idx_planting_records_location_crop ON planting_records(location_crop_id);
CREATE INDEX IF NOT EXISTS idx_planting_records_date ON planting_records(recorded_at DESC);

-- schema.sql の再実行で作成された空の旧テーブルを削除（冪等性のため）
DROP TABLE IF EXISTS location_crops;
DROP TABLE IF EXISTS growth_records;
