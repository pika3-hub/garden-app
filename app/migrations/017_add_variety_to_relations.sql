-- 日記・タスクの関連付けに品種(variety_id)を追加
-- Migration: 017_add_variety_to_relations
-- relation_type='variety' の行で variety_id をセットし、
-- crop（作物）と排他的に「品種としての関連付け」を表現する。

ALTER TABLE diary_relations ADD COLUMN variety_id INTEGER REFERENCES varieties(id) ON DELETE CASCADE;
ALTER TABLE task_relations  ADD COLUMN variety_id INTEGER REFERENCES varieties(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_diary_relations_variety ON diary_relations(variety_id);
CREATE INDEX IF NOT EXISTS idx_task_relations_variety  ON task_relations(variety_id);
