import os


class Config:
    """基本設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE = os.path.join(os.getcwd(), 'instance', 'garden.db')


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
