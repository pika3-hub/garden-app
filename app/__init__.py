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
    from app.routes import crop_routes, location_routes, diary_routes
    app.register_blueprint(crop_routes.bp)
    app.register_blueprint(location_routes.bp)
    app.register_blueprint(diary_routes.bp)

    # ホームページルート
    @app.route('/')
    def index():
        from app.models.crop import Crop
        from app.models.location import Location
        from app.models.location_crop import LocationCrop
        from app.models.diary import DiaryEntry

        # 統計情報を取得
        stats = {
            'crop_count': Crop.count(),
            'location_count': Location.count(),
            'active_crop_count': LocationCrop.count_active(),
            'diary_count': DiaryEntry.count()
        }

        # 最近登録した作物と場所を取得
        recent_crops = Crop.get_all()[:5]  # 最新5件
        recent_locations = Location.get_all()[:5]  # 最新5件
        recent_diaries = DiaryEntry.get_recent(5)  # 最新5件

        return render_template('index.html',
                             stats=stats,
                             recent_crops=recent_crops,
                             recent_locations=recent_locations,
                             recent_diaries=recent_diaries)

    return app
