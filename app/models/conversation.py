from app.database import get_db
from app.utils.conversation_links import extract_links

KIND_PRIORITY = {'created': 3, 'updated': 2, 'viewed': 1}
KIND_LABELS = {'created': '作った', 'updated': '変えた', 'viewed': '見た'}

# 画面に出す発言（ツールの呼び出し・結果、本文が空のものは出さない）
_VISIBLE = "m.role IN ('user', 'assistant') AND m.content IS NOT NULL AND m.content != ''"

# 一覧の並びの基準になる時刻
_TS = 'COALESCE(last_activity_at, started_at)'

_LIST_SELECT = f'''
    SELECT c.*,
           (SELECT COUNT(*) FROM conversation_messages m
             WHERE m.conversation_id = c.id AND {_VISIBLE}) AS message_count,
           (SELECT COUNT(*) FROM conversation_images i
             WHERE i.conversation_id = c.id) AS image_count,
           EXISTS(SELECT 1 FROM conversation_messages m
                   WHERE m.conversation_id = c.id AND {_VISIBLE}
                     AND m.content LIKE '%[Image attached at:%') AS has_image_marker,
           (SELECT COUNT(*) FROM conversation_links l
             WHERE l.conversation_id = c.id) AS link_count
      FROM conversations c
'''
_ORDER = f'ORDER BY {_TS} DESC, c.id DESC'


def _like_escape(keyword):
    return keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


# ユーザーが変えた題名（hermes_chats.custom_title）があれば Hermes の題名より優先する
_TITLE_SQL = '''COALESCE(
    (SELECT custom_title FROM hermes_chats
      WHERE session_id IN (:hermes_id, :parent_hermes_id) AND custom_title IS NOT NULL
      ORDER BY id DESC LIMIT 1),
    :title)'''


class Conversation:
    """Hermes との会話モデル"""

    @staticmethod
    def is_deleted(hermes_id, parent_hermes_id):
        """アプリから消した会話か（取り込みで復活させないための判定）"""
        row = get_db().execute(
            'SELECT 1 FROM deleted_conversations WHERE hermes_id IN (?, ?) LIMIT 1',
            (hermes_id, parent_hermes_id)
        ).fetchone()
        return row is not None

    @staticmethod
    def upsert(session):
        """hermes_id で探し、あれば更新・無ければ作成する。(id, 作ったか) を返す"""
        db = get_db()
        existing = db.execute(
            'SELECT id FROM conversations WHERE hermes_id = ?', (session['hermes_id'],)
        ).fetchone()
        db.execute(
            f'''INSERT INTO conversations
                   (hermes_id, source, title, started_at, ended_at, last_activity_at,
                    end_reason, parent_hermes_id)
               VALUES (:hermes_id, :source, {_TITLE_SQL}, :started_at, :ended_at, :last_activity_at,
                       :end_reason, :parent_hermes_id)
               ON CONFLICT(hermes_id) DO UPDATE SET
                   source = excluded.source,
                   title = excluded.title,
                   started_at = excluded.started_at,
                   ended_at = excluded.ended_at,
                   last_activity_at = excluded.last_activity_at,
                   end_reason = excluded.end_reason,
                   parent_hermes_id = excluded.parent_hermes_id,
                   updated_at = datetime('now', '+9 hours')''',
            {k: session.get(k) for k in (
                'hermes_id', 'source', 'title', 'started_at', 'ended_at',
                'last_activity_at', 'end_reason', 'parent_hermes_id')}
        )
        db.commit()
        row = db.execute(
            'SELECT id FROM conversations WHERE hermes_id = ?', (session['hermes_id'],)
        ).fetchone()
        return row['id'], existing is None

    @staticmethod
    def upsert_messages(conversation_id, messages):
        """hermes_message_id で上書き・追加する。渡されなかった発言は消さない"""
        db = get_db()
        for m in messages:
            db.execute(
                '''INSERT INTO conversation_messages
                       (conversation_id, hermes_message_id, role, content, tool_calls,
                        tool_call_id, tool_name, display_kind, timestamp)
                   VALUES (:conversation_id, :hermes_message_id, :role, :content, :tool_calls,
                           :tool_call_id, :tool_name, :display_kind, :timestamp)
                   ON CONFLICT(conversation_id, hermes_message_id) DO UPDATE SET
                       role = excluded.role,
                       content = excluded.content,
                       tool_calls = excluded.tool_calls,
                       tool_call_id = excluded.tool_call_id,
                       tool_name = excluded.tool_name,
                       display_kind = excluded.display_kind,
                       timestamp = excluded.timestamp''',
                {
                    'conversation_id': conversation_id,
                    'hermes_message_id': m['hermes_message_id'],
                    'role': m['role'],
                    'content': m.get('content'),
                    'tool_calls': m.get('tool_calls'),
                    'tool_call_id': m.get('tool_call_id'),
                    'tool_name': m.get('tool_name'),
                    'display_kind': m.get('display_kind'),
                    'timestamp': m.get('timestamp'),
                }
            )
        db.commit()

    @staticmethod
    def get_messages(conversation_id, *, include_tools=False):
        """発言を時刻・hermes_message_id の順に取得（既定は user / assistant の本文ありだけ）"""
        db = get_db()
        query = 'SELECT * FROM conversation_messages m WHERE m.conversation_id = ?'
        if not include_tools:
            query += f' AND {_VISIBLE}'
        query += ' ORDER BY m.timestamp, m.hermes_message_id'
        return [dict(r) for r in db.execute(query, (conversation_id,)).fetchall()]

    @staticmethod
    def has_image(conversation_id, file_name):
        row = get_db().execute(
            'SELECT 1 FROM conversation_images WHERE conversation_id = ? AND file_name = ?',
            (conversation_id, file_name)
        ).fetchone()
        return row is not None

    @staticmethod
    def add_image(conversation_id, file_name, image_path):
        db = get_db()
        db.execute(
            '''INSERT INTO conversation_images (conversation_id, file_name, image_path)
               VALUES (?, ?, ?)
               ON CONFLICT(conversation_id, file_name) DO UPDATE SET image_path = excluded.image_path''',
            (conversation_id, file_name, image_path)
        )
        db.commit()

    @staticmethod
    def get_images(conversation_id):
        """{file_name: image_path}"""
        rows = get_db().execute(
            'SELECT file_name, image_path FROM conversation_images WHERE conversation_id = ?',
            (conversation_id,)
        ).fetchall()
        return {r['file_name']: r['image_path'] for r in rows}

    @staticmethod
    def replace_links(conversation_id, links):
        """その会話の結び付けを全部消して入れ直す"""
        db = get_db()
        db.execute('DELETE FROM conversation_links WHERE conversation_id = ?', (conversation_id,))
        for link in links:
            db.execute(
                '''INSERT OR IGNORE INTO conversation_links
                       (conversation_id, entity_type, entity_id, kind, hermes_message_id)
                   VALUES (?, ?, ?, ?, ?)''',
                (conversation_id, link['entity_type'], link['entity_id'], link['kind'],
                 link.get('hermes_message_id'))
            )
        db.commit()

    @staticmethod
    def relink(conversation_id):
        """保存済みの全発言から結び付けを作り直す。件数を返す"""
        links = extract_links(Conversation.get_messages(conversation_id, include_tools=True))
        Conversation.replace_links(conversation_id, links)
        return len(links)

    @staticmethod
    def get_links(conversation_id):
        rows = get_db().execute(
            '''SELECT id, conversation_id, entity_type, entity_id, kind, hermes_message_id
               FROM conversation_links WHERE conversation_id = ? ORDER BY id''',
            (conversation_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_entity(entity_type, entity_id):
        """そのデータに結び付いた会話（新しい順）。複数の区分は優先の高い1つにまとめる"""
        rows = get_db().execute(
            f'''SELECT c.id, c.title, c.last_activity_at, c.started_at, l.kind
                FROM conversation_links l
                JOIN conversations c ON c.id = l.conversation_id
                WHERE l.entity_type = ? AND l.entity_id = ?
                ORDER BY COALESCE(c.last_activity_at, c.started_at) DESC, c.id DESC''',
            (entity_type, entity_id)
        ).fetchall()
        merged = {}
        for r in rows:
            d = dict(r)
            cur = merged.get(d['id'])
            if cur is None:
                merged[d['id']] = d
            elif KIND_PRIORITY[d['kind']] > KIND_PRIORITY[cur['kind']]:
                cur['kind'] = d['kind']
        return list(merged.values())

    @staticmethod
    def get_all():
        rows = get_db().execute(f'{_LIST_SELECT} {_ORDER}').fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def search(keyword):
        """題名と user / assistant の本文の部分一致"""
        rows = get_db().execute(
            f'''{_LIST_SELECT}
                WHERE c.title LIKE :p ESCAPE '\\'
                   OR EXISTS(SELECT 1 FROM conversation_messages m
                              WHERE m.conversation_id = c.id AND {_VISIBLE}
                                AND m.content LIKE :p ESCAPE '\\')
                {_ORDER}''',
            {'p': f'%{_like_escape(keyword)}%'}
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(conversation_id):
        row = get_db().execute(
            'SELECT * FROM conversations WHERE id = ?', (conversation_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_hermes_id(hermes_id):
        row = get_db().execute(
            'SELECT * FROM conversations WHERE hermes_id = ?', (hermes_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_adjacent(conversation_id):
        """一覧の並びで (古い方, 新しい方) を返す"""
        db = get_db()
        cur = db.execute(
            f"SELECT id, IFNULL({_TS}, '') AS ts FROM conversations WHERE id = ?",
            (conversation_id,)
        ).fetchone()
        if not cur:
            return None, None
        params = {'ts': cur['ts'], 'id': cur['id']}
        ts = f"IFNULL({_TS}, '')"
        prev_row = db.execute(
            f'''SELECT id, title, {_TS} AS last_activity_at FROM conversations
                WHERE {ts} < :ts OR ({ts} = :ts AND id < :id)
                ORDER BY {ts} DESC, id DESC LIMIT 1''', params
        ).fetchone()
        next_row = db.execute(
            f'''SELECT id, title, {_TS} AS last_activity_at FROM conversations
                WHERE {ts} > :ts OR ({ts} = :ts AND id > :id)
                ORDER BY {ts} ASC, id ASC LIMIT 1''', params
        ).fetchone()
        return (dict(prev_row) if prev_row else None,
                dict(next_row) if next_row else None)

    @staticmethod
    def all_ids():
        rows = get_db().execute('SELECT id FROM conversations ORDER BY id').fetchall()
        return [r['id'] for r in rows]
