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
               planting_season, harvest_season, notes, image_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['name'], data['crop_type'], data.get('variety'),
             data.get('characteristics'), data.get('planting_season'),
             data.get('harvest_season'), data.get('notes'), data.get('image_path'),
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
               notes = ?, image_path = ?, updated_at = ?
               WHERE id = ?''',
            (data['name'], data['crop_type'], data.get('variety'),
             data.get('characteristics'), data.get('planting_season'),
             data.get('harvest_season'), data.get('notes'), data.get('image_path'),
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
