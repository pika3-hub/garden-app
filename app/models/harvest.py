from app.database import get_db
from datetime import datetime
from app.utils.timezone import get_jst_now


class Harvest:
    """収穫記録モデル"""

    @staticmethod
    def get_all(limit=None, offset=None):
        """全収穫記録を取得（ページネーション対応）"""
        db = get_db()
        query = '''
            SELECT h.*, c.name as crop_name, l.name as location_name,
                   lc.planted_date
            FROM harvests h
            JOIN location_crops lc ON h.location_crop_id = lc.id
            JOIN crops c ON lc.crop_id = c.id
            JOIN locations l ON lc.location_id = l.id
            ORDER BY h.harvest_date DESC, h.created_at DESC
        '''
        params = []

        if limit:
            query += ' LIMIT ?'
            params.append(limit)
            if offset:
                query += ' OFFSET ?'
                params.append(offset)

        harvests = db.execute(query, params).fetchall()
        result = []
        for h in harvests:
            harvest_dict = dict(h)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                h['planted_date'], h['harvest_date']
            )
            result.append(harvest_dict)
        return result

    @staticmethod
    def get_by_id(harvest_id):
        """IDで収穫記録を取得"""
        db = get_db()
        harvest = db.execute(
            '''SELECT h.*, c.name as crop_name, l.name as location_name,
                      lc.planted_date, lc.location_id
               FROM harvests h
               JOIN location_crops lc ON h.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE h.id = ?''',
            (harvest_id,)
        ).fetchone()
        if harvest:
            harvest_dict = dict(harvest)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                harvest['planted_date'], harvest['harvest_date']
            )
            return harvest_dict
        return None

    @staticmethod
    def get_by_location_crop(location_crop_id):
        """栽培記録に紐付く収穫一覧を取得"""
        db = get_db()
        harvests = db.execute(
            '''SELECT h.*, lc.planted_date
               FROM harvests h
               JOIN location_crops lc ON h.location_crop_id = lc.id
               WHERE h.location_crop_id = ?
               ORDER BY h.harvest_date DESC''',
            (location_crop_id,)
        ).fetchall()
        result = []
        for h in harvests:
            harvest_dict = dict(h)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                h['planted_date'], h['harvest_date']
            )
            result.append(harvest_dict)
        return result

    @staticmethod
    def get_by_location(location_id):
        """場所の全収穫記録を取得"""
        db = get_db()
        harvests = db.execute(
            '''SELECT h.*, c.name as crop_name, lc.planted_date
               FROM harvests h
               JOIN location_crops lc ON h.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               WHERE lc.location_id = ?
               ORDER BY h.harvest_date DESC''',
            (location_id,)
        ).fetchall()
        result = []
        for h in harvests:
            harvest_dict = dict(h)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                h['planted_date'], h['harvest_date']
            )
            result.append(harvest_dict)
        return result

    @staticmethod
    def get_by_crop(crop_id):
        """作物の全収穫記録を取得"""
        db = get_db()
        harvests = db.execute(
            '''SELECT h.*, l.name as location_name, lc.planted_date
               FROM harvests h
               JOIN location_crops lc ON h.location_crop_id = lc.id
               JOIN locations l ON lc.location_id = l.id
               WHERE lc.crop_id = ?
               ORDER BY h.harvest_date DESC''',
            (crop_id,)
        ).fetchall()
        result = []
        for h in harvests:
            harvest_dict = dict(h)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                h['planted_date'], h['harvest_date']
            )
            result.append(harvest_dict)
        return result

    @staticmethod
    def create(data):
        """収穫記録を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO harvests
               (location_crop_id, harvest_date, quantity, unit, notes, image_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['location_crop_id'], data['harvest_date'],
             data.get('quantity'), data.get('unit'),
             data.get('notes'), data.get('image_path'),
             now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(harvest_id, data):
        """収穫記録を更新"""
        db = get_db()
        db.execute(
            '''UPDATE harvests SET
               harvest_date = ?, quantity = ?, unit = ?,
               notes = ?, image_path = ?, updated_at = ?
               WHERE id = ?''',
            (data['harvest_date'], data.get('quantity'), data.get('unit'),
             data.get('notes'), data.get('image_path'),
             get_jst_now(), harvest_id)
        )
        db.commit()

    @staticmethod
    def delete(harvest_id):
        """収穫記録を削除"""
        db = get_db()
        db.execute('DELETE FROM harvests WHERE id = ?', (harvest_id,))
        db.commit()

    @staticmethod
    def count():
        """収穫記録の総数を取得"""
        db = get_db()
        result = db.execute('SELECT COUNT(*) as count FROM harvests').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def get_recent(limit=5):
        """最新の収穫記録を取得"""
        db = get_db()
        harvests = db.execute(
            '''SELECT h.*, c.name as crop_name, l.name as location_name,
                      lc.planted_date
               FROM harvests h
               JOIN location_crops lc ON h.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               ORDER BY h.harvest_date DESC, h.created_at DESC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        result = []
        for h in harvests:
            harvest_dict = dict(h)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                h['planted_date'], h['harvest_date']
            )
            result.append(harvest_dict)
        return result

    @staticmethod
    def search(keyword=None, date_from=None, date_to=None,
               location_id=None, crop_id=None):
        """収穫記録を検索"""
        db = get_db()
        query = '''
            SELECT h.*, c.name as crop_name, l.name as location_name,
                   lc.planted_date
            FROM harvests h
            JOIN location_crops lc ON h.location_crop_id = lc.id
            JOIN crops c ON lc.crop_id = c.id
            JOIN locations l ON lc.location_id = l.id
            WHERE 1=1
        '''
        params = []

        if keyword:
            query += ' AND (c.name LIKE ? OR l.name LIKE ? OR h.notes LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])

        if date_from:
            query += ' AND h.harvest_date >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND h.harvest_date <= ?'
            params.append(date_to)

        if location_id:
            query += ' AND lc.location_id = ?'
            params.append(location_id)

        if crop_id:
            query += ' AND lc.crop_id = ?'
            params.append(crop_id)

        query += ' ORDER BY h.harvest_date DESC, h.created_at DESC'

        harvests = db.execute(query, params).fetchall()
        result = []
        for h in harvests:
            harvest_dict = dict(h)
            harvest_dict['days_from_planting'] = Harvest._calculate_days(
                h['planted_date'], h['harvest_date']
            )
            result.append(harvest_dict)
        return result

    @staticmethod
    def get_summary_by_location_crop(location_crop_id):
        """栽培記録の収穫サマリーを取得"""
        db = get_db()
        result = db.execute(
            '''SELECT COUNT(*) as harvest_count,
                      SUM(quantity) as total_quantity,
                      MIN(harvest_date) as first_harvest_date,
                      MAX(harvest_date) as last_harvest_date
               FROM harvests
               WHERE location_crop_id = ?''',
            (location_crop_id,)
        ).fetchone()
        return dict(result) if result else None

    @staticmethod
    def _calculate_days(planted_date, harvest_date):
        """植え付け日から収穫日までの日数を計算"""
        if not planted_date or not harvest_date:
            return None
        try:
            if isinstance(planted_date, str):
                planted = datetime.strptime(planted_date, '%Y-%m-%d')
            else:
                planted = planted_date
            if isinstance(harvest_date, str):
                harvested = datetime.strptime(harvest_date, '%Y-%m-%d')
            else:
                harvested = harvest_date
            return (harvested - planted).days
        except (ValueError, TypeError):
            return None
