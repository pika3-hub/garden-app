-- Hermes のアドバイスの保存テーブル
-- Migration: 024_add_advices
--
-- 起動のたびに実行されるので IF NOT EXISTS で何度実行しても同じ結果にする。
CREATE TABLE IF NOT EXISTS advices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    question TEXT,
    answer TEXT NOT NULL,
    advised_on DATE NOT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);
CREATE INDEX IF NOT EXISTS idx_advices_advised_on ON advices(advised_on DESC);

CREATE TABLE IF NOT EXISTS advice_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    advice_id INTEGER NOT NULL,
    relation_type VARCHAR(20) NOT NULL,
    crop_id INTEGER,
    variety_id INTEGER,
    location_crop_id INTEGER,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (advice_id) REFERENCES advices(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE CASCADE,
    FOREIGN KEY (variety_id) REFERENCES varieties(id) ON DELETE CASCADE,
    FOREIGN KEY (location_crop_id) REFERENCES plantings(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_advice_relations_advice ON advice_relations(advice_id);
CREATE INDEX IF NOT EXISTS idx_advice_relations_crop ON advice_relations(crop_id);
CREATE INDEX IF NOT EXISTS idx_advice_relations_variety ON advice_relations(variety_id);
CREATE INDEX IF NOT EXISTS idx_advice_relations_location_crop ON advice_relations(location_crop_id);

-- 品種を消したら、その品種に付いたアドバイスは親作物への関連に付け替える（重複は先に消す）
CREATE TRIGGER IF NOT EXISTS trg_promote_variety_advice_relations_before_delete
BEFORE DELETE ON varieties
FOR EACH ROW
BEGIN
    DELETE FROM advice_relations
     WHERE variety_id = OLD.id
       AND advice_id IN (SELECT advice_id FROM advice_relations
                          WHERE relation_type = 'crop' AND crop_id = OLD.crop_id);
    UPDATE advice_relations
       SET relation_type = 'crop', crop_id = OLD.crop_id, variety_id = NULL
     WHERE variety_id = OLD.id;
END;
