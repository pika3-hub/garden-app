-- タスク機能のテーブル追加
-- Migration: 006_add_task_support

-- タスクテーブル
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    due_date DATE,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours'))
);

-- タスクの関連テーブル（作物・場所・植え付け場所との多対多関連）
CREATE TABLE IF NOT EXISTS task_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    relation_type VARCHAR(20) NOT NULL,
    crop_id INTEGER,
    location_id INTEGER,
    location_crop_id INTEGER,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id) REFERENCES crops(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (location_crop_id) REFERENCES location_crops(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_relations_task ON task_relations(task_id);
CREATE INDEX IF NOT EXISTS idx_task_relations_crop ON task_relations(crop_id);
CREATE INDEX IF NOT EXISTS idx_task_relations_location ON task_relations(location_id);
