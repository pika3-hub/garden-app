from app.database import get_db
from app.utils.timezone import get_jst_now


class DiaryEntry:
    """日記エントリモデル"""

    @staticmethod
    def get_all(limit=None, offset=None):
        """全日記を取得（ページネーション対応）"""
        db = get_db()
        query = 'SELECT * FROM diary_entries ORDER BY entry_date DESC, created_at DESC'
        params = []

        if limit:
            query += ' LIMIT ?'
            params.append(limit)
            if offset:
                query += ' OFFSET ?'
                params.append(offset)

        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_by_id(diary_id):
        """IDで日記を取得"""
        db = get_db()
        entry = db.execute(
            'SELECT * FROM diary_entries WHERE id = ?',
            (diary_id,)
        ).fetchone()
        return dict(entry) if entry else None

    @staticmethod
    def create(data):
        """日記を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO diary_entries (title, content, entry_date, weather, status, image_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['title'], data.get('content'), data['entry_date'],
             data.get('weather'), data.get('status', 'published'), data.get('image_path'),
             now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(diary_id, data):
        """日記を更新"""
        db = get_db()
        db.execute(
            '''UPDATE diary_entries SET title = ?, content = ?, entry_date = ?,
               weather = ?, status = ?, image_path = ?, updated_at = ?
               WHERE id = ?''',
            (data['title'], data.get('content'), data['entry_date'],
             data.get('weather'), data.get('status', 'published'), data.get('image_path'),
             get_jst_now(), diary_id)
        )
        db.commit()

    @staticmethod
    def delete(diary_id):
        """日記を削除"""
        db = get_db()
        db.execute('DELETE FROM diary_entries WHERE id = ?', (diary_id,))
        db.commit()

    @staticmethod
    def count():
        """日記の総数を取得"""
        db = get_db()
        result = db.execute('SELECT COUNT(*) as count FROM diary_entries').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def search(keyword, date_from=None, date_to=None):
        """日記を検索"""
        db = get_db()
        query = '''SELECT * FROM diary_entries WHERE 1=1'''
        params = []

        if keyword:
            query += ' AND (title LIKE ? OR content LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        if date_from:
            query += ' AND entry_date >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND entry_date <= ?'
            params.append(date_to)

        query += ' ORDER BY entry_date DESC, created_at DESC'

        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_recent(limit=5):
        """最新の日記を取得"""
        db = get_db()
        entries = db.execute(
            '''SELECT * FROM diary_entries
               ORDER BY entry_date DESC, created_at DESC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_relations(diary_id):
        """日記に関連するデータを取得"""
        db = get_db()

        # 関連する作物を取得（作物レベルの関連のため variety は NULL）
        crops = db.execute(
            '''SELECT dr.crop_id, c.name as crop_name, c.crop_type, NULL as variety,
                      c.icon_path, c.image_color, c.image_path as crop_image_path
               FROM diary_relations dr
               JOIN crops c ON dr.crop_id = c.id
               WHERE dr.diary_id = ? AND dr.relation_type = 'crop' ''',
            (diary_id,)
        ).fetchall()

        # 関連する品種を取得（外観・メモは親作物から継承）
        varieties = db.execute(
            '''SELECT dr.variety_id, v.name as variety,
                      c.id as crop_id, c.name as crop_name, c.crop_type,
                      COALESCE(v.icon_path, c.icon_path) as icon_path,
                      COALESCE(v.image_color, c.image_color) as image_color,
                      COALESCE(v.image_path, c.image_path) as variety_image_path
               FROM diary_relations dr
               JOIN varieties v ON dr.variety_id = v.id
               JOIN crops c ON v.crop_id = c.id
               WHERE dr.diary_id = ? AND dr.relation_type = 'variety' ''',
            (diary_id,)
        ).fetchall()

        # 関連する場所を取得
        locations = db.execute(
            '''SELECT dr.location_id, l.name as location_name, l.location_type,
                      l.image_path as location_image_path
               FROM diary_relations dr
               JOIN locations l ON dr.location_id = l.id
               WHERE dr.diary_id = ? AND dr.relation_type = 'location' ''',
            (diary_id,)
        ).fetchall()

        # 関連する植え付け場所を取得
        location_crops = db.execute(
            '''SELECT lc.id as id, lc.id as location_crop_id, cv.crop_name, cv.variety,
                      cv.icon_path, cv.image_color, l.name as location_name,
                      lc.location_id, lc.planted_date, lc.status,
                      (SELECT pr.image_path FROM planting_records pr
                       WHERE pr.location_crop_id = lc.id AND pr.image_path IS NOT NULL AND pr.image_path != ''
                       ORDER BY pr.recorded_at DESC, pr.created_at DESC LIMIT 1) as latest_record_image
               FROM diary_relations dr
               JOIN plantings lc ON dr.location_crop_id = lc.id
               JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1) AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
               JOIN locations l ON lc.location_id = l.id
               WHERE dr.diary_id = ? AND dr.relation_type = 'location_crop' ''',
            (diary_id,)
        ).fetchall()

        # 関連する収穫記録を取得
        harvests = db.execute(
            '''SELECT h.id as id, h.id as harvest_id, h.harvest_date, h.quantity, h.unit,
                      h.image_path,
                      cv.crop_name, cv.variety, cv.icon_path, cv.image_color,
                      l.name as location_name
               FROM diary_relations dr
               JOIN harvests h ON dr.harvest_id = h.id
               JOIN plantings lc ON h.location_crop_id = lc.id
               JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1) AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
               JOIN locations l ON lc.location_id = l.id
               WHERE dr.diary_id = ? AND dr.relation_type = 'harvest' ''',
            (diary_id,)
        ).fetchall()

        return {
            'crops': [dict(c) for c in crops],
            'varieties': [dict(v) for v in varieties],
            'locations': [dict(l) for l in locations],
            'location_crops': [dict(lc) for lc in location_crops],
            'harvests': [dict(h) for h in harvests]
        }

    @staticmethod
    def save_relations(diary_id, relations):
        """日記の関連を保存"""
        db = get_db()

        # 既存の関連を削除
        db.execute('DELETE FROM diary_relations WHERE diary_id = ?', (diary_id,))

        # 作物の関連を保存
        for crop_id in relations.get('crop_ids', []):
            db.execute(
                '''INSERT INTO diary_relations (diary_id, relation_type, crop_id)
                   VALUES (?, 'crop', ?)''',
                (diary_id, crop_id)
            )

        # 品種の関連を保存
        for variety_id in relations.get('variety_ids', []):
            db.execute(
                '''INSERT INTO diary_relations (diary_id, relation_type, variety_id)
                   VALUES (?, 'variety', ?)''',
                (diary_id, variety_id)
            )

        # 場所の関連を保存
        for location_id in relations.get('location_ids', []):
            db.execute(
                '''INSERT INTO diary_relations (diary_id, relation_type, location_id)
                   VALUES (?, 'location', ?)''',
                (diary_id, location_id)
            )

        # 植え付け場所の関連を保存
        for location_crop_id in relations.get('location_crop_ids', []):
            db.execute(
                '''INSERT INTO diary_relations (diary_id, relation_type, location_crop_id)
                   VALUES (?, 'location_crop', ?)''',
                (diary_id, location_crop_id)
            )

        # 収穫記録の関連を保存
        for harvest_id in relations.get('harvest_ids', []):
            db.execute(
                '''INSERT INTO diary_relations (diary_id, relation_type, harvest_id)
                   VALUES (?, 'harvest', ?)''',
                (diary_id, harvest_id)
            )

        db.commit()

    @staticmethod
    def get_adjacent(diary_id):
        """現在の日記の前後の日記を取得"""
        db = get_db()
        entry = db.execute(
            'SELECT id, entry_date, created_at FROM diary_entries WHERE id = ?',
            (diary_id,)
        ).fetchone()
        if not entry:
            return None, None

        # 前の日記（より古い日付方向）
        prev_entry = db.execute(
            '''SELECT id, title, entry_date FROM diary_entries
               WHERE (entry_date < :date)
                  OR (entry_date = :date AND created_at < :created_at)
                  OR (entry_date = :date AND created_at = :created_at AND id < :id)
               ORDER BY entry_date DESC, created_at DESC, id DESC
               LIMIT 1''',
            {'date': entry['entry_date'], 'created_at': entry['created_at'], 'id': entry['id']}
        ).fetchone()

        # 次の日記（より新しい日付方向）
        next_entry = db.execute(
            '''SELECT id, title, entry_date FROM diary_entries
               WHERE (entry_date > :date)
                  OR (entry_date = :date AND created_at > :created_at)
                  OR (entry_date = :date AND created_at = :created_at AND id > :id)
               ORDER BY entry_date ASC, created_at ASC, id ASC
               LIMIT 1''',
            {'date': entry['entry_date'], 'created_at': entry['created_at'], 'id': entry['id']}
        ).fetchone()

        return (dict(prev_entry) if prev_entry else None,
                dict(next_entry) if next_entry else None)

    @staticmethod
    def get_crop_icons_batch(diary_ids):
        """日記IDリストに対して関連作物アイコンを一括取得（effective_crop_idで重複排除）"""
        if not diary_ids:
            return {}
        db = get_db()
        ph = ','.join('?' * len(diary_ids))
        ids = list(diary_ids)
        rows = db.execute(f'''
            SELECT diary_id, effective_crop_id, icon_path, image_color, rel_id
            FROM (
                SELECT dr.diary_id, c.id AS effective_crop_id,
                       c.icon_path, c.image_color, dr.id AS rel_id
                FROM diary_relations dr
                JOIN crops c ON dr.crop_id = c.id
                WHERE dr.diary_id IN ({ph}) AND dr.relation_type = 'crop'
                UNION ALL
                SELECT dr.diary_id, c.id AS effective_crop_id,
                       COALESCE(v.icon_path, c.icon_path) AS icon_path,
                       COALESCE(v.image_color, c.image_color) AS image_color,
                       dr.id AS rel_id
                FROM diary_relations dr
                JOIN varieties v ON dr.variety_id = v.id
                JOIN crops c ON v.crop_id = c.id
                WHERE dr.diary_id IN ({ph}) AND dr.relation_type = 'variety'
                UNION ALL
                SELECT dr.diary_id, cv.effective_crop_id,
                       cv.icon_path, cv.image_color, dr.id AS rel_id
                FROM diary_relations dr
                JOIN plantings lc ON dr.location_crop_id = lc.id
                JOIN crop_variety_view cv
                  ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1)
                  AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
                WHERE dr.diary_id IN ({ph}) AND dr.relation_type = 'location_crop'
                UNION ALL
                SELECT dr.diary_id, cv.effective_crop_id,
                       cv.icon_path, cv.image_color, dr.id AS rel_id
                FROM diary_relations dr
                JOIN harvests h ON dr.harvest_id = h.id
                JOIN plantings lc ON h.location_crop_id = lc.id
                JOIN crop_variety_view cv
                  ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1)
                  AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
                WHERE dr.diary_id IN ({ph}) AND dr.relation_type = 'harvest'
            )
            ORDER BY diary_id, rel_id
        ''', ids * 4).fetchall()

        result = {}
        for row in rows:
            did = row['diary_id']
            ecid = row['effective_crop_id']
            if did not in result:
                result[did] = {'seen': set(), 'icons': []}
            if ecid not in result[did]['seen'] and row['icon_path']:
                result[did]['seen'].add(ecid)
                result[did]['icons'].append({
                    'icon_path': row['icon_path'],
                    'image_color': row['image_color']
                })
        return {did: data['icons'] for did, data in result.items()}

    @staticmethod
    def get_by_crop(crop_id, limit=None):
        """作物に関連する日記を取得"""
        db = get_db()
        # 作物に紐づく日記 = 直接 dr.crop_id 紐づけ
        #                OR 品種経由（dr.variety_id が当作物の品種を指す）
        #                OR 植え付け経由（作物直接 + 品種経由）
        query = '''SELECT DISTINCT de.*
               FROM diary_entries de
               JOIN diary_relations dr ON de.id = dr.diary_id
               WHERE dr.crop_id = ?
                  OR dr.variety_id IN (SELECT id FROM varieties WHERE crop_id = ?)
                  OR dr.location_crop_id IN (
                       SELECT lc.id FROM plantings lc
                       LEFT JOIN varieties v ON v.id = lc.variety_id
                       WHERE lc.crop_id = ? OR v.crop_id = ?
                   )
               ORDER BY de.entry_date DESC'''
        params = [crop_id, crop_id, crop_id, crop_id]
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_by_variety(variety_id, limit=None):
        """品種に関連する日記を取得"""
        db = get_db()
        # 品種に紐づく日記 = dr.variety_id 直接紐づけ OR 植え付け（variety_id一致）経由
        query = '''SELECT DISTINCT de.*
               FROM diary_entries de
               JOIN diary_relations dr ON de.id = dr.diary_id
               WHERE dr.variety_id = ?
                  OR dr.location_crop_id IN (SELECT id FROM plantings WHERE variety_id = ?)
               ORDER BY de.entry_date DESC'''
        params = [variety_id, variety_id]
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_by_location(location_id, limit=None):
        """場所に関連する日記を取得"""
        db = get_db()
        query = '''SELECT DISTINCT de.*
               FROM diary_entries de
               JOIN diary_relations dr ON de.id = dr.diary_id
               WHERE dr.location_id = ? OR dr.location_crop_id IN (
                   SELECT id FROM plantings WHERE location_id = ?
               )
               ORDER BY de.entry_date DESC'''
        params = [location_id, location_id]
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_by_location_crop(location_crop_id, limit=None):
        """植え付けに関連する日記を取得"""
        db = get_db()
        query = '''SELECT DISTINCT de.*
               FROM diary_entries de
               JOIN diary_relations dr ON de.id = dr.diary_id
               WHERE dr.location_crop_id = ?
               ORDER BY de.entry_date DESC'''
        params = [location_crop_id]
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]

    @staticmethod
    def get_by_harvest(harvest_id, limit=None):
        """収穫記録に関連する日記を取得"""
        db = get_db()
        query = '''SELECT DISTINCT de.*
               FROM diary_entries de
               JOIN diary_relations dr ON de.id = dr.diary_id
               WHERE dr.harvest_id = ?
               ORDER BY de.entry_date DESC'''
        params = [harvest_id]
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        entries = db.execute(query, params).fetchall()
        return [dict(entry) for entry in entries]
