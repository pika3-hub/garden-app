from flask import Flask, render_template
from app.config import config
from app.database import init_db


def create_app(config_name='default'):
    """Flaskアプリケーションファクトリ"""
    app = Flask(__name__, instance_relative_config=True)

    # 設定読み込み
    app.config.from_object(config[config_name])

    # データベース初期化
    init_db(app)

    # ブループリント登録
    from app.routes import crop_routes, location_routes, diary_routes, harvest_routes, calendar_routes
    app.register_blueprint(crop_routes.bp)
    app.register_blueprint(location_routes.bp)
    app.register_blueprint(diary_routes.bp)
    app.register_blueprint(harvest_routes.bp)
    app.register_blueprint(calendar_routes.bp)

    # ホームページルート
    @app.route('/')
    def index():
        from app.models.crop import Crop
        from app.models.location import Location
        from app.models.location_crop import LocationCrop
        from app.models.diary import DiaryEntry
        from app.models.harvest import Harvest

        # 統計情報を取得
        stats = {
            'crop_count': Crop.count(),
            'location_count': Location.count(),
            'active_crop_count': LocationCrop.count_active(),
            'diary_count': DiaryEntry.count(),
            'harvest_count': Harvest.count()
        }

        # 最新データを取得
        recent_diaries = DiaryEntry.get_recent(5)
        recent_plantings = LocationCrop.get_recent(5)
        recent_harvests = Harvest.get_recent(5)

        return render_template('index.html',
                             stats=stats,
                             recent_diaries=recent_diaries,
                             recent_plantings=recent_plantings,
                             recent_harvests=recent_harvests)

    return app
