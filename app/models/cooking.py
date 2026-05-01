from app.database import get_db
from app.utils.timezone import get_jst_now


class Cooking:
    """料理モデル"""

    @staticmethod
    def get_all(limit=None, offset=None):
        """全料理を取得（ページネーション対応）"""
        db = get_db()
        query = 'SELECT * FROM cooking ORDER BY cooked_date DESC, created_at DESC'
        params = []

        if limit:
            query += ' LIMIT ?'
            params.append(limit)
            if offset:
                query += ' OFFSET ?'
                params.append(offset)

        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(cooking_id):
        """IDで料理を取得"""
        db = get_db()
        row = db.execute('SELECT * FROM cooking WHERE id = ?', (cooking_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        """料理を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO cooking (title, category, notes, image_path, cooked_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (data['title'], data.get('category'), data.get('notes'),
             data.get('image_path'), data['cooked_date'], now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(cooking_id, data):
        """料理を更新"""
        db = get_db()
        db.execute(
            '''UPDATE cooking SET title = ?, category = ?, notes = ?,
               image_path = ?, cooked_date = ?, updated_at = ?
               WHERE id = ?''',
            (data['title'], data.get('category'), data.get('notes'),
             data.get('image_path'), data['cooked_date'],
             get_jst_now(), cooking_id)
        )
        db.commit()

    @staticmethod
    def delete(cooking_id):
        """料理を削除"""
        db = get_db()
        db.execute('DELETE FROM cooking WHERE id = ?', (cooking_id,))
        db.commit()

    @staticmethod
    def count():
        """料理の総数を取得"""
        db = get_db()
        result = db.execute('SELECT COUNT(*) as count FROM cooking').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def search(keyword=None, category=None):
        """料理を検索"""
        db = get_db()
        query = 'SELECT * FROM cooking WHERE 1=1'
        params = []

        if keyword:
            query += ' AND (title LIKE ? OR notes LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        if category:
            query += ' AND category = ?'
            params.append(category)

        query += ' ORDER BY cooked_date DESC, created_at DESC'
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_categories():
        """登録済みカテゴリ一覧を取得"""
        db = get_db()
        rows = db.execute(
            'SELECT DISTINCT category FROM cooking WHERE category IS NOT NULL AND category != "" ORDER BY category'
        ).fetchall()
        return [r['category'] for r in rows]

    @staticmethod
    def get_recent(limit=5):
        """最新の料理を取得"""
        db = get_db()
        rows = db.execute(
            'SELECT * FROM cooking ORDER BY cooked_date DESC, created_at DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_relations(cooking_id):
        """料理に関連するデータを取得"""
        db = get_db()

        crops = db.execute(
            '''SELECT cr.crop_id, c.name as crop_name, c.crop_type, NULL as variety,
                      c.icon_path, c.image_color, c.image_path as crop_image_path
               FROM cooking_relations cr
               JOIN crops c ON cr.crop_id = c.id
               WHERE cr.cooking_id = ? AND cr.relation_type = 'crop' ''',
            (cooking_id,)
        ).fetchall()

        varieties = db.execute(
            '''SELECT cr.variety_id, v.name as variety,
                      c.id as crop_id, c.name as crop_name, c.crop_type,
                      COALESCE(v.icon_path, c.icon_path) as icon_path,
                      COALESCE(v.image_color, c.image_color) as image_color,
                      COALESCE(v.image_path, c.image_path) as variety_image_path
               FROM cooking_relations cr
               JOIN varieties v ON cr.variety_id = v.id
               JOIN crops c ON v.crop_id = c.id
               WHERE cr.cooking_id = ? AND cr.relation_type = 'variety' ''',
            (cooking_id,)
        ).fetchall()

        location_crops = db.execute(
            '''SELECT lc.id as id, lc.id as location_crop_id, cv.crop_name, cv.variety,
                      cv.icon_path, cv.image_color, l.name as location_name,
                      lc.location_id, lc.planted_date, lc.status,
                      (SELECT pr.image_path FROM planting_records pr
                       WHERE pr.location_crop_id = lc.id AND pr.image_path IS NOT NULL AND pr.image_path != ''
                       ORDER BY pr.recorded_at DESC, pr.created_at DESC LIMIT 1) as latest_record_image
               FROM cooking_relations cr
               JOIN plantings lc ON cr.location_crop_id = lc.id
               JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1) AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
               JOIN locations l ON lc.location_id = l.id
               WHERE cr.cooking_id = ? AND cr.relation_type = 'location_crop' ''',
            (cooking_id,)
        ).fetchall()

        harvests = db.execute(
            '''SELECT h.id as id, h.id as harvest_id, h.harvest_date, h.quantity, h.unit,
                      h.image_path,
                      cv.crop_name, cv.variety, cv.icon_path, cv.image_color,
                      l.name as location_name
               FROM cooking_relations cr
               JOIN harvests h ON cr.harvest_id = h.id
               JOIN plantings lc ON h.location_crop_id = lc.id
               JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1) AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
               JOIN locations l ON lc.location_id = l.id
               WHERE cr.cooking_id = ? AND cr.relation_type = 'harvest' ''',
            (cooking_id,)
        ).fetchall()

        return {
            'crops': [dict(c) for c in crops],
            'varieties': [dict(v) for v in varieties],
            'location_crops': [dict(lc) for lc in location_crops],
            'harvests': [dict(h) for h in harvests]
        }

    @staticmethod
    def save_relations(cooking_id, relations):
        """料理の関連を保存"""
        db = get_db()
        db.execute('DELETE FROM cooking_relations WHERE cooking_id = ?', (cooking_id,))

        for crop_id in relations.get('crop_ids', []):
            db.execute(
                "INSERT INTO cooking_relations (cooking_id, relation_type, crop_id) VALUES (?, 'crop', ?)",
                (cooking_id, crop_id)
            )

        for variety_id in relations.get('variety_ids', []):
            db.execute(
                "INSERT INTO cooking_relations (cooking_id, relation_type, variety_id) VALUES (?, 'variety', ?)",
                (cooking_id, variety_id)
            )

        for location_crop_id in relations.get('location_crop_ids', []):
            db.execute(
                "INSERT INTO cooking_relations (cooking_id, relation_type, location_crop_id) VALUES (?, 'location_crop', ?)",
                (cooking_id, location_crop_id)
            )

        for harvest_id in relations.get('harvest_ids', []):
            db.execute(
                "INSERT INTO cooking_relations (cooking_id, relation_type, harvest_id) VALUES (?, 'harvest', ?)",
                (cooking_id, harvest_id)
            )

        db.commit()

    @staticmethod
    def get_adjacent(cooking_id):
        """現在の料理の前後の料理を取得"""
        db = get_db()
        row = db.execute(
            'SELECT id, cooked_date, created_at FROM cooking WHERE id = ?',
            (cooking_id,)
        ).fetchone()
        if not row:
            return None, None

        prev_row = db.execute(
            '''SELECT id, title, cooked_date FROM cooking
               WHERE (cooked_date < :date)
                  OR (cooked_date = :date AND created_at < :created_at)
                  OR (cooked_date = :date AND created_at = :created_at AND id < :id)
               ORDER BY cooked_date DESC, created_at DESC, id DESC
               LIMIT 1''',
            {'date': row['cooked_date'], 'created_at': row['created_at'], 'id': row['id']}
        ).fetchone()

        next_row = db.execute(
            '''SELECT id, title, cooked_date FROM cooking
               WHERE (cooked_date > :date)
                  OR (cooked_date = :date AND created_at > :created_at)
                  OR (cooked_date = :date AND created_at = :created_at AND id > :id)
               ORDER BY cooked_date ASC, created_at ASC, id ASC
               LIMIT 1''',
            {'date': row['cooked_date'], 'created_at': row['created_at'], 'id': row['id']}
        ).fetchone()

        return (dict(prev_row) if prev_row else None,
                dict(next_row) if next_row else None)
