from app.database import get_db
import calendar
from datetime import date


class Calendar:
    """カレンダー用データ取得モデル"""

    @staticmethod
    def get_month_data(year, month):
        """指定した年月のカレンダーデータを取得

        Returns:
            dict: 日付をキーとし、その日のデータを含む辞書
            {
                '2024-01-15': {
                    'crops': [{'id': 1, 'name': 'トマト', 'variety': '桃太郎'}, ...],
                    'locations': [{'id': 1, 'name': '畑A'}, ...],
                    'diaries': [{'id': 1, 'title': '種まき'}, ...],
                    'location_crops': [{'id': 1, 'location_id': 1, 'crop_name': 'トマト', ...}, ...],
                    'harvests': [{'id': 1, 'crop_name': 'トマト', 'quantity': 5, 'unit': '個'}, ...]
                }, ...
            }
        """
        db = get_db()

        # 月の開始日と終了日を取得
        _, last_day = calendar.monthrange(year, month)
        start_date = f'{year:04d}-{month:02d}-01'
        end_date = f'{year:04d}-{month:02d}-{last_day:02d}'

        result = {}

        # 作物を取得 (created_atの日付部分で取得)
        crops = db.execute(
            '''SELECT id, name, variety, DATE(created_at) as date
               FROM crops
               WHERE DATE(created_at) BETWEEN ? AND ?
               ORDER BY created_at''',
            (start_date, end_date)
        ).fetchall()
        for crop in crops:
            date_str = crop['date']
            if date_str not in result:
                result[date_str] = {'crops': [], 'locations': [], 'diaries': [], 'location_crops': [], 'harvests': []}
            result[date_str]['crops'].append({
                'id': crop['id'],
                'name': crop['name'],
                'variety': crop['variety']
            })

        # 場所を取得 (created_atの日付部分で取得)
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
                result[date_str] = {'crops': [], 'locations': [], 'diaries': [], 'location_crops': [], 'harvests': []}
            result[date_str]['locations'].append({
                'id': location['id'],
                'name': location['name']
            })

        # 日記を取得 (entry_dateで取得)
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
                result[date_str] = {'crops': [], 'locations': [], 'diaries': [], 'location_crops': [], 'harvests': []}
            result[date_str]['diaries'].append({
                'id': diary['id'],
                'title': diary['title']
            })

        # 栽培中を取得 (planted_dateで取得)
        location_crops = db.execute(
            '''SELECT lc.id, lc.location_id, DATE(lc.planted_date) as date,
                      c.name as crop_name, c.variety, l.name as location_name
               FROM location_crops lc
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE DATE(lc.planted_date) BETWEEN ? AND ?
               ORDER BY lc.planted_date''',
            (start_date, end_date)
        ).fetchall()
        for lc in location_crops:
            date_str = lc['date']
            if date_str not in result:
                result[date_str] = {'crops': [], 'locations': [], 'diaries': [], 'location_crops': [], 'harvests': []}
            result[date_str]['location_crops'].append({
                'id': lc['id'],
                'location_id': lc['location_id'],
                'crop_name': lc['crop_name'],
                'variety': lc['variety'],
                'location_name': lc['location_name']
            })

        # 収穫を取得 (harvest_dateで取得)
        harvests = db.execute(
            '''SELECT h.id, h.quantity, h.unit, DATE(h.harvest_date) as date,
                      c.name as crop_name, c.variety
               FROM harvests h
               JOIN location_crops lc ON h.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               WHERE DATE(h.harvest_date) BETWEEN ? AND ?
               ORDER BY h.harvest_date''',
            (start_date, end_date)
        ).fetchall()
        for harvest in harvests:
            date_str = harvest['date']
            if date_str not in result:
                result[date_str] = {'crops': [], 'locations': [], 'diaries': [], 'location_crops': [], 'harvests': []}
            result[date_str]['harvests'].append({
                'id': harvest['id'],
                'crop_name': harvest['crop_name'],
                'variety': harvest['variety'],
                'quantity': harvest['quantity'],
                'unit': harvest['unit']
            })

        return result

    @staticmethod
    def get_calendar_weeks(year, month):
        """指定した年月のカレンダー週リストを取得（日曜始まり）

        Returns:
            list: 週ごとの日付リスト（各週は7日分の日付またはNone）
        """
        cal = calendar.Calendar(firstweekday=6)  # 日曜始まり
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
