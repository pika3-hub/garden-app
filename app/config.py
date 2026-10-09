import os


class Config:
    """基本設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # 起動ディレクトリに依存しないよう、絶対パスで上書きできる（Ubuntu 移設時の systemd 用）
    DATABASE = os.environ.get('DATABASE') or os.path.join(os.getcwd(), 'instance', 'garden.db')

    # アップロード設定
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 256 * 1024 * 1024  # 256MB（写真プールの一括アップロード対応）
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # 外部API（app/api/）。API_TOKEN が無い・32文字未満なら API アプリは起動しない
    API_TOKEN = os.environ.get('API_TOKEN')
    API_MAX_IMAGE_MB = int(os.environ.get('API_MAX_IMAGE_MB') or 20)
    # レスポンスの web_url / image_url の基準（スマホから開ける Web 画面の URL）
    WEB_BASE_URL = os.environ.get('WEB_BASE_URL') or 'http://localhost:5000'


class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY')


class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    DATABASE = ':memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
