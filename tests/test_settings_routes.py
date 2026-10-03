import pytest

from app.models.app_settings import AppSettings
from app.models.crop import Crop
from app.utils.ai_notes import AiNotesError


def test_settings_page_shows_unconfigured_state(client):
    res = client.get('/settings/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert '地域・栽培環境' in html
    assert '未設定' in html
    assert 'ANTHROPIC_API_KEY' in html
    assert 'Claude Opus 5.5' in html


def test_settings_page_shows_configured_key_without_revealing_it(client, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-secret-value')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-sonnet-5-5')
    html = client.get('/settings/').get_data(as_text=True)
    assert 'APIキー設定済み' in html
    assert 'sk-ant-secret-value' not in html
    assert 'Claude Sonnet 5.5' in html


def test_save_region(client, app):
    res = client.post('/settings/', data={'region': '  神奈川県（温暖地）  '})
    assert res.status_code == 302
    with app.app_context():
        assert AppSettings.get('region') == '神奈川県（温暖地）'
    html = client.get('/settings/').get_data(as_text=True)
    assert '設定を保存しました' in html
    assert '神奈川県（温暖地）' in html


def test_region_too_long_is_rejected(client, app):
    res = client.post('/settings/', data={'region': 'あ' * 501})
    assert res.status_code == 400
    assert '500文字以内' in res.get_data(as_text=True)
    with app.app_context():
        assert AppSettings.get('region') is None


def test_navbar_has_settings_link(client):
    html = client.get('/settings/').get_data(as_text=True)
    assert 'href="/settings/"' in html


# --- 下書き生成 API ---

URL = '/settings/ai/notes-draft'


@pytest.fixture
def ready(app, monkeypatch):
    """地域とAPIキーが設定済みの状態にし、generate_notes の呼び出しを記録する"""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    with app.app_context():
        AppSettings.set('region', '神奈川県（温暖地）')
    calls = []

    def fake_generate(crop_name, crop_type, variety_name, region, use_web_search):
        calls.append(dict(crop_name=crop_name, crop_type=crop_type, variety_name=variety_name,
                          region=region, use_web_search=use_web_search))
        return '## 植え付け時期\n4月'

    monkeypatch.setattr('app.routes.settings_routes.generate_notes', fake_generate)
    return calls


def _make_crop(app, name='トマト', crop_type='トマト'):
    with app.app_context():
        return Crop.create({'name': name, 'crop_type': crop_type})


def test_crop_mode_success(client, ready):
    res = client.post(URL, json={'mode': 'crop', 'crop_name': ' ミニトマト ',
                                 'crop_type': 'トマト', 'use_web_search': False})
    assert res.status_code == 200
    assert res.get_json() == {'ok': True, 'markdown': '## 植え付け時期\n4月'}
    assert ready == [dict(crop_name='ミニトマト', crop_type='トマト', variety_name=None,
                          region='神奈川県（温暖地）', use_web_search=False)]


def test_variety_mode_looks_up_parent_crop(client, app, ready):
    crop_id = _make_crop(app, name='ミニトマト', crop_type='トマト')
    res = client.post(URL, json={'mode': 'variety', 'crop_id': str(crop_id),
                                 'variety_name': 'アイコ', 'use_web_search': True})
    assert res.status_code == 200
    assert ready[0] == dict(crop_name='ミニトマト', crop_type='トマト', variety_name='アイコ',
                            region='神奈川県（温暖地）', use_web_search=True)


@pytest.mark.parametrize('payload, fragment', [
    ({'mode': 'crop', 'crop_name': '   '}, '作物名を入力'),
    ({'mode': 'crop'}, '作物名を入力'),
    ({'mode': 'variety', 'crop_id': 99999, 'variety_name': 'アイコ'}, '親作物が見つかりません'),
    ({'mode': 'variety', 'crop_id': 'abc', 'variety_name': 'アイコ'}, '親作物が見つかりません'),
    ({'mode': 'variety', 'variety_name': 'アイコ'}, '親作物が見つかりません'),
    ({'mode': 'unknown', 'crop_name': 'トマト'}, '不正なリクエスト'),
])
def test_invalid_input_returns_400(client, ready, payload, fragment):
    res = client.post(URL, json=payload)
    assert res.status_code == 400
    body = res.get_json()
    assert body['ok'] is False and fragment in body['error']
    assert ready == []


def test_variety_mode_requires_variety_name(client, app, ready):
    crop_id = _make_crop(app)
    res = client.post(URL, json={'mode': 'variety', 'crop_id': crop_id, 'variety_name': ' '})
    assert res.status_code == 400
    assert '品種名を入力' in res.get_json()['error']


def test_non_json_body_returns_400(client, ready):
    res = client.post(URL, data='not json', content_type='text/plain')
    assert res.status_code == 400


def test_missing_region_returns_need_settings(client, app, ready):
    with app.app_context():
        AppSettings.set('region', '')
    res = client.post(URL, json={'mode': 'crop', 'crop_name': 'トマト'})
    assert res.status_code == 400
    body = res.get_json()
    assert body['need_settings'] is True
    assert '地域' in body['error']


def test_missing_api_key_returns_400(client, ready, monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    res = client.post(URL, json={'mode': 'crop', 'crop_name': 'トマト'})
    assert res.status_code == 400
    assert 'ANTHROPIC_API_KEY' in res.get_json()['error']


def test_generation_error_returns_502(client, ready, monkeypatch):
    def failing(*args, **kwargs):
        raise AiNotesError('混み合っています。しばらく待ってから再度お試しください')
    monkeypatch.setattr('app.routes.settings_routes.generate_notes', failing)
    res = client.post(URL, json={'mode': 'crop', 'crop_name': 'トマト'})
    assert res.status_code == 502
    assert res.get_json() == {'ok': False,
                              'error': '混み合っています。しばらく待ってから再度お試しください'}


# --- フォームへの組み込み ---

def test_crop_form_has_ai_button_disabled_without_key(client):
    html = client.get('/crops/new').get_data(as_text=True)
    assert 'id="aiNotesBtn"' in html
    assert 'id="aiNotesModal"' in html
    assert 'data-mode="crop"' in html
    assert 'APIキーが未設定' in html
    assert 'js/ai-notes.js' in html


def test_variety_form_has_ai_button_enabled_with_key(client, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    html = client.get('/varieties/new').get_data(as_text=True)
    assert 'data-mode="variety"' in html
    assert 'APIキーが未設定' not in html
    # 品種は Web検索の初期値 ON
    assert 'id="aiNotesWebSearch" checked' in html
