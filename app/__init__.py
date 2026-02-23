import os
from flask import Flask, render_template
from app.config import config
from app.database import init_db


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


def create_app(config_name='default'):
    """Flaskアプリケーションファクトリ"""
    app = Flask(__name__, instance_relative_config=True)

    # 設定読み込み
    app.config.from_object(config[config_name])

    # データベース初期化
    init_db(app)

    # Jinja2 フィルター登録
    app.jinja_env.filters['thumb_path'] = _thumb_path_filter

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

        return render_template('index.html',
                             stats=stats,
                             recent_diaries=recent_diaries,
                             recent_plantings=recent_plantings,
                             recent_harvests=recent_harvests,
                             pending_tasks=pending_tasks,
                             recent_growth_records=recent_growth_records,
                             Task=Task)

    return app
