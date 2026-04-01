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
    from app.routes import crop_routes, location_routes, diary_routes, harvest_routes, calendar_routes, task_routes, planting_routes
    app.register_blueprint(crop_routes.bp)
    app.register_blueprint(location_routes.bp)
    app.register_blueprint(diary_routes.bp)
    app.register_blueprint(harvest_routes.bp)
    app.register_blueprint(calendar_routes.bp)
    app.register_blueprint(task_routes.bp)
    app.register_blueprint(planting_routes.bp)

    # ホームページルート
    @app.route('/')
    def index():
        from app.models.crop import Crop
        from app.models.location import Location
        from app.models.planting import Planting
        from app.models.diary import DiaryEntry
        from app.models.harvest import Harvest
        from app.models.task import Task
        from app.models.planting_record import PlantingRecord

        # 統計情報を取得
        stats = {
            'crop_count': Crop.count(),
            'location_count': Location.count(),
            'active_crop_count': Planting.count_active(),
            'diary_count': DiaryEntry.count(),
            'harvest_count': Harvest.count(),
            'pending_task_count': Task.count(Task.STATUS_PENDING) + Task.count(Task.STATUS_IN_PROGRESS)
        }

        # 最新データを取得
        recent_diaries = DiaryEntry.get_recent(5)
        recent_plantings = Planting.get_recent(5)
        recent_harvests = Harvest.get_recent(5)
        pending_tasks = Task.get_pending(5)
        recent_growth_records = PlantingRecord.get_recent(5)

        # カルーセル用: 最近の画像を全テーブルから取得
        db = get_db()
        carousel_images_raw = db.execute('''
            SELECT 'crop' AS type, id, image_path, name AS label, CAST(created_at AS TEXT) AS sort_date
            FROM crops WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'location' AS type, id, image_path, name AS label, CAST(created_at AS TEXT) AS sort_date
            FROM locations WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'diary' AS type, id, image_path, title AS label, CAST(entry_date AS TEXT) AS sort_date
            FROM diary_entries WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'harvest' AS type, id, image_path, '' AS label, CAST(harvest_date AS TEXT) AS sort_date
            FROM harvests WHERE image_path IS NOT NULL AND image_path != ''
            UNION ALL
            SELECT 'planting_record' AS type, id, image_path, '' AS label, CAST(recorded_at AS TEXT) AS sort_date
            FROM planting_records WHERE image_path IS NOT NULL AND image_path != ''
            ORDER BY sort_date DESC
            LIMIT 20
        ''').fetchall()

        carousel_images = [dict(row) for row in carousel_images_raw]

        type_config = {
            'crop': ('crops.detail', 'crop_id', 'icon_crop.png', '作物'),
            'location': ('locations.detail', 'location_id', 'icon_location.png', '場所'),
            'diary': ('diary.detail', 'diary_id', 'icon_diary.png', '日記'),
            'harvest': ('harvests.detail', 'harvest_id', 'icon_harvest.png', '収穫'),
            'planting_record': ('plantings.record_detail', 'record_id', 'icon_location_crop.png', '栽培記録'),
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
                             recent_diaries=recent_diaries,
                             recent_plantings=recent_plantings,
                             recent_harvests=recent_harvests,
                             pending_tasks=pending_tasks,
                             recent_growth_records=recent_growth_records,
                             carousel_images=carousel_images,
                             Task=Task)

    return app
