from app.database import get_db
from app.models.planting import _CV_JOIN


def _crop_label(crop_name, variety):
    return f'{crop_name}（{variety}）' if variety else crop_name


# 使用先の種類ごとの (SQL, 行→ラベル)。SQL は id を IN (...) で絞る {ph} を持つ
_LABEL_QUERIES = {
    'crop': ('SELECT id, name FROM crops WHERE id IN ({ph})', lambda r: r['name']),
    'variety': ('SELECT v.id, c.name AS crop_name, v.name AS variety '
                'FROM varieties v JOIN crops c ON c.id = v.crop_id WHERE v.id IN ({ph})',
                lambda r: _crop_label(r['crop_name'], r['variety'])),
    'location': ('SELECT id, name FROM locations WHERE id IN ({ph})', lambda r: r['name']),
    'planting_record': (f'SELECT pr.id, cv.crop_name, cv.variety, pr.recorded_at FROM planting_records pr '
                        f'JOIN plantings lc ON lc.id = pr.location_crop_id {_CV_JOIN} '
                        f'WHERE pr.id IN ({{ph}})',
                        lambda r: f"栽培記録 {_crop_label(r['crop_name'], r['variety'])} {r['recorded_at']}"),
    'harvest': (f'SELECT h.id, cv.crop_name, cv.variety, h.harvest_date FROM harvests h '
                f'JOIN plantings lc ON lc.id = h.location_crop_id {_CV_JOIN} '
                f'WHERE h.id IN ({{ph}})',
                lambda r: f"収穫 {_crop_label(r['crop_name'], r['variety'])} {r['harvest_date']}"),
    'planting': (f'SELECT lc.id, cv.crop_name, cv.variety, l.name AS location_name FROM plantings lc '
                 f'JOIN locations l ON l.id = lc.location_id {_CV_JOIN} '
                 f'WHERE lc.id IN ({{ph}})',
                 lambda r: f"{_crop_label(r['crop_name'], r['variety'])} {r['location_name']}"),
    'cooking': ('SELECT id, title FROM cooking WHERE id IN ({ph})', lambda r: r['title']),
    'diary': ('SELECT id, title FROM diary_entries WHERE id IN ({ph})', lambda r: r['title']),
    'task': ('SELECT id, title FROM tasks WHERE id IN ({ph})', lambda r: r['title']),
}


def _labels(db, entity_type, ids):
    """{id: ラベル}。未知の種類・削除済みの id は含まない"""
    query = _LABEL_QUERIES.get(entity_type)
    if not query or not ids:
        return {}
    sql, to_label = query
    ids = tuple(ids)
    rows = db.execute(sql.format(ph=','.join('?' * len(ids))), ids).fetchall()
    return {r['id']: to_label(r) for r in rows}


def _supplement_parents(db, supplement_ids):
    """{補足情報id: (親の entity_type, 親の entity_id)}"""
    if not supplement_ids:
        return {}
    ids = tuple(supplement_ids)
    rows = db.execute(
        f'SELECT id, entity_type, entity_id FROM supplements WHERE id IN ({",".join("?" * len(ids))})',
        ids
    ).fetchall()
    return {r['id']: (r['entity_type'], r['entity_id']) for r in rows}


class PhotoPool:

    @staticmethod
    def get_all():
        """全プール写真を取得（使用回数付き、新しい順）"""
        db = get_db()
        rows = db.execute(
            '''SELECT p.*,
                      (SELECT COUNT(*) FROM photo_pool_usages u
                       WHERE u.photo_pool_id = p.id) AS usage_count
               FROM photo_pool p
               ORDER BY p.created_at DESC'''
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(photo_id):
        db = get_db()
        row = db.execute(
            '''SELECT p.*,
                      (SELECT COUNT(*) FROM photo_pool_usages u
                       WHERE u.photo_pool_id = p.id) AS usage_count
               FROM photo_pool p
               WHERE p.id = ?''',
            (photo_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(image_path, original_filename=None, file_size=None, taken_at=None):
        db = get_db()
        cursor = db.execute(
            '''INSERT INTO photo_pool (image_path, original_filename, file_size, taken_at)
               VALUES (?, ?, ?, ?)''',
            (image_path, original_filename, file_size, taken_at)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update_notes(photo_id, notes):
        db = get_db()
        db.execute(
            '''UPDATE photo_pool
               SET notes = ?, updated_at = datetime('now', '+9 hours')
               WHERE id = ?''',
            (notes, photo_id)
        )
        db.commit()

    @staticmethod
    def delete(photo_id):
        """写真削除。戻り値は削除したimage_path（ファイル削除用）"""
        db = get_db()
        row = db.execute('SELECT image_path FROM photo_pool WHERE id = ?', (photo_id,)).fetchone()
        if not row:
            return None
        db.execute('DELETE FROM photo_pool_usages WHERE photo_pool_id = ?', (photo_id,))
        db.execute('DELETE FROM photo_pool WHERE id = ?', (photo_id,))
        db.commit()
        return row['image_path']

    @staticmethod
    def delete_many(photo_ids):
        """複数写真を削除。戻り値は削除した image_path のリスト（ファイル削除用）"""
        if not photo_ids:
            return []
        db = get_db()
        placeholders = ','.join('?' * len(photo_ids))
        ids = tuple(photo_ids)
        rows = db.execute(
            f'SELECT image_path FROM photo_pool WHERE id IN ({placeholders})',
            ids
        ).fetchall()
        paths = [r['image_path'] for r in rows]
        db.execute(f'DELETE FROM photo_pool_usages WHERE photo_pool_id IN ({placeholders})', ids)
        db.execute(f'DELETE FROM photo_pool WHERE id IN ({placeholders})', ids)
        db.commit()
        return paths

    @staticmethod
    def record_usage(photo_id, entity_type, entity_id, copied_image_path):
        db = get_db()
        db.execute(
            '''INSERT INTO photo_pool_usages (photo_pool_id, entity_type, entity_id, copied_image_path)
               VALUES (?, ?, ?, ?)''',
            (photo_id, entity_type, entity_id, copied_image_path)
        )
        db.commit()

    @staticmethod
    def get_usage_links(photo_ids):
        """写真ごとの使用先一覧 {photo_id: [link, ...]}（新しい順）。

        link は entity_type / entity_id / label / target_type / target_id / created_at。
        label が None なら使用先は削除済み。target_* はリンク先で、補足情報は親を指す。
        """
        if not photo_ids:
            return {}
        db = get_db()
        placeholders = ','.join('?' * len(photo_ids))
        rows = db.execute(
            f'''SELECT * FROM photo_pool_usages
                WHERE photo_pool_id IN ({placeholders})
                ORDER BY created_at DESC, id DESC''',
            tuple(photo_ids)
        ).fetchall()

        def ids_of(entity_type, items):
            return {r['entity_id'] for r in items if r['entity_type'] == entity_type}

        sup_parents = _supplement_parents(db, ids_of('supplement', rows))
        targets = {}
        for r in rows:
            if r['entity_type'] == 'supplement':
                parent = sup_parents.get(r['entity_id'])
                if parent:
                    targets.setdefault(parent[0], set()).add(parent[1])
            else:
                targets.setdefault(r['entity_type'], set()).add(r['entity_id'])
        labels = {t: _labels(db, t, ids) for t, ids in targets.items()}

        result = {pid: [] for pid in photo_ids}
        for r in rows:
            if r['entity_type'] == 'supplement':
                target_type, target_id = sup_parents.get(r['entity_id'], (None, None))
                parent_label = labels.get(target_type, {}).get(target_id)
                label = f'{parent_label}の補足情報' if parent_label else None
            else:
                target_type, target_id = r['entity_type'], r['entity_id']
                label = labels.get(target_type, {}).get(target_id)
            result[r['photo_pool_id']].append({
                'entity_type': r['entity_type'],
                'entity_id': r['entity_id'],
                'label': label,
                'target_type': target_type if label else None,
                'target_id': target_id if label else None,
                'created_at': r['created_at'],
            })
        return result

    @staticmethod
    def get_usages(photo_id):
        db = get_db()
        rows = db.execute(
            '''SELECT * FROM photo_pool_usages
               WHERE photo_pool_id = ?
               ORDER BY created_at DESC''',
            (photo_id,)
        ).fetchall()
        return [dict(r) for r in rows]
