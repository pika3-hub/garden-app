import re
from urllib.parse import urlparse, parse_qs
from app.database import get_db

# YouTube動画ID抽出パターン
_YOUTUBE_PATTERNS = [
    # watch?v=ID
    re.compile(r'(?:youtube\.com/watch\?.*?v=)([a-zA-Z0-9_-]{11})'),
    # youtu.be/ID
    re.compile(r'youtu\.be/([a-zA-Z0-9_-]{11})'),
    # youtube.com/embed/ID
    re.compile(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})'),
    # youtube.com/shorts/ID
    re.compile(r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})'),
]

# タイムスタンプ抽出パターン
_TIME_PATTERN = re.compile(r'[?&](?:t|start)=(\d+)')

VALID_ENTITY_TYPES = {'crop', 'location', 'diary', 'task'}
VALID_SUPPLEMENT_TYPES = {'text', 'image', 'url', 'youtube'}


def extract_youtube_info(input_text):
    """YouTube URL/iframe から動画IDとタイムスタンプを抽出する。

    Returns:
        tuple: (video_id, start_seconds) or (None, None)
    """
    if not input_text:
        return None, None

    text = input_text.strip()
    video_id = None

    for pattern in _YOUTUBE_PATTERNS:
        match = pattern.search(text)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        return None, None

    # タイムスタンプ抽出
    start = None
    time_match = _TIME_PATTERN.search(text)
    if time_match:
        start = int(time_match.group(1))

    return video_id, start


def format_youtube_content(video_id, start_seconds=None):
    """動画IDとタイムスタンプをcontent保存形式に変換する。"""
    if start_seconds:
        return f"{video_id}:{start_seconds}"
    return video_id


def parse_youtube_content(content):
    """content保存形式から動画IDとタイムスタンプを取得する。

    Returns:
        tuple: (video_id, start_seconds_or_None)
    """
    if not content:
        return None, None
    if ':' in content:
        parts = content.split(':', 1)
        return parts[0], int(parts[1])
    return content, None


def validate_url(url):
    """URLがhttp/httpsスキームか検証する。"""
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


class Supplement:

    @staticmethod
    def get_by_entity(entity_type, entity_id):
        db = get_db()
        return db.execute(
            '''SELECT * FROM supplements
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY sort_order, created_at''',
            (entity_type, entity_id)
        ).fetchall()

    @staticmethod
    def get_by_id(supplement_id):
        db = get_db()
        return db.execute(
            'SELECT * FROM supplements WHERE id = ?',
            (supplement_id,)
        ).fetchone()

    @staticmethod
    def create(data):
        db = get_db()
        # sort_order: 既存の最大値 + 1
        max_order = db.execute(
            '''SELECT COALESCE(MAX(sort_order), -1) FROM supplements
               WHERE entity_type = ? AND entity_id = ?''',
            (data['entity_type'], data['entity_id'])
        ).fetchone()[0]

        cursor = db.execute(
            '''INSERT INTO supplements
               (entity_type, entity_id, supplement_type, title, content, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (data['entity_type'], data['entity_id'], data['supplement_type'],
             data.get('title'), data['content'], max_order + 1)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(supplement_id, data):
        db = get_db()
        db.execute(
            '''UPDATE supplements
               SET title = ?, content = ?, updated_at = datetime('now', '+9 hours')
               WHERE id = ?''',
            (data.get('title'), data['content'], supplement_id)
        )
        db.commit()

    @staticmethod
    def delete(supplement_id):
        db = get_db()
        db.execute('DELETE FROM supplements WHERE id = ?', (supplement_id,))
        db.commit()

    @staticmethod
    def delete_by_entity(entity_type, entity_id):
        """エンティティに紐づく全補足を削除し、画像パスのリストを返す。"""
        db = get_db()
        image_rows = db.execute(
            '''SELECT content FROM supplements
               WHERE entity_type = ? AND entity_id = ? AND supplement_type = 'image' ''',
            (entity_type, entity_id)
        ).fetchall()
        image_paths = [row['content'] for row in image_rows if row['content']]

        db.execute(
            'DELETE FROM supplements WHERE entity_type = ? AND entity_id = ?',
            (entity_type, entity_id)
        )
        db.commit()
        return image_paths

    @staticmethod
    def count_by_entity(entity_type, entity_id):
        db = get_db()
        return db.execute(
            '''SELECT COUNT(*) FROM supplements
               WHERE entity_type = ? AND entity_id = ?''',
            (entity_type, entity_id)
        ).fetchone()[0]
