import html as htmllib
import json
import re

import pytest

from app.database import get_db


@pytest.fixture
def east_field(app):
    with app.app_context():
        db = get_db()
        loc = db.execute("INSERT INTO locations (name, location_type, canvas_top_direction) VALUES ('東の畑', '畑', '東')").lastrowid
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ニンニク', 'ねぎ類')").lastrowid
        planting = db.execute("INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'active')", (loc, crop)).lastrowid
        db.commit()
    return {'loc': loc, 'planting': planting}


@pytest.mark.parametrize('path', ['/locations/{loc}', '/plantings/{planting}', '/locations/{loc}/canvas',
                                  '/plantings/{planting}/place'])
def test_canvas_views_have_area_config_and_toggle(client, east_field, path):
    html = client.get(path.format(**east_field)).get_data(as_text=True)
    assert 'data-canvas-areas=' in html
    raw = re.search(r'data-canvas-areas="([^"]*)"', html).group(1)
    assert json.loads(htmllib.unescape(raw))['names'][0][0] == '北東'   # 上が東の左上
    assert 'data-canvas-grid-toggle=' in html
    assert 'js/canvas-areas.js' in html


def test_data_attribute_round_trips_as_json(client, east_field):
    html = client.get(f'/locations/{east_field["loc"]}').get_data(as_text=True)
    raw = re.search(r'data-canvas-areas="([^"]*)"', html).group(1)
    config = json.loads(htmllib.unescape(raw))
    assert config['names'][0][0] == '北東'
    assert config['edges'] == {'top': '東', 'right': '南', 'bottom': '西', 'left': '北'}


def test_grid_toggle_visible_to_viewers(anon_client, east_field):
    html = anon_client.get(f'/locations/{east_field["loc"]}').get_data(as_text=True)
    assert 'data-canvas-grid-toggle=' in html


def test_area_config_without_direction(app):
    with app.test_request_context():
        config = app.jinja_env.globals['canvas_area_config'](None)
    assert config == {'names': [['左上', '上', '右上'], ['左', '中央', '右'], ['左下', '下', '右下']], 'edges': None}
