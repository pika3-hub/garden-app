"""追加 URL（補足情報の url 型）の検証・保存

OGP は保存時に取得する。API からはインターネット上のアドレスにだけ接続する（fetch_ogp の public_only）。
"""
from app.api.errors import detail
from app.models.supplement import Supplement, validate_url
from app.utils.ogp_fetcher import fetch_ogp

URL_KEYS = ('extra_urls',)
MAX_URLS_PER_REQUEST = 10
MAX_URL_LENGTH = 2000


def collect_urls(payload, errors, res):
    """extra_urls を検証して URL のリストを返す（前後の空白を除き、リクエスト内の重複は1つにする）"""
    raw = payload.get('extra_urls')
    if raw is None:
        return []
    if not res.supplement_type:
        errors.append(detail('extra_urls', f'{res.label}には補足情報（URL）を付けられません'))
        return []
    if not isinstance(raw, list):
        errors.append(detail('extra_urls', 'URL の配列で指定してください（例: ["https://example.com/a"]）'))
        return []
    if len(raw) > MAX_URLS_PER_REQUEST:
        errors.append(detail('extra_urls', f'URL は1回のリクエストで{MAX_URLS_PER_REQUEST}件までです（{len(raw)}件）'))
        return []
    urls = []
    for i, value in enumerate(raw):
        field_name = f'extra_urls[{i}]'
        shown = value if isinstance(value, (int, str)) else None
        if not isinstance(value, str):
            errors.append(detail(field_name, 'URL を文字列で指定してください', shown))
            continue
        url = value.strip()
        if len(url) > MAX_URL_LENGTH:
            errors.append(detail(field_name, f'URL は{MAX_URL_LENGTH}文字までです'))
        elif not validate_url(url):
            errors.append(detail(field_name, 'http:// か https:// で始まる URL を指定してください', value))
        elif url not in urls:
            urls.append(url)
    return urls


def add_extra_urls(urls, entity_type, entity_id):
    """URL を補足情報（url 型）として添付する。同じ URL が既にあれば追加しない"""
    if not urls:
        return
    existing = {s['content'] for s in Supplement.get_by_entity(entity_type, entity_id)
                if s['supplement_type'] == 'url'}
    for url in urls:
        if url in existing:
            continue
        Supplement.create({'entity_type': entity_type, 'entity_id': entity_id,
                           'supplement_type': 'url', 'title': None, 'content': url,
                           **fetch_ogp(url, public_only=True)})
        existing.add(url)
