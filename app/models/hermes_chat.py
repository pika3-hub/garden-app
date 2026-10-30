import secrets

from app.database import get_db
from app.utils.timezone import get_jst_now

ENTITY_TYPES = ('planting', 'crop', 'variety')


FREE_TITLE_LENGTH = 30


def make_title(text):
    """最初の質問から会話の題名を作る（改行は空白、30文字を超えたら29文字＋「…」）"""
    text = ' '.join(text.split())
    if len(text) > FREE_TITLE_LENGTH:
        return text[:FREE_TITLE_LENGTH - 1] + '…'
    return text


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
    def touch(session_id):
        """最終使用日時だけを更新する（last_run_id は変えない。終わった古い run が
        後から始めた新しい run を上書きしないように）"""
        db = get_db()
        db.execute(
            'UPDATE hermes_chats SET last_used_at = ? WHERE session_id = ?',
            (get_jst_now(), session_id)
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

    @staticmethod
    def create_free(title):
        """対象なしの新しい会話を作る（active=0＝パネルの active の仕組みには乗せない）"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO hermes_chats
               (entity_type, entity_id, session_id, active, title, created_at, last_used_at)
               VALUES (NULL, NULL, ?, 0, ?, ?, ?)''',
            (new_session_id(None, None), title, now, now)
        )
        db.commit()
        return HermesChat.get_by_id(cursor.lastrowid)

    @staticmethod
    def get_by_id(chat_id):
        row = get_db().execute(
            'SELECT * FROM hermes_chats WHERE id = ?', (chat_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def set_title_if_empty(chat_id, title):
        """題名がまだ無いときだけ（最初の質問から）付ける"""
        db = get_db()
        db.execute(
            'UPDATE hermes_chats SET title = ? WHERE id = ? AND title IS NULL',
            (title, chat_id)
        )
        db.commit()

    @staticmethod
    def list_for_chat():
        """チャット画面の一覧用に全行を返す（display_title 付き、新しく使った順）"""
        rows = get_db().execute(
            '''SELECT h.*, COALESCE(h.custom_title, h.title, c.title) AS display_title
                 FROM hermes_chats h
                 LEFT JOIN conversations c ON c.hermes_id = h.session_id
                ORDER BY h.last_used_at DESC, h.id DESC'''
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def rename(chat_id, title):
        """ユーザーが題名を変える。会話の履歴（本人と子）の題名も揃える。行が無ければ False"""
        db = get_db()
        chat = HermesChat.get_by_id(chat_id)
        if not chat:
            return False
        sid = chat['session_id']
        db.execute('UPDATE hermes_chats SET custom_title = ? WHERE id = ?', (title, chat_id))
        db.execute(
            'UPDATE conversations SET title = ? WHERE hermes_id = ? OR parent_hermes_id = ?',
            (title, sid, sid)
        )
        db.commit()
        return True

    @staticmethod
    def delete(chat_id):
        """会話を消す（履歴・発言・写真・結び付きごと）。消した縮小版の相対パスの一覧を返す。
        取り込みで復活しないよう Hermes の ID を deleted_conversations に覚える。行が無ければ None"""
        db = get_db()
        chat = HermesChat.get_by_id(chat_id)
        if not chat:
            return None
        sid = chat['session_id']
        convs = db.execute(
            'SELECT id, hermes_id FROM conversations WHERE hermes_id = ? OR parent_hermes_id = ?',
            (sid, sid)
        ).fetchall()
        conv_ids = [c['id'] for c in convs]
        paths = []
        try:
            if conv_ids:
                marks = ','.join('?' * len(conv_ids))
                paths = [r['image_path'] for r in db.execute(
                    f'SELECT image_path FROM conversation_images WHERE conversation_id IN ({marks})',
                    conv_ids).fetchall()]
            db.execute('INSERT OR IGNORE INTO deleted_conversations (hermes_id) VALUES (?)', (sid,))
            for c in convs:
                db.execute('INSERT OR IGNORE INTO deleted_conversations (hermes_id) VALUES (?)',
                           (c['hermes_id'],))
            if conv_ids:
                # 外部キー制約は有効にしていない（PRAGMA 無し）ので子の表も明示して消す
                for table in ('conversation_messages', 'conversation_images', 'conversation_links'):
                    db.execute(f'DELETE FROM {table} WHERE conversation_id IN ({marks})', conv_ids)
                db.execute(f'DELETE FROM conversations WHERE id IN ({marks})', conv_ids)
            db.execute('DELETE FROM hermes_chats WHERE id = ?', (chat_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise
        return paths
