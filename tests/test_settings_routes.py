from app.models.app_settings import AppSettings


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
