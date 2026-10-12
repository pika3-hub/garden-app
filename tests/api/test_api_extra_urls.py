"""extra_urls（補足情報の URL）と、API 用の OGP 取得の制限"""
import urllib.request

import pytest

from app.api import urls as api_urls
from app.utils import ogp_fetcher

OGP = {'ogp_image': 'https://example.com/a.png', 'ogp_title': 'タイトル', 'ogp_description': '説明'}


@pytest.fixture
def fetched(monkeypatch):
    """OGP 取得を差し替え、呼ばれた URL を記録する（実ネットワークには出ない）"""
    calls = []

    def fake(url, public_only=False):
        calls.append((url, public_only))
        return dict(OGP)
    monkeypatch.setattr(api_urls, 'fetch_ogp', fake)
    return calls


def _crop(api, **extra):
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科', **extra})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_with_extra_urls(api, sql, fetched):
    data = _crop(api, extra_urls=['https://example.com/a', 'http://example.com/b'])
    assert [u['url'] for u in data['extra_urls']] == ['https://example.com/a', 'http://example.com/b']
    assert data['extra_urls'][0]['title'] == 'タイトル'
    assert all('supplement_id' in u for u in data['extra_urls'])
    assert fetched == [('https://example.com/a', True), ('http://example.com/b', True)]
    rows = sql("SELECT * FROM supplements WHERE entity_type = 'crop' ORDER BY sort_order")
    assert [r['supplement_type'] for r in rows] == ['url', 'url']
    assert rows[0]['ogp_image'] == OGP['ogp_image']
    assert rows[0]['ogp_description'] == OGP['ogp_description']


def test_extra_urls_empty_by_default(api, fetched):
    assert _crop(api)['extra_urls'] == []
    assert fetched == []


def test_patch_adds_urls_and_skips_duplicates(api, fetched):
    variety_crop = _crop(api)
    res = api.post('/api/v1/varieties', json={'crop_id': variety_crop['id'], 'name': 'アイコ',
                                              'extra_urls': ['https://example.com/a']})
    assert res.status_code == 201, res.get_json()
    vid = res.get_json()['data']['id']
    res = api.patch(f'/api/v1/varieties/{vid}', json={
        'extra_urls': ['https://example.com/a', ' https://example.com/b ', 'https://example.com/b']})
    assert res.status_code == 200, res.get_json()
    assert [u['url'] for u in res.get_json()['data']['extra_urls']] == [
        'https://example.com/a', 'https://example.com/b']
    assert [c[0] for c in fetched] == ['https://example.com/a', 'https://example.com/b']


def test_patch_with_only_extra_urls_keeps_other_fields(api, fetched):
    crop = _crop(api, notes='メモ')
    res = api.patch(f'/api/v1/crops/{crop["id"]}', json={'extra_urls': ['https://example.com/a']})
    assert res.status_code == 200
    assert res.get_json()['data']['notes'] == 'メモ'


@pytest.mark.parametrize('value, field', [
    ('https://example.com/a', 'extra_urls'),              # 配列でない
    (['ftp://example.com/a'], 'extra_urls[0]'),           # http/https 以外
    (['example.com/a'], 'extra_urls[0]'),                 # スキームなし
    ([123], 'extra_urls[0]'),                             # 文字列でない
    (['https://example.com/' + 'a' * 2000], 'extra_urls[0]'),  # 長すぎる
    (['https://example.com/a'] * 11, 'extra_urls'),       # 件数超過
])
def test_extra_urls_validation(api, sql, fetched, value, field):
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科', 'extra_urls': value})
    assert res.status_code == 422
    assert field in [d['field'] for d in res.get_json()['error']['details']]
    assert sql('SELECT COUNT(*) AS n FROM crops')[0]['n'] == 0
    assert fetched == []


def test_extra_urls_rejected_without_supplements(api, sql, fetched):
    loc = api.post('/api/v1/locations', json={'name': '畑', 'location_type': '畑'}).get_json()['data']
    crop = _crop(api)
    planting = api.post('/api/v1/plantings', json={'location_id': loc['id'], 'crop_id': crop['id']})
    res = api.post('/api/v1/planting_records', json={
        'planting_id': planting.get_json()['data']['id'], 'recorded_at': '2026-10-12',
        'extra_urls': ['https://example.com/a']})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == 'extra_urls'


# --- fetch_ogp(public_only=True) ---

@pytest.mark.parametrize('host, expected', [
    ('127.0.0.1', False),
    ('192.168.1.10', False),
    ('10.0.0.1', False),
    ('169.254.1.1', False),
    ('::1', False),
    ('localhost', False),
    ('8.8.8.8', True),
])
def test_is_public_host(host, expected):
    assert ogp_fetcher.is_public_host(host) is expected


def test_fetch_ogp_public_only_skips_private(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('接続してはいけない')
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', boom)
    assert ogp_fetcher.fetch_ogp('http://127.0.0.1:5000/', public_only=True)['ogp_title'] is None


def test_redirect_to_private_is_blocked():
    handler = ogp_fetcher._PublicOnlyRedirectHandler()
    req = urllib.request.Request('https://example.com/')
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(req, None, 302, 'Found', {}, 'http://127.0.0.1:5000/')


@pytest.mark.parametrize('raw, header, expected', [
    ('<meta charset="Shift_JIS"><title>x</title>'.encode('ascii'), None, 'cp932'),
    (b'<meta http-equiv="Content-Type" content="text/html; charset=EUC-JP">', None, 'euc_jp'),
    (b'<meta charset="Shift_JIS">', 'utf-8', 'utf-8'),   # ヘッダーの指定が優先
    (b'<html><head></head>', None, 'utf-8'),            # 指定なしは UTF-8
    (b'<meta charset="no-such-codec">', None, 'utf-8'),  # 知らない文字コードは UTF-8
])
def test_detect_charset(raw, header, expected):
    assert ogp_fetcher._detect_charset(raw, header) == expected


def test_parse_shift_jis_page():
    html = '<html><head><meta charset="Shift_JIS"><meta property="og:title" content="タキイ種苗"></head>'
    raw = html.encode('shift_jis')
    assert ogp_fetcher._parse_ogp(raw, None, 'https://example.com/')['ogp_title'] == 'タキイ種苗'
