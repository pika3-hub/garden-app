import secrets

from app.database import get_db
from app.utils.timezone import get_jst_now

ENTITY_TYPES = ('planting', 'crop', 'variety')


def new_session_id(entity_type, entity_id):
    """Hermes のセッション ID を作る（対象なしは garden-free-...）"""
    suffix = secrets.token_hex(8)
    if entity_type is None:
        return f'garden-free-{suffix}'
    return f'garden-{entity_type}-{entity_id}-{suffix}'


class HermesChat:
    """Hermes に聞くパネルの会話モデル（hermes_chats テーブル）

    対象（植え付け・作物・品種、または対象なし）ごとに Hermes のセッション ID を持つ。
    対象なしは entity_type / entity_id が NULL なので、比較は `IS ?` で行う。
    """

    @staticmethod
    def get_active(entity_type, entity_id):
        row = get_db().execute(
            '''SELECT * FROM hermes_chats
               WHERE entity_type IS ? AND entity_id IS ? AND active = 1
               ORDER BY id DESC LIMIT 1''',
            (entity_type, entity_id)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _create(entity_type, entity_id):
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO hermes_chats
               (entity_type, entity_id, session_id, active, created_at, last_used_at)
               VALUES (?, ?, ?, 1, ?, ?)''',
            (entity_type, entity_id, new_session_id(entity_type, entity_id), now, now)
        )
        row = db.execute(
            'SELECT * FROM hermes_chats WHERE id = ?', (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    @staticmethod
    def get_or_create_active(entity_type, entity_id):
        """active な会話を返す（無ければ作る）"""
        row = HermesChat.get_active(entity_type, entity_id)
        if row:
            return row
        row = HermesChat._create(entity_type, entity_id)
        get_db().commit()
        return row

    @staticmethod
    def start_new(entity_type, entity_id):
        """今の active を 0 にして新しい会話を作る（古い行は残す）"""
        db = get_db()
        db.execute(
            '''UPDATE hermes_chats SET active = 0
               WHERE entity_type IS ? AND entity_id IS ? AND active = 1''',
            (entity_type, entity_id)
        )
        row = HermesChat._create(entity_type, entity_id)
        db.commit()
        return row

    @staticmethod
    def set_last_run(session_id, run_id):
        """最後の run ID を記録し、最終使用日時を更新"""
        db = get_db()
        db.execute(
            'UPDATE hermes_chats SET last_run_id = ?, last_used_at = ? WHERE session_id = ?',
            (run_id, get_jst_now(), session_id)
        )
        db.commit()

    @staticmethod
    def find_by_run_id(run_id):
        """last_run_id が一致する行（active かどうかを問わない）。無ければ None"""
        if not run_id:
            return None
        row = get_db().execute(
            'SELECT * FROM hermes_chats WHERE last_run_id = ? ORDER BY id DESC LIMIT 1',
            (run_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_session_ids(session_ids):
        """session_id -> 行 の辞書"""
        if not session_ids:
            return {}
        placeholders = ','.join('?' * len(session_ids))
        rows = get_db().execute(
            f'SELECT * FROM hermes_chats WHERE session_id IN ({placeholders})',
            list(session_ids)
        ).fetchall()
        return {r['session_id']: dict(r) for r in rows}
