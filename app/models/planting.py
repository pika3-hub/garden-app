import json
from datetime import datetime, timedelta

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
    def _get_canvas_placement_map(location_id):
        """locations.canvas_data から locationCropId → [配置情報] のマップを構築"""
        from app.models.location import Location
        canvas_data = Location.get_canvas_data(location_id)
        placement_map = {}
        if canvas_data and canvas_data.get('version') == '2.0':
            for p in canvas_data.get('placements', []):
                lc_id = p.get('locationCropId')
                if lc_id is not None:
                    placement_map.setdefault(lc_id, []).append(p)
        return placement_map

    @staticmethod
    def _get_snapshot_placements(canvas_snapshot, location_crop_id):
        """canvas_snapshot JSON から該当 locationCropId の配置リストを返す"""
        if not canvas_snapshot:
            return []
        try:
            snap = json.loads(canvas_snapshot)
            if snap.get('version') == '2.0':
                return [p for p in snap.get('placements', [])
                        if p.get('locationCropId') == location_crop_id]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @staticmethod
    def get_historical_change_dates(location_id):
        """見取り図に変化がある日付の一覧を返す（位置情報を持つ植え付けのみ対象）"""
        db = get_db()
        rows = db.execute(
            '''SELECT id, DATE(planted_date) as planted, DATE(end_date) as ended,
                      status, canvas_snapshot
               FROM plantings
               WHERE location_id = ? AND planted_date IS NOT NULL
                 AND NOT (end_date IS NULL AND status = 'harvested')''',
            (location_id,)
        ).fetchall()

        # active 作物用: locations.canvas_data から位置マップを取得
        canvas_map = Planting._get_canvas_placement_map(location_id)

        # 位置情報を持つ（プレビュー再現可能な）植え付けのみ抽出
        renderable = []
        for r in rows:
            if r['status'] == 'active':
                has_pos = r['id'] in canvas_map
            else:
                has_pos = len(Planting._get_snapshot_placements(
                    r['canvas_snapshot'], r['id'])) > 0
            if has_pos:
                renderable.append({'planted': r['planted'], 'ended': r['ended']})

        if not renderable:
            return None

        # 候補日付を収集
        candidate_dates = set()
        for p in renderable:
            candidate_dates.add(p['planted'])
            if p['ended']:
                candidate_dates.add(p['ended'])

        # 各候補日付について、再現可能な植え付けが1つでも表示されるか確認
        valid_dates = []
        for d in sorted(candidate_dates):
            for p in renderable:
                if p['planted'] <= d and (p['ended'] is None or p['ended'] >= d):
                    valid_dates.append(d)
                    break

        if not valid_dates:
            return None

        # 左端: 最初の植え付け日の1日前を追加（何もない状態）
        first_date = valid_dates[0]
        day_before = (datetime.strptime(first_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        valid_dates.insert(0, day_before)

        # 右端: 今日の日付を追加（重複は除く）
        today = get_jst_now()[:10]
        if valid_dates[-1] != today:
            valid_dates.append(today)
        return valid_dates

    @staticmethod
    def get_historical_canvas_data(location_id, target_date):
        """指定日付の見取り図配置データを返す（version 2.0形式）
        - active 作物: locations.canvas_data から位置取得（複数配置対応）
        - harvested 作物: plantings.canvas_snapshot から位置取得
        """
        db = get_db()
        rows = db.execute(
            '''SELECT lc.id as location_crop_id, lc.crop_id, lc.status,
                      lc.canvas_snapshot,
                      c.name as crop_name, c.variety, c.icon_path, c.image_color
               FROM plantings lc
               JOIN crops c ON lc.crop_id = c.id
               WHERE lc.location_id = ? AND lc.planted_date IS NOT NULL
                 AND DATE(lc.planted_date) <= ?
                 AND NOT (lc.end_date IS NULL AND lc.status = 'harvested')
                 AND (lc.end_date IS NULL OR DATE(lc.end_date) >= ?)''',
            (location_id, target_date, target_date)
        ).fetchall()

        # active 作物用: locations.canvas_data から位置マップを取得
        canvas_map = Planting._get_canvas_placement_map(location_id)

        placements = []
        for row in rows:
            r = dict(row)
            lc_id = r['location_crop_id']
            base = {
                'cropId': r['crop_id'],
                'iconPath': r['icon_path'],
                'imageColor': r['image_color'],
                'cropName': r['crop_name'],
                'variety': r['variety']
            }

            if r['status'] == 'active':
                # active: locations.canvas_data から取得（複数配置対応）
                for p in canvas_map.get(lc_id, []):
                    placements.append({
                        **base,
                        'locationCropId': lc_id,
                        'x': p.get('x', 0),
                        'y': p.get('y', 0),
                    })
            else:
                # harvested: canvas_snapshot から取得
                for p in Planting._get_snapshot_placements(
                        r['canvas_snapshot'], lc_id):
                    placements.append({
                        **base,
                        'locationCropId': lc_id,
                        'x': p.get('x', 0),
                        'y': p.get('y', 0),
                    })

        return {'version': '2.0', 'placements': placements}

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
