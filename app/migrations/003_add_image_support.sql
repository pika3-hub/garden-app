-- 画像添付機能のカラム追加
-- Migration: 003_add_image_support

-- crops テーブルに画像パスカラム追加
ALTER TABLE crops ADD COLUMN image_path VARCHAR(255);

-- locations テーブルに画像パスカラム追加
ALTER TABLE locations ADD COLUMN image_path VARCHAR(255);

-- diary_entries テーブルに画像パスカラム追加
ALTER TABLE diary_entries ADD COLUMN image_path VARCHAR(255);
