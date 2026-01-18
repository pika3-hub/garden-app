-- 日記と収穫記録の関連付けサポート
-- Migration: 005_add_diary_harvest_relation

-- diary_relationsテーブルにharvest_idカラムを追加
ALTER TABLE diary_relations ADD COLUMN harvest_id INTEGER REFERENCES harvests(id) ON DELETE CASCADE;

-- インデックス
CREATE INDEX IF NOT EXISTS idx_diary_relations_harvest ON diary_relations(harvest_id);
