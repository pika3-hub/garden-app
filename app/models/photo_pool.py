from app.database import get_db


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
    def get_usages(photo_id):
        db = get_db()
        rows = db.execute(
            '''SELECT * FROM photo_pool_usages
               WHERE photo_pool_id = ?
               ORDER BY created_at DESC''',
            (photo_id,)
        ).fetchall()
        return [dict(r) for r in rows]
