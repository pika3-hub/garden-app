import urllib.request
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin

_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)
_TIMEOUT = 5        # 秒
_MAX_BYTES = 524288  # 512KB


class _OgpParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = {}
        self._done = False

    def handle_starttag(self, tag, attrs):
        if self._done or tag != 'meta':
            return
        d = dict(attrs)
        prop = d.get('property', '')
        if prop in ('og:image', 'og:title', 'og:description') and d.get('content'):
            self.og[prop] = d['content']

    def handle_endtag(self, tag):
        if tag == 'head':
            self._done = True

    def feed(self, data):
        if not self._done:
            super().feed(data)


def fetch_ogp(url: str) -> dict:
    """OGPメタデータを取得。失敗時は全 None を返す（例外を raise しない）。"""
    empty = {'ogp_image': None, 'ogp_title': None, 'ogp_description': None}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            charset = resp.headers.get_content_charset('utf-8')
            raw = resp.read(_MAX_BYTES)
        html = raw.decode(charset, errors='replace')
        parser = _OgpParser()
        parser.feed(html)
        og = parser.og
        image = og.get('og:image')
        if image:
            image = urljoin(url, image)
        return {
            'ogp_image':       image or None,
            'ogp_title':       og.get('og:title') or None,
            'ogp_description': og.get('og:description') or None,
        }
    except Exception:
        return empty
