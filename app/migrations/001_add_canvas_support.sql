-- キャンバス機能追加マイグレーション
-- 実行日: 2026-01-04

-- locationsテーブルにcanvas_dataカラム追加
ALTER TABLE locations ADD COLUMN canvas_data TEXT DEFAULT NULL;

-- location_cropsテーブルに位置情報カラム追加
ALTER TABLE location_crops ADD COLUMN position_x DECIMAL(10, 2) DEFAULT NULL;
ALTER TABLE location_crops ADD COLUMN position_y DECIMAL(10, 2) DEFAULT NULL;
