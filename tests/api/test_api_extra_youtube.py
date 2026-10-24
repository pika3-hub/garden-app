"""extra_youtube（補足情報の YouTube）と、oEmbed による動画の確認"""
import io
import json
import urllib.error

import pytest

from app.api import youtube as api_youtube

TITLES = {'MKEpG7yO5Cw': 'ミニトマト【アイコ】たわわに実らす3つのコツ',
          'tuKLWxz1ez0': 'おすすめ品種の特徴と栽培の注意点'}


@pytest.fixture
def looked_up(monkeypatch):
    """oEmbed の問い合わせを差し替え、問い合わせた動画 ID を記録する（実ネットワークには出ない）"""
    calls = []

    def fake(video_id):
        calls.append(video_id)
        if video_id not in TITLES:
            raise api_youtube.VideoNotFound(video_id)
        return TITLES[video_id]
    monkeypatch.setattr(api_youtube, 'fetch_video_title', fake)
    return calls


def _crop(api, **extra):
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科', **extra})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_with_extra_youtube(api, sql, looked_up):
    data = _crop(api, extra_youtube=['https://www.youtube.com/watch?v=MKEpG7yO5Cw&utm_source=openai',
                                     'https://youtu.be/tuKLWxz1ez0?t=90'])
    assert [(v['url'], v['title']) for v in data['extra_youtube']] == [
        ('https://www.youtube.com/watch?v=MKEpG7yO5Cw', TITLES['MKEpG7yO5Cw']),
        ('https://www.youtube.com/watch?v=tuKLWxz1ez0&t=90s', TITLES['tuKLWxz1ez0'])]
    assert all('supplement_id' in v for v in data['extra_youtube'])
    rows = sql("SELECT * FROM supplements WHERE entity_type = 'crop' ORDER BY sort_order")
    assert [(r['supplement_type'], r['content'], r['title']) for r in rows] == [
        ('youtube', 'MKEpG7yO5Cw', TITLES['MKEpG7yO5Cw']),
        ('youtube', 'tuKLWxz1ez0:90', TITLES['tuKLWxz1ez0'])]


def test_extra_youtube_empty_by_default(api, looked_up):
    assert _crop(api)['extra_youtube'] == []
    assert looked_up == []


def test_patch_skips_videos_already_attached(api, looked_up):
    crop = _crop(api, extra_youtube=['https://www.youtube.com/watch?v=MKEpG7yO5Cw'])
    res = api.patch(f'/api/v1/crops/{crop["id"]}', json={'extra_youtube': [
        'https://youtu.be/MKEpG7yO5Cw',                      # 書き方が違うが同じ動画
        'https://www.youtube.com/shorts/tuKLWxz1ez0',
        'https://m.youtube.com/watch?v=tuKLWxz1ez0']})       # リクエスト内の重複
    assert res.status_code == 200, res.get_json()
    assert [v['url'] for v in res.get_json()['data']['extra_youtube']] == [
        'https://www.youtube.com/watch?v=MKEpG7yO5Cw', 'https://www.youtube.com/watch?v=tuKLWxz1ez0']
    assert looked_up == ['MKEpG7yO5Cw', 'tuKLWxz1ez0']   # 既にある動画は問い合わせない


def test_extra_youtube_and_extra_urls_together(api, monkeypatch, looked_up):
    from app.api import urls as api_urls
    monkeypatch.setattr(api_urls, 'fetch_ogp', lambda url, public_only=False: {
        'ogp_image': None, 'ogp_title': 'ページ', 'ogp_description': None})
    data = _crop(api, extra_urls=['https://example.com/a'],
                 extra_youtube=['https://www.youtube.com/watch?v=MKEpG7yO5Cw'])
    assert [u['url'] for u in data['extra_urls']] == ['https://example.com/a']
    assert [v['title'] for v in data['extra_youtube']] == [TITLES['MKEpG7yO5Cw']]


@pytest.mark.parametrize('value, field', [
    ('https://youtu.be/MKEpG7yO5Cw', 'extra_youtube'),                 # 配列でない
    ([123], 'extra_youtube[0]'),                                      # 文字列でない
    (['https://example.com/watch?v=MKEpG7yO5Cw'], 'extra_youtube[0]'),  # YouTube 以外
    (['https://notyoutube.com/watch?v=MKEpG7yO5Cw'], 'extra_youtube[0]'),
    (['https://www.youtube.com/@tomataro'], 'extra_youtube[0]'),        # 動画ではない
    (['www.youtube.com/watch?v=MKEpG7yO5Cw'], 'extra_youtube[0]'),      # スキームなし
    (['https://youtu.be/MKEpG7yO5Cw'] * 11, 'extra_youtube'),          # 件数超過
])
def test_extra_youtube_validation(api, sql, looked_up, value, field):
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科', 'extra_youtube': value})
    assert res.status_code == 422
    assert field in [d['field'] for d in res.get_json()['error']['details']]
    assert sql('SELECT COUNT(*) AS n FROM crops')[0]['n'] == 0
    assert looked_up == []


def test_missing_video_is_rejected_before_saving(api, sql, looked_up):
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科', 'extra_youtube': [
        'https://youtu.be/MKEpG7yO5Cw', 'https://youtu.be/AAAAAAAAAAA']})
    assert res.status_code == 422
    assert [d['field'] for d in res.get_json()['error']['details']] == ['extra_youtube[1]']
    assert sql('SELECT COUNT(*) AS n FROM crops')[0]['n'] == 0
    assert sql('SELECT COUNT(*) AS n FROM supplements')[0]['n'] == 0


def test_no_lookup_when_other_fields_are_invalid(api, looked_up):
    res = api.post('/api/v1/crops', json={'crop_type': 'ナス科',
                                          'extra_youtube': ['https://youtu.be/MKEpG7yO5Cw']})
    assert res.status_code == 422
    assert looked_up == []


def test_unreachable_youtube_is_rejected(api, sql, monkeypatch):
    def fail(video_id):
        raise api_youtube.YouTubeUnreachable(video_id)
    monkeypatch.setattr(api_youtube, 'fetch_video_title', fail)
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科',
                                          'extra_youtube': ['https://youtu.be/MKEpG7yO5Cw']})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == 'extra_youtube[0]'
    assert sql('SELECT COUNT(*) AS n FROM crops')[0]['n'] == 0


def test_extra_youtube_rejected_without_supplements(api, looked_up):
    loc = api.post('/api/v1/locations', json={'name': '畑', 'location_type': '畑'}).get_json()['data']
    crop = _crop(api)
    planting = api.post('/api/v1/plantings', json={'location_id': loc['id'], 'crop_id': crop['id']})
    res = api.post('/api/v1/planting_records', json={
        'planting_id': planting.get_json()['data']['id'], 'recorded_at': '2026-10-12',
        'extra_youtube': ['https://youtu.be/MKEpG7yO5Cw']})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == 'extra_youtube'
    assert looked_up == []


def test_youtube_added_on_web_is_listed(api, sql, looked_up):
    crop = _crop(api)
    sql("INSERT INTO supplements (entity_type, entity_id, supplement_type, title, content) "
        f"VALUES ('crop', {crop['id']}, 'youtube', NULL, 'tuKLWxz1ez0')")
    data = api.get(f'/api/v1/crops/{crop["id"]}').get_json()['data']
    assert data['extra_youtube'][0]['url'] == 'https://www.youtube.com/watch?v=tuKLWxz1ez0'
    assert data['extra_youtube'][0]['title'] is None


# --- fetch_video_title（oEmbed） ---

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_fetch_video_title_asks_youtube_oembed(monkeypatch):
    requested = []

    def fake_urlopen(req, timeout):
        requested.append(req.full_url)
        return _Resp(json.dumps({'title': 'アイコの育て方'}).encode())
    monkeypatch.setattr(api_youtube.urllib.request, 'urlopen', fake_urlopen)
    assert api_youtube.fetch_video_title('MKEpG7yO5Cw') == 'アイコの育て方'
    assert requested == ['https://www.youtube.com/oembed?format=json&url='
                         'https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DMKEpG7yO5Cw']


@pytest.mark.parametrize('code', [400, 401, 403, 404])
def test_fetch_video_title_not_found(monkeypatch, code):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, code, 'x', {}, None)
    monkeypatch.setattr(api_youtube.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(api_youtube.VideoNotFound):
        api_youtube.fetch_video_title('MKEpG7yO5Cw')


@pytest.mark.parametrize('error', [urllib.error.URLError('down'), TimeoutError(),
                                   urllib.error.HTTPError('u', 500, 'x', {}, None)])
def test_fetch_video_title_unreachable(monkeypatch, error):
    def fake_urlopen(req, timeout):
        raise error
    monkeypatch.setattr(api_youtube.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(api_youtube.YouTubeUnreachable):
        api_youtube.fetch_video_title('MKEpG7yO5Cw')
