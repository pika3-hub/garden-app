-- 植え付け (plantings) の作物ID・品種ID管理を排他化する
-- - crop_id を nullable 化 + CHECK 制約（crop_id XOR variety_id）
-- - variety_id の FK を ON DELETE SET NULL → CASCADE に変更
-- - 品種削除時に親作物に昇格させる BEFORE DELETE トリガーを追加
-- - crop_variety_view を再構築（品種行は crop_id=NULL, effective_crop_id を追加）

PRAGMA foreign_keys = OFF;

-- plantings を参照する VIEW とトリガーを先に削除（テーブル再作成時の参照エラー回避）
DROP VIEW IF EXISTS crop_variety_view;
DROP TRIGGER IF EXISTS trg_promote_variety_plantings_before_delete;

-- 念のため中間テーブルをクリア
DROP TABLE IF EXISTS plantings_new;

-- 新スキーマで中間テーブルを作成
CREATE TABLE plantings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    crop_id INTEGER DEFAULT NULL,
    variety_id INTEGER DEFAULT NULL,
    planted_date DATE,
    quantity INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    position_x DECIMAL(10, 2) DEFAULT NULL,
    position_y DECIMAL(10, 2) DEFAULT NULL,
    end_date DATE DEFAULT NULL,
    canvas_snapshot TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    updated_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    CHECK (
        (crop_id IS NOT NULL AND variety_id IS NULL) OR
        (crop_id IS NULL AND variety_id IS NOT NULL)
    ),
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY (crop_id)     REFERENCES crops(id)     ON DELETE CASCADE,
    FOREIGN KEY (variety_id)  REFERENCES varieties(id) ON DELETE CASCADE
);

-- データ移行: variety_id がある行は crop_id を NULL に変換
INSERT INTO plantings_new (
    id, location_id, crop_id, variety_id, planted_date, quantity, status,
    notes, position_x, position_y, end_date, canvas_snapshot,
    created_at, updated_at
)
SELECT
    id,
    location_id,
    CASE WHEN variety_id IS NOT NULL THEN NULL ELSE crop_id END AS crop_id,
    variety_id,
    planted_date, quantity, status,
    notes, position_x, position_y, end_date, canvas_snapshot,
    created_at, updated_at
FROM plantings;

-- 旧テーブルを削除して新テーブルをリネーム
DROP TABLE plantings;
ALTER TABLE plantings_new RENAME TO plantings;

-- インデックス再作成
CREATE INDEX IF NOT EXISTS idx_plantings_location ON plantings(location_id);
CREATE INDEX IF NOT EXISTS idx_plantings_crop     ON plantings(crop_id);
CREATE INDEX IF NOT EXISTS idx_plantings_variety  ON plantings(variety_id);
CREATE INDEX IF NOT EXISTS idx_plantings_status   ON plantings(status);

-- 品種単独削除時に親作物の植え付けへ昇格させるトリガーを再作成
-- （crop_id をセットしておくことで FK CASCADE の対象から外れ、植え付けは残る）
CREATE TRIGGER trg_promote_variety_plantings_before_delete
BEFORE DELETE ON varieties
FOR EACH ROW
BEGIN
    UPDATE plantings
       SET crop_id = OLD.crop_id, variety_id = NULL
     WHERE variety_id = OLD.id;
END;

-- VIEW を新仕様で再作成
-- 品種行は crop_id=NULL（plantings の品種行とマッチするため）
-- effective_crop_id は集計・「作物Xの植え付け一覧」用に常に crops.id を持つ
CREATE VIEW crop_variety_view AS
SELECT
    NULL AS crop_id,
    v.id AS variety_id,
    c.id AS effective_crop_id,
    c.name AS crop_name,
    c.crop_type,
    v.name AS variety,
    COALESCE(v.notes, c.notes)             AS notes,
    COALESCE(v.icon_path, c.icon_path)     AS icon_path,
    COALESCE(v.image_color, c.image_color) AS image_color,
    COALESCE(v.image_path, c.image_path)   AS image_path
FROM varieties v
JOIN crops c ON v.crop_id = c.id
UNION ALL
SELECT
    c.id AS crop_id,
    NULL AS variety_id,
    c.id AS effective_crop_id,
    c.name AS crop_name,
    c.crop_type,
    NULL AS variety,
    c.notes,
    c.icon_path,
    c.image_color,
    c.image_path
FROM crops c;

PRAGMA foreign_keys = ON;
