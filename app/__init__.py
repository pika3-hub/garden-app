import os
import random
from flask import Flask, render_template, url_for
from app.config import config
from app.database import init_db, get_db


def _thumb_path_filter(image_path):
    """一覧用サムネイルのパスを返す
    例: 'crops/abc.png' → 'crops/thumbs/abc.jpg'
    """
    if not image_path:
        return image_path
    parts = image_path.split('/', 1)
    if len(parts) != 2:
        return image_path
    folder, filename = parts
    basename = os.path.splitext(filename)[0]
    return f"{folder}/thumbs/{basename}.jpg"


def _crop_display_name(name, variety=None):
    """作物名表記ルール: 品種あり→品種名（作物名）、品種なし→作物名"""
    if variety:
        return f"{variety}（{name}）"
    return name


def create_app(config_name='default'):
    """Flaskアプリケーションファクトリ"""
    app = Flask(__name__, instance_relative_config=True)

    # 設定読み込み
    app.config.from_object(config[config_name])

    # データベース初期化
    init_db(app)

    # Jinja2 フィルター登録
    app.jinja_env.filters['thumb_path'] = _thumb_path_filter

    # Jinja2 グローバル関数登録
    app.jinja_env.globals['crop_display_name'] = _crop_display_name

    # ブループリント登録
    from app.routes import (
        crop_routes, variety_routes, location_routes, diary_routes,
        harvest_routes, calendar_routes, task_routes, planting_routes,
        supplement_routes, photo_pool_routes, cooking_routes
    )
    app.register_blueprint(crop_routes.bp)
    app.register_blueprint(variety_routes.bp)
    app.register_blueprint(location_routes.bp)
    app.register_blueprint(diary_routes.bp)
    app.register_blueprint(harvest_routes.bp)
    app.register_blueprint(calendar_routes.bp)
    app.register_blueprint(task_routes.bp)
    app.register_blueprint(planting_routes.bp)
    app.register_blueprint(supplement_routes.bp)
    app.register_blueprint(photo_pool_routes.bp)
    app.register_blueprint(cooking_routes.bp)

    # ホームページルート
    @app.route('/')
    def index():
        from app.models.crop import Crop
        from app.models.variety import Variety
        from app.models.location import Location
        from app.models.planting import Planting
        from app.models.diary import DiaryEntry
        from app.models.harvest import Harvest
        from app.models.task import Task
        from app.models.cooking import Cooking

        # 統計情報を取得
        stats = {
            'crop_count': Crop.count(),
            'variety_count': Variety.count(),
            'location_count': Location.count(),
            'active_crop_count': Planting.count_active(),
            'diary_count': DiaryEntry.count(),
            'harvest_count': Harvest.count(),
            'pending_task_count': Task.count(Task.STATUS_PENDING) + Task.count(Task.STATUS_IN_PROGRESS),
            'cooking_count': Cooking.count(),
        }

        # タイムライン用: 5種別を統合して日付降順に最新20件取得
        import datetime
        from collections import OrderedDict
        db_for_timeline = get_db()

        # 記録のある直近3日分の日付を取得
        top_dates_rows = db_for_timeline.execute('''
            SELECT item_date FROM (
                SELECT entry_date AS item_date FROM diary_entries WHERE entry_date IS NOT NULL
                UNION
                SELECT planted_date FROM plantings WHERE planted_date IS NOT NULL
                UNION
                SELECT recorded_at FROM planting_records WHERE recorded_at IS NOT NULL
                UNION
                SELECT harvest_date FROM harvests WHERE harvest_date IS NOT NULL
                UNION
                SELECT cooked_date FROM cooking WHERE cooked_date IS NOT NULL
            ) sub
            GROUP BY item_date
            ORDER BY item_date DESC
            LIMIT 7
        ''').fetchall()

        timeline_rows = []
        if top_dates_rows:
            top_dates = tuple(str(r[0])[:10] for r in top_dates_rows)
            placeholders = ','.join('?' * len(top_dates))
            timeline_rows = db_for_timeline.execute(f'''
                SELECT * FROM (
                    SELECT 'diary' AS item_type, 5 AS type_order,
                           d.id AS item_id,
                           d.entry_date AS item_date,
                           d.title AS title,
                           NULL AS variety,
                           NULL AS icon_path,
                           NULL AS image_color
                    FROM diary_entries d
                    WHERE d.entry_date IS NOT NULL

                    UNION ALL

                    SELECT 'planting' AS item_type, 1 AS type_order,
                           lc.id AS item_id,
                           lc.planted_date AS item_date,
                           cv.crop_name AS title,
                           cv.variety AS variety,
                           cv.icon_path AS icon_path,
                           cv.image_color AS image_color
                    FROM plantings lc
                    JOIN crop_variety_view cv
                      ON IFNULL(cv.crop_id,-1)=IFNULL(lc.crop_id,-1)
                      AND IFNULL(cv.variety_id,-1)=IFNULL(lc.variety_id,-1)
                    WHERE lc.planted_date IS NOT NULL

                    UNION ALL

                    SELECT 'planting_record' AS item_type, 2 AS type_order,
                           gr.id AS item_id,
                           gr.recorded_at AS item_date,
                           cv.crop_name AS title,
                           cv.variety AS variety,
                           cv.icon_path AS icon_path,
                           cv.image_color AS image_color
                    FROM planting_records gr
                    JOIN plantings lc ON gr.location_crop_id = lc.id
                    JOIN crop_variety_view cv
                      ON IFNULL(cv.crop_id,-1)=IFNULL(lc.crop_id,-1)
                      AND IFNULL(cv.variety_id,-1)=IFNULL(lc.variety_id,-1)
                    WHERE gr.recorded_at IS NOT NULL

                    UNION ALL

                    SELECT 'harvest' AS item_type, 3 AS type_order,
                           h.id AS item_id,
                           h.harvest_date AS item_date,
                           cv.crop_name AS title,
                           cv.variety AS variety,
                           cv.icon_path AS icon_path,
                           cv.image_color AS image_color
                    FROM harvests h
                    JOIN plantings lc ON h.location_crop_id = lc.id
                    JOIN crop_variety_view cv
                      ON IFNULL(cv.crop_id,-1)=IFNULL(lc.crop_id,-1)
                      AND IFNULL(cv.variety_id,-1)=IFNULL(lc.variety_id,-1)
                    WHERE h.harvest_date IS NOT NULL

                    UNION ALL

                    SELECT 'cooking' AS item_type, 4 AS type_order,
                           c.id AS item_id,
                           c.cooked_date AS item_date,
                           c.title AS title,
                           c.category AS variety,
                           NULL AS icon_path,
                           NULL AS image_color
                    FROM cooking c
                    WHERE c.cooked_date IS NOT NULL
                ) WHERE item_date IN ({placeholders})
                ORDER BY item_date DESC, type_order ASC, item_id DESC
            ''', top_dates).fetchall()

        _timeline_type_config = {
            'diary':           ('diary.detail',           'diary_id',          '日記',     '📖'),
            'planting':        ('plantings.detail',       'location_crop_id',  '植え付け', '🌱'),
            'planting_record': ('plantings.record_detail','record_id',         '栽培記録', '📝'),
            'harvest':         ('harvests.detail',        'harvest_id',        '収穫',     '🌾'),
            'cooking':         ('cooking.detail',         'cooking_id',        '料理',     '🍳'),
        }

        timeline_items = []
        for row in timeline_rows:
            item = dict(row)
            endpoint, param, label, icon = _timeline_type_config[item['item_type']]
            item['detail_url'] = url_for(endpoint, **{param: item['item_id']})
            item['type_label'] = label
            item['type_icon'] = icon
            d_str = str(item['item_date'])[:10] if item['item_date'] else None
            if d_str:
                try:
                    dt = datetime.date.fromisoformat(d_str)
                    weekday = ['月', '火', '水', '木', '金', '土', '日'][dt.weekday()]
                    item['item_date_formatted'] = f"{dt.year}年{dt.month}月{dt.day}日（{weekday}）"
                except ValueError:
                    item['item_date_formatted'] = d_str
            else:
                item['item_date_formatted'] = '日付不明'
            timeline_items.append(item)

        from itertools import groupby as _igroup

        timeline_by_date = OrderedDict()
        for item in timeline_items:
            key = str(item['item_date'])[:10] if item['item_date'] else ''
            if key not in timeline_by_date:
                timeline_by_date[key] = {'formatted': item['item_date_formatted'], 'entries': []}
            timeline_by_date[key]['entries'].append(item)

        # デスクトップ用: 同日・同種別をまとめたグループ（entries は type_order 順に並んでいる前提）
        for group in timeline_by_date.values():
            by_type = []
            for _, g in _igroup(group['entries'], key=lambda x: x['item_type']):
                items = list(g)
                by_type.append({
                    'type':    items[0]['item_type'],
                    'label':   items[0]['type_label'],
                    'entries': items,
                })
            group['by_type'] = by_type

        # 直近タスク: due_date が今日から3日以内の未完了タスク（期限切れ含む）
        today_dt = datetime.date.today()
        cutoff_dt = today_dt + datetime.timedelta(days=7)
        upcoming_task_rows = db_for_timeline.execute('''
            SELECT id, title, due_date, status
            FROM tasks
            WHERE status != 'completed'
              AND due_date IS NOT NULL
              AND due_date <= ?
            ORDER BY due_date ASC, id ASC
        ''', (cutoff_dt.isoformat(),)).fetchall()

        def _urgency(due_str):
            try:
                due = datetime.date.fromisoformat(str(due_str)[:10])
            except (ValueError, TypeError):
                return ('?', 9)
            delta = (due - today_dt).days
            if delta < 0:   return ('期限切れ', 0)
            if delta == 0:  return ('今日',     1)
            if delta == 1:  return ('明日',     2)
            return (f'{delta}日後',             3)

        upcoming_tasks = []
        for row in upcoming_task_rows:
            task = dict(row)
            task['urgency_label'], task['urgency_order'] = _urgency(task['due_date'])
            task['detail_url'] = url_for('tasks.detail', task_id=task['id'])
            upcoming_tasks.append(task)

        upcoming_tasks_by_urgency = []
        for _, g in _igroup(upcoming_tasks, key=lambda x: x['urgency_order']):
            grp = list(g)
            upcoming_tasks_by_urgency.append({
                'label':   grp[0]['urgency_label'],
                'order':   grp[0]['urgency_order'],
                'entries': grp,
            })

        # カルーセル用: 最近の画像を全テーブルから取得
        # crops/varieties は独立、harvests/planting_records は VIEW 経由で表示用情報を取得
        db = get_db()
        carousel_images_raw = db.execute('''
            SELECT 'crop' AS type, id, image_path, name AS label, CAST(created_at AS TEXT) AS sort_date,
                   name AS crop_name, NULL AS variety, icon_path, image_color
            FROM crops WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'variety' AS type, v.id, v.image_path,
                   v.name AS label, CAST(v.created_at AS TEXT) AS sort_date,
                   c.name AS crop_name, v.name AS variety,
                   COALESCE(v.icon_path, c.icon_path) AS icon_path,
                   COALESCE(v.image_color, c.image_color) AS image_color
            FROM varieties v JOIN crops c ON v.crop_id = c.id
            WHERE v.image_path IS NOT NULL AND v.image_path != ''
            UNION ALL
            SELECT 'location' AS type, id, image_path, name AS label, CAST(created_at AS TEXT) AS sort_date,
                   NULL, NULL, NULL, NULL
            FROM locations WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'diary' AS type, id, image_path, title AS label, CAST(entry_date AS TEXT) AS sort_date,
                   NULL, NULL, NULL, NULL
            FROM diary_entries WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'harvest' AS type, h.id, h.image_path, '' AS label, CAST(h.harvest_date AS TEXT) AS sort_date,
                   cv.crop_name, cv.variety, cv.icon_path, cv.image_color
            FROM harvests h
            JOIN plantings lc ON h.location_crop_id = lc.id
            JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1)
                                      AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
            WHERE h.image_path IS NOT NULL AND h.image_path != ''
            UNION ALL
            SELECT 'planting_record' AS type, pr.id, pr.image_path, '' AS label, CAST(pr.recorded_at AS TEXT) AS sort_date,
                   cv.crop_name, cv.variety, cv.icon_path, cv.image_color
            FROM planting_records pr
            JOIN plantings lc ON pr.location_crop_id = lc.id
            JOIN crop_variety_view cv ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1)
                                      AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
            WHERE pr.image_path IS NOT NULL AND pr.image_path != ''
            UNION ALL
            SELECT 'cooking' AS type, id, image_path, title AS label, CAST(cooked_date AS TEXT) AS sort_date,
                   NULL, NULL, NULL, NULL
            FROM cooking WHERE image_path IS NOT NULL AND image_path != ''
            ORDER BY sort_date DESC
            LIMIT 20
        ''').fetchall()

        carousel_images = [dict(row) for row in carousel_images_raw]

        type_config = {
            'crop': ('crops.detail', 'crop_id', 'icon_crop.webp', '作物'),
            'variety': ('varieties.detail', 'variety_id', 'icon_variety.webp', '品種'),
            'location': ('locations.detail', 'location_id', 'icon_location.webp', '場所'),
            'diary': ('diary.detail', 'diary_id', 'icon_diary.webp', '日記'),
            'harvest': ('harvests.detail', 'harvest_id', 'icon_harvest.webp', '収穫'),
            'planting_record': ('plantings.record_detail', 'record_id', 'icon_location_crop.webp', '栽培記録'),
            'cooking': ('cooking.detail', 'cooking_id', 'icon_cooking.webp', '料理'),
        }
        for img in carousel_images:
            endpoint, param, icon, type_label = type_config[img['type']]
            img['detail_url'] = url_for(endpoint, **{param: img['id']})
            img['icon'] = icon
            img['type_label'] = type_label

        if carousel_images:
            random.shuffle(carousel_images)

        return render_template('index.html',
                             stats=stats,
                             timeline_by_date=timeline_by_date,
                             upcoming_tasks=upcoming_tasks,
                             upcoming_tasks_by_urgency=upcoming_tasks_by_urgency,
                             carousel_images=carousel_images)

    return app
