-- 新規 DB で diary_entries.image_path が無い問題の修正
-- Migration: 021_ensure_diary_image_path
--
-- 003 は crops.image_path の追加が schema.sql と重複してエラーになり、
-- 同じスクリプト内の diary_entries.image_path の追加まで到達しなかった。
-- 既存 DB では duplicate column の警告になるだけで何も変わらない。
ALTER TABLE diary_entries ADD COLUMN image_path VARCHAR(255);
