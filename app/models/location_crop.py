from app.database import get_db
from app.utils.timezone import get_jst_now


class LocationCrop:
    """場所-作物関連モデル"""

    @staticmethod
    def get_by_location(location_id, status='active'):
        """場所に紐付く作物を取得"""
        db = get_db()
        query = '''
            SELECT lc.*, c.name as crop_name, c.crop_type, c.variety
            FROM location_crops lc
            JOIN crops c ON lc.crop_id = c.id
            WHERE lc.location_id = ?
        '''
        params = [location_id]

        if status:
            query += ' AND lc.status = ?'
            params.append(status)

        query += ' ORDER BY lc.planted_date DESC'

        location_crops = db.execute(query, params).fetchall()
        return [dict(lc) for lc in location_crops]

    @staticmethod
    def get_by_crop(crop_id, status='active'):
        """作物に紐付く場所を取得"""
        db = get_db()
        query = '''
            SELECT lc.*, l.name as location_name, l.location_type
            FROM location_crops lc
            JOIN locations l ON lc.location_id = l.id
            WHERE lc.crop_id = ?
        '''
        params = [crop_id]

        if status:
            query += ' AND lc.status = ?'
            params.append(status)

        query += ' ORDER BY lc.planted_date DESC'

        location_crops = db.execute(query, params).fetchall()
        return [dict(lc) for lc in location_crops]

    @staticmethod
    def get_by_id(location_crop_id):
        """IDで場所-作物関連を取得"""
        db = get_db()
        location_crop = db.execute(
            '''SELECT lc.*, c.name as crop_name, c.variety, l.name as location_name
               FROM location_crops lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE lc.id = ?''',
            (location_crop_id,)
        ).fetchone()
        return dict(location_crop) if location_crop else None

    @staticmethod
    def plant(data):
        """作物を場所に植え付け"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO location_crops (location_id, crop_id, planted_date, quantity, notes, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?)''',
            (data['location_id'], data['crop_id'], data.get('planted_date'),
             data.get('quantity'), data.get('notes'), now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(location_crop_id, data):
        """場所-作物関連を更新"""
        db = get_db()
        db.execute(
            '''UPDATE location_crops
               SET planted_date = ?, quantity = ?, notes = ?, status = ?,
                   updated_at = ?
               WHERE id = ?''',
            (data.get('planted_date'), data.get('quantity'),
             data.get('notes'), data.get('status', 'active'),
             get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def harvest(location_crop_id):
        """収穫済みに変更"""
        db = get_db()
        db.execute(
            '''UPDATE location_crops SET status = 'harvested', updated_at = ?
               WHERE id = ?''',
            (get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def remove(location_crop_id):
        """削除（取り除く）"""
        db = get_db()
        db.execute(
            '''UPDATE location_crops SET status = 'removed', updated_at = ?
               WHERE id = ?''',
            (get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def delete(location_crop_id):
        """場所-作物関連を削除"""
        db = get_db()
        db.execute('DELETE FROM location_crops WHERE id = ?', (location_crop_id,))
        db.commit()

    @staticmethod
    def count_active():
        """栽培中の作物数を取得"""
        db = get_db()
        result = db.execute(
            '''SELECT COUNT(*) as count
               FROM location_crops lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE lc.status = 'active' '''
        ).fetchone()
        return result['count'] if result else 0

    @staticmethod
    def get_all_active():
        """全ての栽培中の作物を取得（作物・場所情報付き）"""
        db = get_db()
        crops = db.execute(
            '''SELECT lc.*,
                      c.name as crop_name, c.crop_type, c.variety,
                      l.name as location_name, l.location_type
               FROM location_crops lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE lc.status = 'active'
               ORDER BY lc.planted_date DESC'''
        ).fetchall()
        return [dict(crop) for crop in crops]

    @staticmethod
    def update_position(location_crop_id, position_x, position_y):
        """作物の配置位置を更新"""
        db = get_db()
        db.execute(
            '''UPDATE location_crops SET position_x = ?, position_y = ?,
               updated_at = ? WHERE id = ?''',
            (position_x, position_y, get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def clear_positions_except(location_id, location_crop_ids):
        """指定されたID以外の作物の位置情報をクリア"""
        db = get_db()
        now = get_jst_now()
        if location_crop_ids:
            placeholders = ','.join('?' * len(location_crop_ids))
            db.execute(
                f'''UPDATE location_crops SET position_x = NULL, position_y = NULL,
                   updated_at = ?
                   WHERE location_id = ? AND status = 'active' AND id NOT IN ({placeholders})''',
                [now, location_id] + list(location_crop_ids)
            )
        else:
            # リストが空の場合、この場所の全ての作物の位置をクリア
            db.execute(
                '''UPDATE location_crops SET position_x = NULL, position_y = NULL,
                   updated_at = ?
                   WHERE location_id = ? AND status = 'active' ''',
                (now, location_id)
            )
        db.commit()

    @staticmethod
    def get_crops_with_position(location_id):
        """場所の作物を位置情報付きで取得"""
        db = get_db()
        crops = db.execute(
            '''SELECT lc.*, c.name as crop_name, c.crop_type,
               lc.position_x, lc.position_y
               FROM location_crops lc
               JOIN crops c ON lc.crop_id = c.id
               WHERE lc.location_id = ? AND lc.status = 'active'
               ORDER BY lc.planted_date DESC''',
            (location_id,)
        ).fetchall()
        return [dict(crop) for crop in crops]
