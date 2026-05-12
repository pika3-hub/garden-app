"""作物エンティティを「作物」+「品種」の2エンティティに分割する1回限りのマイグレーション。

crops テーブルを (name, crop_type) で統合し、variety があるものを varieties テーブルに切り出す。
plantings に variety_id 列を追加、supplements / photo_pool_usages / canvas JSON の参照を新IDに更新。

前提:
- instance/garden.db をバックアップ済み
- Flaskサーバーは停止中

実行:
    uv run python -m app.utils.migrate_crops_split --inspect  # 実行内容のサマリーだけ表示
    uv run python -m app.utils.migrate_crops_split            # 対話確認あり
    uv run python -m app.utils.migrate_crops_split --yes      # 確認プロンプトをスキップ

トランザクション:
    isolation_level=None + 明示 BEGIN で、全DDL/DMLを単一トランザクションに包む。
    途中失敗時は ROLLBACK し、コピーした画像も後始末する。
"""

import json
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

# Windowsコンソールでも日本語/記号を安全に出せるよう UTF-8 に再設定
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / 'instance' / 'garden.db'
UPLOAD_FOLDER = BASE_DIR / 'app' / 'static' / 'uploads'


# ---------- ヘルパー ----------

def _build_markdown_notes(row):
    """旧 crops の planting_season/harvest_season/characteristics/notes を Markdown に統合"""
    sections = []
    if row.get('planting_season'):
        sections.append(f'## 植え付け時期\n{row["planting_season"]}')
    if row.get('harvest_season'):
        sections.append(f'## 収穫時期\n{row["harvest_season"]}')
    if row.get('characteristics'):
        sections.append(f'## 特性\n{row["characteristics"]}')
    if row.get('notes'):
        sections.append(f'## メモ\n{row["notes"]}')
    return '\n\n'.join(sections) if sections else None


def _generate_thumbnail(src_path, folder_dir, basename):
    try:
        from PIL import Image, ImageOps
        img = Image.open(src_path)
        if img.format == 'GIF':
            return
        img = ImageOps.exif_transpose(img)
        img.thumbnail((800, 600), Image.LANCZOS)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        thumbs_dir = folder_dir / 'thumbs'
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        img.save(thumbs_dir / f'{basename}.jpg', format='JPEG', quality=80, optimize=True)
    except Exception as e:
        print(f'    WARN: thumbnail generation failed: {e}')


def _copy_image(relative_path, dest_folder, created_paths):
    if not relative_path:
        return None
    src_full = UPLOAD_FOLDER / relative_path
    if not src_full.exists():
        print(f'    WARN: image not found, skipping: {relative_path}')
        return None
    ext = src_full.suffix.lstrip('.') or 'jpg'
    uuid_basename = uuid.uuid4().hex
    filename = f'{uuid_basename}.{ext}'
    dest_dir = UPLOAD_FOLDER / dest_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_full = dest_dir / filename
    shutil.copy2(src_full, dest_full)
    new_rel = f'{dest_folder}/{filename}'
    created_paths.append(new_rel)
    _generate_thumbnail(dest_full, dest_dir, uuid_basename)
    return new_rel


def _cleanup_created_images(created_paths):
    for rel in created_paths:
        full = UPLOAD_FOLDER / rel
        if full.exists():
            try:
                full.unlink()
            except Exception:
                pass
        parts = rel.split('/', 1)
        if len(parts) == 2:
            thumb = UPLOAD_FOLDER / parts[0] / 'thumbs' / (Path(parts[1]).stem + '.jpg')
            if thumb.exists():
                try:
                    thumb.unlink()
                except Exception:
                    pass


def _assert_preconditions(db):
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    if 'crops_new' in tables:
        raise RuntimeError('crops_new が既に存在します。前回の移行が未完了の可能性があります。')
    if 'varieties' in tables:
        raise RuntimeError('varieties が既に存在します。移行は既に実行されたようです。')
    if '_crop_id_mapping' in tables:
        raise RuntimeError('_crop_id_mapping が既に存在します。')

    views = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()]
    if 'crop_variety_view' in views:
        raise RuntimeError('crop_variety_view が既に存在します。')

    plantings_cols = [r[1] for r in db.execute('PRAGMA table_info(plantings)').fetchall()]
    if 'variety_id' in plantings_cols:
        raise RuntimeError('plantings.variety_id が既に存在します。移行は既に実行されたようです。')

    crops_cols = [r[1] for r in db.execute('PRAGMA table_info(crops)').fetchall()]
    expected = {'id', 'name', 'variety', 'crop_type', 'characteristics',
                'planting_season', 'harvest_season', 'notes',
                'image_path', 'icon_path', 'image_color'}
    missing = expected - set(crops_cols)
    if missing:
        raise RuntimeError(f'crops テーブルに想定カラムが存在しません: {missing}')


# ---------- 実行内容サマリー ----------

def inspect():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    total = db.execute('SELECT COUNT(*) FROM crops').fetchone()[0]
    with_variety = db.execute(
        'SELECT COUNT(*) FROM crops WHERE variety IS NOT NULL AND variety != ""'
    ).fetchone()[0]
    without_variety = total - with_variety

    groups = {}
    for row in db.execute('SELECT name, crop_type FROM crops').fetchall():
        groups.setdefault((row['name'], row['crop_type']), 0)
        groups[(row['name'], row['crop_type'])] += 1

    merged_groups = [(k, c) for k, c in groups.items() if c > 1]

    plantings_n = db.execute('SELECT COUNT(*) FROM plantings').fetchone()[0]
    supplements_n = db.execute(
        'SELECT COUNT(*) FROM supplements WHERE entity_type = "crop"'
    ).fetchone()[0]
    diary_rel_n = db.execute(
        'SELECT COUNT(*) FROM diary_relations WHERE relation_type = "crop" AND crop_id IS NOT NULL'
    ).fetchone()[0]
    task_rel_n = db.execute(
        'SELECT COUNT(*) FROM task_relations WHERE relation_type = "crop" AND crop_id IS NOT NULL'
    ).fetchone()[0]
    canvas_loc = db.execute(
        'SELECT COUNT(*) FROM locations WHERE canvas_data IS NOT NULL'
    ).fetchone()[0]
    canvas_plt = db.execute(
        'SELECT COUNT(*) FROM plantings WHERE canvas_snapshot IS NOT NULL'
    ).fetchone()[0]

    print('=== INSPECT: 移行対象のサマリー ===\n')
    print(f'現状 crops:               {total}')
    print(f'  うち品種あり:           {with_variety}')
    print(f'  うち品種なし:           {without_variety}')
    print(f'(name, crop_type)グループ: {len(groups)}  → 統合後の crops(新) 件数')
    print(f'  うち統合が発生するグループ (2件以上): {len(merged_groups)}')
    print(f'予想 varieties(新):        {with_variety}')
    print(f'plantings:                 {plantings_n} (全件 crop_id 更新、variety_id 設定)')
    print(f'supplements crop:          {supplements_n} (variety有無で振り分け)')
    print(f'diary_relations crop:      {diary_rel_n}')
    print(f'task_relations crop:       {task_rel_n}')
    print(f'locations.canvas_data:     {canvas_loc} (cropId 書き換え対象)')
    print(f'plantings.canvas_snapshot: {canvas_plt}')

    if merged_groups:
        print('\n--- 統合されるグループ（元レコード数 2件以上） ---')
        for (name, crop_type), c in sorted(merged_groups, key=lambda x: -x[1]):
            print(f'  {c}件  {name} / {crop_type}')

    db.close()


# ---------- 本体 ----------

def migrate():
    # isolation_level=None で自動BEGIN禁止、明示BEGIN/COMMIT/ROLLBACK
    db = sqlite3.connect(str(DB_PATH), isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = OFF')

    created_images = []

    try:
        _assert_preconditions(db)

        db.execute('BEGIN')

        # ---- STEP 0: DDL ----
        print('\n=== STEP 0: DDL ===')
        db.execute('''
            CREATE TABLE crops_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                crop_type VARCHAR(50) NOT NULL,
                notes TEXT,
                icon_path TEXT,
                image_color TEXT DEFAULT '#4CAF50',
                image_path VARCHAR(255),
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE varieties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                notes TEXT,
                icon_path TEXT,
                image_color TEXT,
                image_path VARCHAR(255),
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (crop_id) REFERENCES crops_new(id) ON DELETE CASCADE
            )
        ''')
        db.execute('CREATE INDEX idx_varieties_crop ON varieties(crop_id)')
        db.execute('''
            CREATE TABLE _crop_id_mapping (
                old_crop_id INTEGER PRIMARY KEY,
                new_crop_id INTEGER NOT NULL,
                new_variety_id INTEGER
            )
        ''')
        db.execute('ALTER TABLE plantings ADD COLUMN variety_id INTEGER DEFAULT NULL')
        db.execute('CREATE INDEX IF NOT EXISTS idx_plantings_variety ON plantings(variety_id)')

        # ---- STEP 1: 作物(新) への統合 ----
        print('\n=== STEP 1: 作物(新)への統合 ===')
        groups = {}
        for row in db.execute(
            'SELECT * FROM crops ORDER BY created_at ASC, id ASC'
        ).fetchall():
            key = (row['name'], row['crop_type'])
            groups.setdefault(key, []).append(dict(row))

        crop_new_id_by_key = {}
        for (name, crop_type), rows in groups.items():
            def first_non_null(field):
                for r in rows:
                    if r.get(field):
                        return r[field]
                return None

            icon_path = first_non_null('icon_path')
            image_color = first_non_null('image_color') or '#4CAF50'
            original_image = first_non_null('image_path')
            new_image_path = _copy_image(original_image, 'crops', created_images) if original_image else None

            variety_less_rows = [r for r in rows if not r.get('variety')]
            notes_parts = [_build_markdown_notes(r) for r in variety_less_rows]
            notes_parts = [p for p in notes_parts if p]
            notes = '\n\n---\n\n'.join(notes_parts) if notes_parts else None

            created_at = rows[0].get('created_at')
            updated_at = rows[-1].get('updated_at') or created_at

            cursor = db.execute(
                '''INSERT INTO crops_new (name, crop_type, notes, icon_path,
                   image_color, image_path, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, crop_type, notes, icon_path, image_color,
                 new_image_path, created_at, updated_at)
            )
            crop_new_id_by_key[(name, crop_type)] = cursor.lastrowid
            print(f'  [{cursor.lastrowid}] {name} / {crop_type} '
                  f'(元={len(rows)}, 品種なし={len(variety_less_rows)})')

        # ---- STEP 2: 品種(新) への移行 ----
        print('\n=== STEP 2: 品種(新)への移行 ===')
        new_variety_id_by_old_crop_id = {}
        for row in db.execute(
            'SELECT * FROM crops WHERE variety IS NOT NULL AND variety != "" '
            'ORDER BY created_at ASC, id ASC'
        ).fetchall():
            old = dict(row)
            parent_crop_id = crop_new_id_by_key[(old['name'], old['crop_type'])]

            new_image_path = _copy_image(old['image_path'], 'varieties', created_images) if old['image_path'] else None
            md = _build_markdown_notes(old)

            cursor = db.execute(
                '''INSERT INTO varieties (crop_id, name, notes, icon_path,
                   image_color, image_path, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (parent_crop_id, old['variety'], md,
                 old['icon_path'], old['image_color'], new_image_path,
                 old['created_at'], old.get('updated_at') or old['created_at'])
            )
            new_variety_id_by_old_crop_id[old['id']] = cursor.lastrowid
            print(f'  v[{cursor.lastrowid}] crop={parent_crop_id} {old["variety"]}（{old["name"]}）')

        # ---- STEP 3: ID変換テーブル ----
        print('\n=== STEP 3: ID変換テーブル ===')
        for row in db.execute('SELECT id, name, crop_type FROM crops').fetchall():
            old_id = row['id']
            new_cid = crop_new_id_by_key[(row['name'], row['crop_type'])]
            new_vid = new_variety_id_by_old_crop_id.get(old_id)
            db.execute(
                'INSERT INTO _crop_id_mapping (old_crop_id, new_crop_id, new_variety_id) VALUES (?, ?, ?)',
                (old_id, new_cid, new_vid)
            )
        total_map = db.execute('SELECT COUNT(*) FROM _crop_id_mapping').fetchone()[0]
        print(f'  mappings: {total_map}')

        # ---- STEP 4: 参照テーブル更新 ----
        print('\n=== STEP 4: 参照テーブル更新 ===')

        n = db.execute(
            '''UPDATE plantings
               SET crop_id = (SELECT new_crop_id FROM _crop_id_mapping WHERE old_crop_id = plantings.crop_id),
                   variety_id = (SELECT new_variety_id FROM _crop_id_mapping WHERE old_crop_id = plantings.crop_id)
               WHERE crop_id IN (SELECT old_crop_id FROM _crop_id_mapping)'''
        ).rowcount
        print(f'  plantings: {n}')

        n = db.execute(
            '''UPDATE diary_relations
               SET crop_id = (SELECT new_crop_id FROM _crop_id_mapping WHERE old_crop_id = diary_relations.crop_id)
               WHERE relation_type = 'crop'
                 AND crop_id IN (SELECT old_crop_id FROM _crop_id_mapping)'''
        ).rowcount
        print(f'  diary_relations: {n}')

        n = db.execute(
            '''UPDATE task_relations
               SET crop_id = (SELECT new_crop_id FROM _crop_id_mapping WHERE old_crop_id = task_relations.crop_id)
               WHERE relation_type = 'crop'
                 AND crop_id IN (SELECT old_crop_id FROM _crop_id_mapping)'''
        ).rowcount
        print(f'  task_relations: {n}')

        n_c = n_v = 0
        for r in db.execute(
            'SELECT id, entity_id FROM supplements WHERE entity_type = "crop"'
        ).fetchall():
            m = db.execute(
                'SELECT new_crop_id, new_variety_id FROM _crop_id_mapping WHERE old_crop_id = ?',
                (r['entity_id'],)
            ).fetchone()
            if not m:
                continue
            if m['new_variety_id']:
                db.execute(
                    'UPDATE supplements SET entity_type = "variety", entity_id = ? WHERE id = ?',
                    (m['new_variety_id'], r['id'])
                )
                n_v += 1
            else:
                db.execute(
                    'UPDATE supplements SET entity_id = ? WHERE id = ?',
                    (m['new_crop_id'], r['id'])
                )
                n_c += 1
        print(f'  supplements: crop={n_c}, variety={n_v}')

        n_c = n_v = 0
        for r in db.execute(
            'SELECT id, entity_id FROM photo_pool_usages WHERE entity_type = "crop"'
        ).fetchall():
            m = db.execute(
                'SELECT new_crop_id, new_variety_id FROM _crop_id_mapping WHERE old_crop_id = ?',
                (r['entity_id'],)
            ).fetchone()
            if not m:
                continue
            if m['new_variety_id']:
                db.execute(
                    'UPDATE photo_pool_usages SET entity_type = "variety", entity_id = ? WHERE id = ?',
                    (m['new_variety_id'], r['id'])
                )
                n_v += 1
            else:
                db.execute(
                    'UPDATE photo_pool_usages SET entity_id = ? WHERE id = ?',
                    (m['new_crop_id'], r['id'])
                )
                n_c += 1
        print(f'  photo_pool_usages: crop={n_c}, variety={n_v}')

        # ---- STEP 5: canvas JSON 書き換え ----
        print('\n=== STEP 5: canvas JSON 書き換え ===')

        def remap_json(json_str):
            if not json_str:
                return None
            try:
                data = json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                return None
            if data.get('version') != '2.0':
                return None
            changed = False
            for p in data.get('placements', []):
                old_cid = p.get('cropId')
                if old_cid:
                    m = db.execute(
                        'SELECT new_crop_id FROM _crop_id_mapping WHERE old_crop_id = ?',
                        (old_cid,)
                    ).fetchone()
                    if m:
                        p['cropId'] = m['new_crop_id']
                        changed = True
            return json.dumps(data, ensure_ascii=False) if changed else None

        n = 0
        for r in db.execute(
            'SELECT id, canvas_data FROM locations WHERE canvas_data IS NOT NULL'
        ).fetchall():
            new_json = remap_json(r['canvas_data'])
            if new_json:
                db.execute('UPDATE locations SET canvas_data = ? WHERE id = ?',
                           (new_json, r['id']))
                n += 1
        print(f'  locations.canvas_data: {n}')

        n = 0
        for r in db.execute(
            'SELECT id, canvas_snapshot FROM plantings WHERE canvas_snapshot IS NOT NULL'
        ).fetchall():
            new_json = remap_json(r['canvas_snapshot'])
            if new_json:
                db.execute('UPDATE plantings SET canvas_snapshot = ? WHERE id = ?',
                           (new_json, r['id']))
                n += 1
        print(f'  plantings.canvas_snapshot: {n}')

        # ---- STEP 6: リネーム + VIEW ----
        print('\n=== STEP 6: テーブルリネーム + VIEW 作成 ===')
        db.execute('DROP TABLE crops')
        db.execute('ALTER TABLE crops_new RENAME TO crops')
        db.execute('''
            CREATE VIEW crop_variety_view AS
            SELECT
                c.id AS crop_id,
                v.id AS variety_id,
                c.name AS crop_name,
                c.crop_type,
                v.name AS variety,
                COALESCE(v.notes, c.notes) AS notes,
                COALESCE(v.icon_path, c.icon_path) AS icon_path,
                COALESCE(v.image_color, c.image_color) AS image_color,
                COALESCE(v.image_path, c.image_path) AS image_path
            FROM crops c
            JOIN varieties v ON v.crop_id = c.id
            UNION ALL
            SELECT
                c.id AS crop_id,
                NULL AS variety_id,
                c.name AS crop_name,
                c.crop_type,
                NULL AS variety,
                c.notes,
                c.icon_path,
                c.image_color,
                c.image_path
            FROM crops c
        ''')
        db.execute('DROP TABLE _crop_id_mapping')

        # ---- 検証サマリー ----
        print('\n=== 検証サマリー ===')
        n_crops = db.execute('SELECT COUNT(*) FROM crops').fetchone()[0]
        n_varieties = db.execute('SELECT COUNT(*) FROM varieties').fetchone()[0]
        n_plt = db.execute('SELECT COUNT(*) FROM plantings').fetchone()[0]
        n_plt_v = db.execute('SELECT COUNT(*) FROM plantings WHERE variety_id IS NOT NULL').fetchone()[0]
        n_sup_c = db.execute("SELECT COUNT(*) FROM supplements WHERE entity_type = 'crop'").fetchone()[0]
        n_sup_v = db.execute("SELECT COUNT(*) FROM supplements WHERE entity_type = 'variety'").fetchone()[0]
        orphan_plantings = db.execute(
            'SELECT COUNT(*) FROM plantings WHERE crop_id NOT IN (SELECT id FROM crops)'
        ).fetchone()[0]
        print(f'  crops (new): {n_crops}')
        print(f'  varieties: {n_varieties}')
        print(f'  plantings total: {n_plt}')
        print(f'  plantings with variety_id: {n_plt_v}')
        print(f'  supplements crop: {n_sup_c}')
        print(f'  supplements variety: {n_sup_v}')
        print(f'  orphan plantings (要0): {orphan_plantings}')
        if orphan_plantings > 0:
            raise RuntimeError('検証失敗: 孤児 plantings が存在します。ROLLBACK します。')

        db.execute('COMMIT')
        print('\n=== COMMIT 完了 ===')
        return 0

    except Exception as e:
        print(f'\nERROR: {e}')
        import traceback
        traceback.print_exc()
        try:
            db.execute('ROLLBACK')
        except Exception:
            pass
        _cleanup_created_images(created_images)
        return 1
    finally:
        db.close()


def main():
    if '--inspect' in sys.argv:
        inspect()
        return 0

    skip_confirm = '--yes' in sys.argv

    print(f'作物エンティティ分割マイグレーション')
    print(f'DB: {DB_PATH}')
    if not skip_confirm:
        print('\n*** 実行前に instance/garden.db のバックアップを取得していることを確認してください ***')
        ans = input('続行しますか? [y/N]: ').strip().lower()
        if ans != 'y':
            print('中止しました')
            return 2
    return migrate()


if __name__ == '__main__':
    sys.exit(main())
