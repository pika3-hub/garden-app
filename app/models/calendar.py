from app.database import get_db
import calendar
from datetime import date


_CV_JOIN = (
    'JOIN crop_variety_view cv ON '
    'IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1) '
    'AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)'
)


class Calendar:
    """カレンダー用データ取得モデル"""

    @staticmethod
    def _empty_date_bucket():
        return {
            'crops': [], 'locations': [], 'diaries': [],
            'location_crops': [], 'harvests': [], 'tasks': [],
            'growth_records': [], 'varieties': []
        }

    @staticmethod
    def get_month_data(year, month):
        """指定した年月のカレンダーデータを取得"""
        db = get_db()

        _, last_day = calendar.monthrange(year, month)
        start_date = f'{year:04d}-{month:02d}-01'
        end_date = f'{year:04d}-{month:02d}-{last_day:02d}'

        result = {}

        # 作物を取得（created_atの日付部分で取得）
        crops = db.execute(
            '''SELECT id, name, icon_path, image_color,
                      DATE(created_at) as date
               FROM crops
               WHERE DATE(created_at) BETWEEN ? AND ?
               ORDER BY created_at''',
            (start_date, end_date)
        ).fetchall()
        for crop in crops:
            date_str = crop['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            result[date_str]['crops'].append({
                'id': crop['id'],
                'name': crop['name'],
                'variety': None,
                'icon_path': crop['icon_path'],
                'image_color': crop['image_color'],
                'label': crop['name'],
                'url': f"/crops/{crop['id']}"
            })

        # 品種を取得（created_atの日付部分で取得）
        varieties = db.execute(
            '''SELECT v.id, v.name as variety_name,
                      COALESCE(v.icon_path, c.icon_path) as icon_path,
                      COALESCE(v.image_color, c.image_color) as image_color,
                      c.name as crop_name,
                      DATE(v.created_at) as date
               FROM varieties v
               JOIN crops c ON v.crop_id = c.id
               WHERE DATE(v.created_at) BETWEEN ? AND ?
               ORDER BY v.created_at''',
            (start_date, end_date)
        ).fetchall()
        for v in varieties:
            date_str = v['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            label = f"{v['variety_name']}（{v['crop_name']}）"
            result[date_str]['varieties'].append({
                'id': v['id'],
                'variety': v['variety_name'],
                'crop_name': v['crop_name'],
                'icon_path': v['icon_path'],
                'image_color': v['image_color'],
                'label': label,
                'url': f"/varieties/{v['id']}"
            })

        # 場所を取得
        locations = db.execute(
            '''SELECT id, name, DATE(created_at) as date
               FROM locations
               WHERE DATE(created_at) BETWEEN ? AND ?
               ORDER BY created_at''',
            (start_date, end_date)
        ).fetchall()
        for location in locations:
            date_str = location['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            result[date_str]['locations'].append({
                'id': location['id'],
                'name': location['name'],
                'label': f"{location['name']}",
                'url': f"/locations/{location['id']}"
            })

        # 日記を取得
        diaries = db.execute(
            '''SELECT id, title, DATE(entry_date) as date
               FROM diary_entries
               WHERE DATE(entry_date) BETWEEN ? AND ?
               ORDER BY entry_date''',
            (start_date, end_date)
        ).fetchall()
        for diary in diaries:
            date_str = diary['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            result[date_str]['diaries'].append({
                'id': diary['id'],
                'title': diary['title'],
                'label': f"{diary['title']}",
                'url': f"/diary/{diary['id']}"
            })

        # 植え付け（栽培中）を取得
        location_crops = db.execute(
            f'''SELECT lc.id, lc.location_id, DATE(lc.planted_date) as date,
                       cv.crop_name, cv.variety,
                       cv.icon_path, cv.image_color, l.name as location_name
                FROM plantings lc
                {_CV_JOIN}
                JOIN locations l ON lc.location_id = l.id
                WHERE DATE(lc.planted_date) BETWEEN ? AND ?
                ORDER BY lc.planted_date''',
            (start_date, end_date)
        ).fetchall()
        for lc in location_crops:
            date_str = lc['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            crop_label = f"{lc['variety']}（{lc['crop_name']}）" if lc['variety'] else lc['crop_name']
            result[date_str]['location_crops'].append({
                'id': lc['id'],
                'location_id': lc['location_id'],
                'crop_name': lc['crop_name'],
                'variety': lc['variety'],
                'icon_path': lc['icon_path'],
                'image_color': lc['image_color'],
                'location_name': lc['location_name'],
                'label': f"{crop_label}@{lc['location_name']}",
                'url': f"/plantings/{lc['id']}"
            })

        # 収穫を取得
        harvests = db.execute(
            f'''SELECT h.id, h.quantity, h.unit, DATE(h.harvest_date) as date,
                       cv.crop_name, cv.variety,
                       cv.icon_path, cv.image_color
                FROM harvests h
                JOIN plantings lc ON h.location_crop_id = lc.id
                {_CV_JOIN}
                WHERE DATE(h.harvest_date) BETWEEN ? AND ?
                ORDER BY h.harvest_date''',
            (start_date, end_date)
        ).fetchall()
        for harvest in harvests:
            date_str = harvest['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            crop_label = f"{harvest['variety']}（{harvest['crop_name']}）" if harvest['variety'] else harvest['crop_name']
            qty_str = f" {harvest['quantity']}{harvest['unit'] or ''}" if harvest['quantity'] else ''
            result[date_str]['harvests'].append({
                'id': harvest['id'],
                'crop_name': harvest['crop_name'],
                'variety': harvest['variety'],
                'icon_path': harvest['icon_path'],
                'image_color': harvest['image_color'],
                'quantity': harvest['quantity'],
                'unit': harvest['unit'],
                'label': f"{crop_label}{qty_str}",
                'url': f"/harvests/{harvest['id']}"
            })

        # タスクを取得
        tasks = db.execute(
            '''SELECT id, title, status, DATE(due_date) as date
               FROM tasks
               WHERE DATE(due_date) BETWEEN ? AND ?
               ORDER BY due_date''',
            (start_date, end_date)
        ).fetchall()
        for task in tasks:
            date_str = task['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            result[date_str]['tasks'].append({
                'id': task['id'],
                'title': task['title'],
                'status': task['status'],
                'label': f"{task['title']}",
                'url': f"/tasks/{task['id']}"
            })

        # 栽培記録を取得
        growth_records = db.execute(
            f'''SELECT gr.id, gr.location_crop_id, DATE(gr.recorded_at) as date,
                       cv.crop_name, cv.variety,
                       cv.icon_path, cv.image_color, l.name as location_name
                FROM planting_records gr
                JOIN plantings lc ON gr.location_crop_id = lc.id
                {_CV_JOIN}
                JOIN locations l ON lc.location_id = l.id
                WHERE DATE(gr.recorded_at) BETWEEN ? AND ?
                ORDER BY gr.recorded_at''',
            (start_date, end_date)
        ).fetchall()
        for gr in growth_records:
            date_str = gr['date']
            if date_str not in result:
                result[date_str] = Calendar._empty_date_bucket()
            crop_label = f"{gr['variety']}（{gr['crop_name']}）" if gr['variety'] else gr['crop_name']
            result[date_str]['growth_records'].append({
                'id': gr['id'],
                'location_crop_id': gr['location_crop_id'],
                'crop_name': gr['crop_name'],
                'variety': gr['variety'],
                'icon_path': gr['icon_path'],
                'image_color': gr['image_color'],
                'location_name': gr['location_name'],
                'label': f"{crop_label}@{gr['location_name']}",
                'url': f"/plantings/record/{gr['id']}"
            })

        return result

    @staticmethod
    def get_calendar_weeks(year, month):
        """指定した年月のカレンダー週リストを取得（日曜始まり）"""
        cal = calendar.Calendar(firstweekday=6)
        weeks = []
        for week in cal.monthdayscalendar(year, month):
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    week_data.append(date(year, month, day))
            weeks.append(week_data)
        return weeks
