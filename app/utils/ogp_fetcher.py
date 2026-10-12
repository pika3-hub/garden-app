import codecs
import ipaddress
import re
import socket
import urllib.request
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)
_TIMEOUT = 5        # 秒
_MAX_BYTES = 524288  # 512KB
_META_CHARSET = re.compile(rb'<meta[^>]+charset\s*=\s*["\']?([A-Za-z0-9_.:-]+)', re.IGNORECASE)


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


def is_public_host(host) -> bool:
    """ホストの解決先がすべてインターネット上のアドレスなら True（LAN・ループバック等や解決失敗は False）"""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    return all(ipaddress.ip_address(info[4][0].split('%')[0]).is_global for info in infos)


class _PublicOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """リダイレクト先が LAN・ループバック等なら追わない"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_public_host(urlparse(newurl).hostname):
            raise urllib.error.URLError(f'リダイレクト先が公開アドレスではありません: {newurl}')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_ogp(url: str, public_only: bool = False) -> dict:
    """OGPメタデータを取得。失敗時は全 None を返す（例外を raise しない）。

    public_only=True ならインターネット上のアドレス以外（リダイレクト先を含む）には接続しない。
    外部 API から使うときに指定する（アプリは Hermes が遮断されている Web 画面にも接続できるため）。
    """
    empty = {'ogp_image': None, 'ogp_title': None, 'ogp_description': None}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': _UA})
        if public_only:
            if not is_public_host(urlparse(url).hostname):
                return empty
            opener = urllib.request.build_opener(_PublicOnlyRedirectHandler)
        else:
            opener = urllib.request.build_opener()
        with opener.open(req, timeout=_TIMEOUT) as resp:
            header_charset = resp.headers.get_content_charset()
            raw = resp.read(_MAX_BYTES)
        return _parse_ogp(raw, header_charset, url)
    except Exception:
        return empty


def _detect_charset(raw: bytes, header_charset) -> str:
    """文字コード: レスポンスヘッダー → HTML の <meta charset> → UTF-8 の順"""
    match = _META_CHARSET.search(raw[:4096])
    for name in (header_charset, match and match.group(1).decode('ascii')):
        if not name:
            continue
        try:
            codec = codecs.lookup(name).name
        except LookupError:
            continue
        # 日本のサイトの Shift_JIS は Windows の拡張文字を含むことが多いので上位互換の cp932 で読む
        return 'cp932' if codec == 'shift_jis' else codec
    return 'utf-8'


def _parse_ogp(raw: bytes, header_charset, url: str) -> dict:
    html = raw.decode(_detect_charset(raw, header_charset), errors='replace')
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
