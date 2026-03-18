from app.database import get_db
from app.utils.timezone import get_jst_now


class Crop:
    """作物モデル"""

    @staticmethod
    def get_all():
        """全作物を取得"""
        db = get_db()
        crops = db.execute(
            'SELECT * FROM crops ORDER BY created_at DESC'
        ).fetchall()
        return [dict(crop) for crop in crops]

    @staticmethod
    def get_by_id(crop_id):
        """IDで作物を取得"""
        db = get_db()
        crop = db.execute(
            'SELECT * FROM crops WHERE id = ?',
            (crop_id,)
        ).fetchone()
        return dict(crop) if crop else None

    @staticmethod
    def create(data):
        """作物を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO crops (name, crop_type, variety, characteristics,
               planting_season, harvest_season, notes, image_path, icon_path, image_color,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['name'], data['crop_type'], data.get('variety'),
             data.get('characteristics'), data.get('planting_season'),
             data.get('harvest_season'), data.get('notes'), data.get('image_path'),
             data.get('icon_path'), data.get('image_color', '#4CAF50'),
             now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(crop_id, data):
        """作物を更新"""
        db = get_db()
        db.execute(
            '''UPDATE crops SET name = ?, crop_type = ?, variety = ?,
               characteristics = ?, planting_season = ?, harvest_season = ?,
               notes = ?, image_path = ?, icon_path = ?, image_color = ?, updated_at = ?
               WHERE id = ?''',
            (data['name'], data['crop_type'], data.get('variety'),
             data.get('characteristics'), data.get('planting_season'),
             data.get('harvest_season'), data.get('notes'), data.get('image_path'),
             data.get('icon_path'), data.get('image_color', '#4CAF50'),
             get_jst_now(), crop_id)
        )
        db.commit()

    @staticmethod
    def delete(crop_id):
        """作物を削除"""
        db = get_db()
        db.execute('DELETE FROM crops WHERE id = ?', (crop_id,))
        db.commit()

    @staticmethod
    def count():
        """作物の総数を取得"""
        db = get_db()
        result = db.execute('SELECT COUNT(*) as count FROM crops').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def get_adjacent(crop_id):
        """現在の作物の前後の作物を取得（created_at DESC順）"""
        db = get_db()
        current = db.execute(
            'SELECT id, created_at FROM crops WHERE id = ?', (crop_id,)
        ).fetchone()
        if not current:
            return None, None

        params = {'created_at': current['created_at'], 'id': current['id']}

        prev_crop = db.execute(
            '''SELECT id, name, variety FROM crops
               WHERE (created_at < :created_at)
                  OR (created_at = :created_at AND id < :id)
               ORDER BY created_at DESC, id DESC LIMIT 1''',
            params
        ).fetchone()

        next_crop = db.execute(
            '''SELECT id, name, variety FROM crops
               WHERE (created_at > :created_at)
                  OR (created_at = :created_at AND id > :id)
               ORDER BY created_at ASC, id ASC LIMIT 1''',
            params
        ).fetchone()

        return (dict(prev_crop) if prev_crop else None,
                dict(next_crop) if next_crop else None)

    @staticmethod
    def search(keyword):
        """作物を検索"""
        db = get_db()
        crops = db.execute(
            '''SELECT * FROM crops
               WHERE name LIKE ? OR crop_type LIKE ? OR variety LIKE ?
               ORDER BY created_at DESC''',
            (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
        ).fetchall()
        return [dict(crop) for crop in crops]
