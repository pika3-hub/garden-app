from datetime import datetime

from app.database import get_db
from app.utils.timezone import get_jst_now


class PlantingRecord:
    """栽培記録モデル"""

    @staticmethod
    def _calculate_days(planted_date, target_date):
        """植え付け日から対象日までの日数を計算"""
        if not planted_date or not target_date:
            return None
        try:
            planted = datetime.strptime(str(planted_date)[:10], '%Y-%m-%d')
            target = datetime.strptime(str(target_date)[:10], '%Y-%m-%d')
            return (target - planted).days
        except (ValueError, TypeError):
            return None

    @staticmethod
    def get_by_location_crop(location_crop_id):
        """特定の栽培に紐づく記録一覧を取得"""
        db = get_db()
        records = db.execute(
            '''SELECT gr.*, c.name as crop_name, c.variety, l.name as location_name,
                      lc.location_id, lc.crop_id, lc.planted_date
               FROM planting_records gr
               JOIN plantings lc ON gr.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE gr.location_crop_id = ?
               ORDER BY gr.recorded_at DESC, gr.created_at DESC''',
            (location_crop_id,)
        ).fetchall()
        result = []
        for r in records:
            record_dict = dict(r)
            record_dict['days_from_planting'] = PlantingRecord._calculate_days(
                record_dict.get('planted_date'), record_dict.get('recorded_at')
            )
            result.append(record_dict)
        return result

    @staticmethod
    def get_recent(limit=5):
        """最新の栽培記録を取得"""
        db = get_db()
        records = db.execute(
            '''SELECT gr.*, c.name as crop_name, c.variety, l.name as location_name,
                      lc.location_id, lc.crop_id, lc.planted_date
               FROM planting_records gr
               JOIN plantings lc ON gr.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               ORDER BY gr.recorded_at DESC, gr.created_at DESC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(r) for r in records]

    @staticmethod
    def get_by_id(record_id):
        """IDで栽培記録を取得"""
        db = get_db()
        record = db.execute(
            '''SELECT gr.*, c.name as crop_name, c.variety, l.name as location_name,
                      lc.location_id, lc.crop_id, lc.planted_date
               FROM planting_records gr
               JOIN plantings lc ON gr.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE gr.id = ?''',
            (record_id,)
        ).fetchone()
        if record:
            record_dict = dict(record)
            record_dict['days_from_planting'] = PlantingRecord._calculate_days(
                record_dict.get('planted_date'), record_dict.get('recorded_at')
            )
            return record_dict
        return None

    @staticmethod
    def create(data):
        """栽培記録を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO planting_records
               (location_crop_id, recorded_at, notes, image_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (data['location_crop_id'], data['recorded_at'],
             data.get('notes'), data.get('image_path'),
             now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(record_id, data):
        """栽培記録を更新"""
        db = get_db()
        db.execute(
            '''UPDATE planting_records SET
               recorded_at = ?, notes = ?, image_path = ?, updated_at = ?
               WHERE id = ?''',
            (data['recorded_at'], data.get('notes'), data.get('image_path'),
             get_jst_now(), record_id)
        )
        db.commit()

    @staticmethod
    def delete(record_id):
        """栽培記録を削除"""
        db = get_db()
        db.execute('DELETE FROM planting_records WHERE id = ?', (record_id,))
        db.commit()
