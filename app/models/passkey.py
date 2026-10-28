import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from app.database import get_db
from app.models.app_settings import AppSettings
from app.utils.timezone import JST, get_jst_now

_TOKEN_HASH_KEY = 'passkey_registration_token_hash'
_TOKEN_EXPIRES_KEY = 'passkey_registration_token_expires'


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class Passkey:
    """パスキー（WebAuthn 資格情報）モデル（passkeys テーブル）

    credential_id / public_key は base64url 文字列。
    登録用のワンタイムトークン（スマホなど別の端末にパスキーを足すとき用）は
    app_settings に SHA-256 のハッシュと期限だけを保存する。
    """

    @staticmethod
    def create(credential_id, public_key, sign_count, name):
        """パスキーを登録して ID を返す（credential_id 重複は IntegrityError）"""
        db = get_db()
        cursor = db.execute(
            '''INSERT INTO passkeys (credential_id, public_key, sign_count, name, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            (credential_id, public_key, sign_count, name, get_jst_now())
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def get_by_id(passkey_id):
        row = get_db().execute(
            'SELECT * FROM passkeys WHERE id = ?', (passkey_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_credential_id(credential_id):
        row = get_db().execute(
            'SELECT * FROM passkeys WHERE credential_id = ?', (credential_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_all():
        """登録の古い順"""
        rows = get_db().execute('SELECT * FROM passkeys ORDER BY id').fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def count():
        return get_db().execute('SELECT COUNT(*) AS n FROM passkeys').fetchone()['n']

    @staticmethod
    def record_use(passkey_id, sign_count):
        """ログインに使ったときの署名カウンタと最終使用日時を更新"""
        db = get_db()
        db.execute(
            'UPDATE passkeys SET sign_count = ?, last_used_at = ? WHERE id = ?',
            (sign_count, get_jst_now(), passkey_id)
        )
        db.commit()

    @staticmethod
    def rename(passkey_id, name):
        db = get_db()
        db.execute('UPDATE passkeys SET name = ? WHERE id = ?', (name, passkey_id))
        db.commit()

    @staticmethod
    def delete(passkey_id):
        db = get_db()
        db.execute('DELETE FROM passkeys WHERE id = ?', (passkey_id,))
        db.commit()

    @staticmethod
    def issue_registration_token(ttl_minutes=15):
        """登録用トークンを発行（前のトークンは上書きで無効になる）"""
        token = secrets.token_urlsafe(32)
        expires = datetime.now(JST) + timedelta(minutes=ttl_minutes)
        AppSettings.set(_TOKEN_HASH_KEY, _hash_token(token))
        AppSettings.set(_TOKEN_EXPIRES_KEY, expires.isoformat())
        return token

    @staticmethod
    def check_registration_token(token):
        """トークンを消さずに確かめる（期限内でハッシュが一致すれば True）"""
        stored_hash = AppSettings.get(_TOKEN_HASH_KEY)
        expires = AppSettings.get(_TOKEN_EXPIRES_KEY)
        if not token or not stored_hash or not expires:
            return False
        try:
            if datetime.fromisoformat(expires) < datetime.now(JST):
                return False
        except ValueError:
            return False
        return hmac.compare_digest(stored_hash, _hash_token(token))

    @staticmethod
    def consume_registration_token(token):
        """確かめて、有効ならトークンを消す（1回限り）"""
        if not Passkey.check_registration_token(token):
            return False
        db = get_db()
        db.execute(
            'DELETE FROM app_settings WHERE key IN (?, ?)',
            (_TOKEN_HASH_KEY, _TOKEN_EXPIRES_KEY)
        )
        db.commit()
        return True
