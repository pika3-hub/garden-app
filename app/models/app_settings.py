from app.database import get_db
from app.utils.timezone import get_jst_now


class AppSettings:
    """アプリ設定モデル（app_settings テーブル、キーバリュー形式）

    使用キー:
        region: 地域・栽培環境（AIメモ下書きの時期の基準）
    """

    @staticmethod
    def get(key, default=None):
        """設定値を取得（未設定・NULL なら default）"""
        row = get_db().execute(
            'SELECT value FROM app_settings WHERE key = ?', (key,)
        ).fetchone()
        if row is None or row['value'] is None:
            return default
        return row['value']

    @staticmethod
    def set(key, value):
        """設定値を保存（既存キーは上書き）"""
        db = get_db()
        db.execute(
            '''INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value, updated_at = excluded.updated_at''',
            (key, value, get_jst_now())
        )
        db.commit()
