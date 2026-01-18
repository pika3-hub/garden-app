import json
from app.database import get_db
from app.utils.timezone import get_jst_now


class Location:
    """場所モデル"""

    @staticmethod
    def get_all():
        """全場所を取得"""
        db = get_db()
        locations = db.execute(
            'SELECT * FROM locations ORDER BY created_at DESC'
        ).fetchall()
        return [dict(location) for location in locations]

    @staticmethod
    def get_by_id(location_id):
        """IDで場所を取得"""
        db = get_db()
        location = db.execute(
            'SELECT * FROM locations WHERE id = ?',
            (location_id,)
        ).fetchone()
        return dict(location) if location else None

    @staticmethod
    def create(data):
        """場所を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO locations (name, location_type, area_size, sun_exposure, notes, image_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['name'], data['location_type'], data.get('area_size'),
             data.get('sun_exposure'), data.get('notes'), data.get('image_path'),
             now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(location_id, data):
        """場所を更新"""
        db = get_db()
        db.execute(
            '''UPDATE locations SET name = ?, location_type = ?, area_size = ?,
               sun_exposure = ?, notes = ?, image_path = ?, updated_at = ?
               WHERE id = ?''',
            (data['name'], data['location_type'], data.get('area_size'),
             data.get('sun_exposure'), data.get('notes'), data.get('image_path'),
             get_jst_now(), location_id)
        )
        db.commit()

    @staticmethod
    def delete(location_id):
        """場所を削除"""
        db = get_db()
        db.execute('DELETE FROM locations WHERE id = ?', (location_id,))
        db.commit()

    @staticmethod
    def count():
        """場所の総数を取得"""
        db = get_db()
        result = db.execute('SELECT COUNT(*) as count FROM locations').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def search(keyword):
        """場所を検索"""
        db = get_db()
        locations = db.execute(
            '''SELECT * FROM locations
               WHERE name LIKE ? OR location_type LIKE ?
               ORDER BY created_at DESC''',
            (f'%{keyword}%', f'%{keyword}%')
        ).fetchall()
        return [dict(location) for location in locations]

    @staticmethod
    def get_canvas_data(location_id):
        """キャンバスデータをJSON形式で取得"""
        db = get_db()
        result = db.execute(
            'SELECT canvas_data FROM locations WHERE id = ?',
            (location_id,)
        ).fetchone()

        if result and result['canvas_data']:
            try:
                return json.loads(result['canvas_data'])
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def save_canvas_data(location_id, canvas_dict):
        """キャンバスデータをJSON形式で保存"""
        from app.models.location_crop import LocationCrop

        db = get_db()
        canvas_json = json.dumps(canvas_dict, ensure_ascii=False)
        db.execute(
            '''UPDATE locations SET canvas_data = ?, updated_at = ?
               WHERE id = ?''',
            (canvas_json, get_jst_now(), location_id)
        )
        db.commit()

        # キャンバス上に存在する作物のIDを抽出
        location_crop_ids = set()
        if canvas_dict and 'objects' in canvas_dict:
            for obj in canvas_dict['objects']:
                if obj.get('locationCropId'):
                    location_crop_ids.add(int(obj['locationCropId']))

        # キャンバス上にない作物の位置情報をクリア
        LocationCrop.clear_positions_except(location_id, location_crop_ids)
