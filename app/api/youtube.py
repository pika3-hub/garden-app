"""追加 YouTube（補足情報の youtube 型）の検証・保存

保存の前に YouTube の oEmbed で動画があるかを確かめ、動画のタイトルを補足情報のタイトルにする
（エージェントが架空の URL を送っても保存しない）。問い合わせ先は www.youtube.com だけ。
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from app.api.errors import detail
from app.models.supplement import (Supplement, extract_youtube_info, format_youtube_content,
                                   parse_youtube_content, validate_url)

YOUTUBE_KEYS = ('extra_youtube',)
MAX_VIDEOS_PER_REQUEST = 10
MAX_URL_LENGTH = 2000
_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}
_OEMBED = 'https://www.youtube.com/oembed'
_TIMEOUT = 5  # 秒


class VideoNotFound(Exception):
    """動画が無い、非公開、埋め込み不可"""


class YouTubeUnreachable(Exception):
    """YouTube に問い合わせられなかった"""


def watch_url(video_id, start=None):
    url = f'https://www.youtube.com/watch?v={video_id}'
    return f'{url}&t={start}s' if start else url


def fetch_video_title(video_id):
    """oEmbed で動画のタイトルを返す。動画が無ければ VideoNotFound、通信できなければ YouTubeUnreachable"""
    query = urllib.parse.urlencode({'format': 'json', 'url': watch_url(video_id)})
    req = urllib.request.Request(f'{_OEMBED}?{query}')
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read()).get('title')
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500:
            raise VideoNotFound(video_id) from e
        raise YouTubeUnreachable(video_id) from e
    except (OSError, ValueError) as e:
        raise YouTubeUnreachable(video_id) from e


def collect_videos(payload, errors, res):
    """extra_youtube を検証して [(位置, 動画ID, 開始秒)] を返す（リクエスト内の同じ動画は1つにする）"""
    raw = payload.get('extra_youtube')
    if raw is None:
        return []
    if not res.supplement_type:
        errors.append(detail('extra_youtube', f'{res.label}には補足情報（YouTube）を付けられません'))
        return []
    if not isinstance(raw, list):
        errors.append(detail('extra_youtube',
                             'YouTube の URL の配列で指定してください（例: ["https://www.youtube.com/watch?v=..."]）'))
        return []
    if len(raw) > MAX_VIDEOS_PER_REQUEST:
        errors.append(detail('extra_youtube',
                             f'YouTube は1回のリクエストで{MAX_VIDEOS_PER_REQUEST}件までです（{len(raw)}件）'))
        return []
    videos = []
    for i, value in enumerate(raw):
        field_name = f'extra_youtube[{i}]'
        shown = value if isinstance(value, (int, str)) else None
        if not isinstance(value, str):
            errors.append(detail(field_name, 'URL を文字列で指定してください', shown))
            continue
        url = value.strip()
        if len(url) > MAX_URL_LENGTH:
            errors.append(detail(field_name, f'URL は{MAX_URL_LENGTH}文字までです'))
            continue
        video_id, start = (extract_youtube_info(url)
                           if validate_url(url) and urlparse(url).hostname in _HOSTS else (None, None))
        if not video_id:
            errors.append(detail(field_name, 'YouTube の動画の URL を指定してください'
                                             '（https://www.youtube.com/watch?v=… か https://youtu.be/…）', value))
        elif video_id not in {v[1] for v in videos}:
            videos.append((i, video_id, start))
    return videos


def _attached_ids(entity_type, entity_id):
    return {parse_youtube_content(s['content'])[0] for s in Supplement.get_by_entity(entity_type, entity_id)
            if s['supplement_type'] == 'youtube'}


def lookup_videos(videos, res, row, errors):
    """付いていない動画を YouTube に問い合わせ、[(動画ID, 開始秒, タイトル)] を返す。無い動画は errors に積む"""
    attached = _attached_ids(res.supplement_type, row['id']) if row and videos else set()
    found = []
    for i, video_id, start in videos:
        if video_id in attached:
            continue
        try:
            found.append((video_id, start, fetch_video_title(video_id)))
        except VideoNotFound:
            errors.append(detail(f'extra_youtube[{i}]',
                                 'YouTube にこの動画が見つかりません（削除・非公開・埋め込み不可を含む）', watch_url(video_id)))
        except YouTubeUnreachable:
            errors.append(detail(f'extra_youtube[{i}]',
                                 'YouTube に動画を確認できませんでした。時間をおいてやり直してください', watch_url(video_id)))
    return found


def add_extra_youtube(videos, entity_type, entity_id):
    """確認済みの動画を補足情報（youtube 型）として添付する。同じ動画が既にあれば追加しない"""
    if not videos:
        return
    attached = _attached_ids(entity_type, entity_id)
    for video_id, start, title in videos:
        if video_id in attached:
            continue
        Supplement.create({'entity_type': entity_type, 'entity_id': entity_id,
                           'supplement_type': 'youtube', 'title': title,
                           'content': format_youtube_content(video_id, start)})
        attached.add(video_id)
