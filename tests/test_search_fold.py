"""検索でひらがな／カタカナ・半角／全角を区別しない（app/utils/search_text.py）"""
import pytest

from app.models.crop import Crop
from app.models.diary import DiaryEntry
from app.models.location import Location
from app.utils.search_text import fold
from tests.api.conftest import api, api_app  # noqa: F401


@pytest.mark.parametrize('text, expected', [
    ('ジャガイモ', 'じゃがいも'),
    ('じゃがいも', 'じゃがいも'),
    ('ｼﾞｬｶﾞｲﾓ', 'じゃがいも'),
    ('白カブ', '白かぶ'),
    ('ミニトマトＡ１', 'みにとまとA1'),
    ('ヴァ', 'ゔぁ'),
    ('ヽヾ', 'ゝゞ'),
    ('ー', 'ー'),
    ('', ''),
    (None, None),
])
def test_fold(text, expected):
    assert fold(text) == expected


def test_sql_function_is_registered(app):
    from app.database import get_db
    with app.app_context():
        assert get_db().execute("SELECT search_fold('ジャガイモ')").fetchone()[0] == 'じゃがいも'
        assert get_db().execute('SELECT search_fold(NULL)').fetchone()[0] is None


def test_model_search_ignores_kana_and_width(app):
    with app.app_context():
        crop_id = Crop.create({'name': 'ジャガイモ', 'crop_type': 'いも'})
        Location.create({'name': '東の畑', 'location_type': 'ﾌﾟﾗﾝﾀｰ'})
        assert [c['id'] for c in Crop.search('じゃがいも')] == [crop_id]
        assert [c['id'] for c in Crop.search('ｲﾓ')] == [crop_id]
        assert [loc['name'] for loc in Location.search('ぷらんたー')] == ['東の畑']
        assert Crop.search('さつまいも') == []


def test_diary_search_ignores_kana(app):
    with app.app_context():
        DiaryEntry.create({'title': '白かぶの間引き', 'content': '', 'entry_date': '2026-10-31'})
        assert [d['title'] for d in DiaryEntry.search(keyword='白カブ')] == ['白かぶの間引き']


def test_api_q_and_lookup_ignore_kana(api):
    api.post('/api/v1/crops', json={'name': 'ジャガイモ', 'crop_type': 'じゃがいも'})
    assert [c['name'] for c in api.get('/api/v1/crops?q=じゃがいも').get_json()['data']] == ['ジャガイモ']
    assert [i['name'] for i in api.get('/api/v1/lookup?q=じゃが').get_json()['data']] == ['ジャガイモ']


@pytest.mark.parametrize('q', ['％', '＿'])
def test_fullwidth_wildcards_stay_literal(api, q):
    """全角の ％ ＿ は NFKC で % _ になるが、検索語をそろえてからエスケープするので文字として扱う"""
    api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'トマト'})
    assert api.get(f'/api/v1/crops?q={q}').get_json()['data'] == []
    assert api.get(f'/api/v1/lookup?q={q}').get_json()['data'] == []


def test_lookup_ranks_exact_match_across_kana(api):
    api.post('/api/v1/crops', json={'name': 'じゃがいも畑の雑草', 'crop_type': 'その他'})
    api.post('/api/v1/crops', json={'name': 'ジャガイモ', 'crop_type': 'じゃがいも'})
    names = [i['name'] for i in api.get('/api/v1/lookup?q=じゃがいも').get_json()['data']]
    assert names == ['ジャガイモ', 'じゃがいも畑の雑草']
