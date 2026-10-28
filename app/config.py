import os


def _env_flag(name, default):
    """'0' / 'false' / 'no' / 'off'（大文字小文字を問わない）と空文字は False、それ以外は True"""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ('', '0', 'false', 'no', 'off')


# 公開リポジトリに書いてある開発用の値。テスト以外では create_app がランダム値に差し替える
DEV_SECRET_KEY = 'dev-secret-key-change-in-production'


class Config:
    """基本設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or DEV_SECRET_KEY
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

    # 持ち主のログイン（パスキー）。RP ID はホスト名、ORIGIN はパスキーを使う画面の入口
    PASSKEY_RP_ID = os.environ.get('PASSKEY_RP_ID') or 'localhost'
    PASSKEY_ORIGIN = os.environ.get('PASSKEY_ORIGIN') or 'http://localhost:5000'
    # 編集するときに開く入口（HTTP の入口の画面から「ログイン」で案内する先）
    OWNER_BASE_URL = os.environ.get('OWNER_BASE_URL') or PASSKEY_ORIGIN
    SESSION_COOKIE_SECURE = False


class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # ログインのクッキーは HTTPS の入口だけで送る（.env の SESSION_COOKIE_SECURE=0 で外せる）
    SESSION_COOKIE_SECURE = _env_flag('SESSION_COOKIE_SECURE', True)


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
