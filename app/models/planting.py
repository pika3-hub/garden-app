import json
from datetime import datetime

from app.database import get_db
from app.utils.timezone import get_jst_now


class Planting:
    """場所-作物関連モデル"""

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
    def get_by_location(location_id, status='active'):
        """場所に紐付く作物を取得"""
        db = get_db()
        query = '''
            SELECT lc.*, c.name as crop_name, c.crop_type, c.variety
            FROM plantings lc
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
            FROM plantings lc
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
               FROM plantings lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE lc.id = ?''',
            (location_crop_id,)
        ).fetchone()
        if location_crop:
            result = dict(location_crop)
            if result.get('status') == 'active':
                today = get_jst_now()[:10]
                result['days_from_planting'] = Planting._calculate_days(
                    result.get('planted_date'), today
                )
            else:
                result['days_from_planting'] = None
            return result
        return None

    @staticmethod
    def plant(data):
        """作物を場所に植え付け"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO plantings (location_id, crop_id, planted_date, quantity, notes, status, created_at, updated_at)
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
            '''UPDATE plantings
               SET planted_date = ?, quantity = ?, notes = ?, status = ?,
                   updated_at = ?
               WHERE id = ?''',
            (data.get('planted_date'), data.get('quantity'),
             data.get('notes'), data.get('status', 'active'),
             get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def harvest(location_crop_id, end_date=None, canvas_snapshot=None):
        """収穫済みに変更"""
        db = get_db()
        db.execute(
            '''UPDATE plantings SET status = 'harvested', end_date = ?,
               canvas_snapshot = ?, updated_at = ? WHERE id = ?''',
            (end_date or get_jst_now()[:10],
             json.dumps(canvas_snapshot, ensure_ascii=False) if canvas_snapshot else None,
             get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def update_end_date_notes(location_crop_id, end_date, notes):
        """harvested 状態の植え付けの終了日・メモを更新"""
        db = get_db()
        db.execute(
            '''UPDATE plantings SET end_date = ?, notes = ?, updated_at = ?
               WHERE id = ?''',
            (end_date or None, notes, get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def remove(location_crop_id):
        """削除（取り除く）"""
        db = get_db()
        db.execute(
            '''UPDATE plantings SET status = 'removed', updated_at = ?
               WHERE id = ?''',
            (get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def delete(location_crop_id):
        """場所-作物関連を削除"""
        db = get_db()
        db.execute('DELETE FROM plantings WHERE id = ?', (location_crop_id,))
        db.commit()

    @staticmethod
    def count_active():
        """栽培中の作物数を取得"""
        db = get_db()
        result = db.execute(
            '''SELECT COUNT(*) as count
               FROM plantings lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE lc.status = 'active' '''
        ).fetchone()
        return result['count'] if result else 0

    @staticmethod
    def get_all_active():
        """全ての栽培中の作物を取得（作物・場所情報付き、栽培記録の件数・最新画像含む）"""
        return Planting.get_all_with_stats(status='active')

    @staticmethod
    def get_all_with_stats(status=None):
        """全ての作物を取得（作物・場所情報付き、栽培記録の件数・最新画像含む）。statusで絞り込み可能"""
        db = get_db()
        query = '''SELECT lc.*,
                      c.name as crop_name, c.crop_type, c.variety,
                      l.name as location_name, l.location_type,
                      COALESCE(gr_stats.record_count, 0) as growth_record_count,
                      gr_img.image_path as latest_growth_image,
                      gr_img.latest_growth_image_date
               FROM plantings lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               LEFT JOIN (
                   SELECT location_crop_id, COUNT(*) as record_count
                   FROM planting_records
                   GROUP BY location_crop_id
               ) gr_stats ON gr_stats.location_crop_id = lc.id
               LEFT JOIN (
                   SELECT gr1.location_crop_id, gr1.image_path, gr1.recorded_at as latest_growth_image_date
                   FROM planting_records gr1
                   INNER JOIN (
                       SELECT location_crop_id, MAX(recorded_at) as max_date
                       FROM planting_records
                       WHERE image_path IS NOT NULL AND image_path != ''
                       GROUP BY location_crop_id
                   ) gr2 ON gr1.location_crop_id = gr2.location_crop_id
                        AND gr1.recorded_at = gr2.max_date
                   WHERE gr1.image_path IS NOT NULL AND gr1.image_path != ''
               ) gr_img ON gr_img.location_crop_id = lc.id'''
        params = []
        if status:
            query += ' WHERE lc.status = ?'
            params.append(status)
        query += ' ORDER BY lc.planted_date DESC'
        crops = db.execute(query, params).fetchall()
        today = get_jst_now()[:10]
        result = []
        for crop in crops:
            crop_dict = dict(crop)
            if crop_dict.get('status') == 'active':
                crop_dict['days_from_planting'] = Planting._calculate_days(
                    crop_dict.get('planted_date'), today
                )
            else:
                crop_dict['days_from_planting'] = None
            result.append(crop_dict)
        return result

    @staticmethod
    def update_position(location_crop_id, position_x, position_y):
        """作物の配置位置を更新"""
        db = get_db()
        db.execute(
            '''UPDATE plantings SET position_x = ?, position_y = ?,
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
                f'''UPDATE plantings SET position_x = NULL, position_y = NULL,
                   updated_at = ?
                   WHERE location_id = ? AND status = 'active' AND id NOT IN ({placeholders})''',
                [now, location_id] + list(location_crop_ids)
            )
        else:
            # リストが空の場合、この場所の全ての作物の位置をクリア
            db.execute(
                '''UPDATE plantings SET position_x = NULL, position_y = NULL,
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
               c.icon_path, c.image_color, c.variety,
               lc.position_x, lc.position_y
               FROM plantings lc
               JOIN crops c ON lc.crop_id = c.id
               WHERE lc.location_id = ? AND lc.status = 'active'
               ORDER BY lc.planted_date DESC''',
            (location_id,)
        ).fetchall()
        return [dict(crop) for crop in crops]

    @staticmethod
    def update_all(location_crop_id, data):
        """植え付けデータを全フィールド更新（location_id, crop_id含む）"""
        db = get_db()
        db.execute(
            '''UPDATE plantings
               SET location_id = ?, crop_id = ?, planted_date = ?,
                   quantity = ?, notes = ?, updated_at = ?
               WHERE id = ?''',
            (data['location_id'], data['crop_id'],
             data.get('planted_date'), data.get('quantity'),
             data.get('notes'), get_jst_now(), location_crop_id)
        )
        db.commit()

    @staticmethod
    def get_earliest_child_date(location_crop_id):
        """この植え付けに紐づく最も古い子レコードの日付を取得"""
        db = get_db()
        record = db.execute(
            '''SELECT MIN(d) as earliest FROM (
                   SELECT MIN(recorded_at) as d FROM planting_records WHERE location_crop_id = ?
                   UNION ALL
                   SELECT MIN(harvest_date) as d FROM harvests WHERE location_crop_id = ?
               )''',
            (location_crop_id, location_crop_id)
        ).fetchone()
        return record['earliest'] if record else None

    @staticmethod
    def get_recent(limit=5):
        """最近植え付けた作物を取得（作物・場所情報付き）"""
        db = get_db()
        crops = db.execute(
            '''SELECT lc.*,
                      c.name as crop_name, c.crop_type, c.variety,
                      l.name as location_name, l.location_type
               FROM plantings lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               ORDER BY lc.planted_date DESC, lc.created_at DESC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(crop) for crop in crops]
