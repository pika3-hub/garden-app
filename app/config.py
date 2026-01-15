import os


class Config:
    """基本設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE = os.path.join(os.getcwd(), 'instance', 'garden.db')

    # アップロード設定
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


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
