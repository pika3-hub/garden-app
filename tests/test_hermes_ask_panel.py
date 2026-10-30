"""Hermes に聞くパネル（右から開く offcanvas）が詳細画面に出るかのテスト"""
from tests.hermes_fakes import crop_id, fake_open, planting_id, variety_id  # noqa: F401


def test_panel_shown_for_owner_on_three_pages(client, fake_open, planting_id, crop_id, variety_id):
    for path in (f'/plantings/{planting_id}', f'/crops/{crop_id}', f'/varieties/{variety_id}'):
        html = client.get(path).get_data(as_text=True)
        assert 'id="hermes-ask-panel"' in html and 'js/hermes-ask.js' in html, path


def test_panel_carries_target(client, fake_open, planting_id):
    html = client.get(f'/plantings/{planting_id}').get_data(as_text=True)
    assert 'data-entity-type="planting"' in html
    assert f'data-entity-id="{planting_id}"' in html


def test_panel_hidden_for_anonymous(anon_client, fake_open, planting_id):
    assert 'hermes-ask-panel' not in anon_client.get(f'/plantings/{planting_id}').get_data(as_text=True)


def test_panel_hidden_without_key(client, app, planting_id):
    app.config['HERMES_API_KEY'] = ''
    assert 'hermes-ask-panel' not in client.get(f'/plantings/{planting_id}').get_data(as_text=True)


def test_key_not_in_page(client, fake_open, planting_id):
    assert 'test-hermes-key' not in client.get(f'/plantings/{planting_id}').get_data(as_text=True)


def test_panel_carries_urls(client, fake_open, planting_id):
    html = client.get(f'/plantings/{planting_id}').get_data(as_text=True)
    assert 'data-hermes-ask' in html
    assert f'data-history-url="/hermes/ask/planting/{planting_id}/history"' in html
    assert f'data-runs-url="/hermes/ask/planting/{planting_id}/runs"' in html
    assert f'data-new-url="/hermes/ask/planting/{planting_id}/new"' in html
