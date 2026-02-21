-- migration 008 で名前変更されたテーブルの残骸をクリーンアップ
-- schema.sql + 旧 migration の再実行で作成された空テーブルを削除する（冪等）
DROP TABLE IF EXISTS location_crops;
DROP TABLE IF EXISTS growth_records;
