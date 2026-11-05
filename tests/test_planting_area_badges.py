import json

import pytest

from app.database import get_db
from app.models.planting import Planting


def _exec(app, query, params=()):
    with app.app_context():
        db = get_db()
        cur = db.execute(query, params)
        db.commit()
        return cur.lastrowid


@pytest.fixture
def garden(app):
    crop = _exec(app, "INSERT INTO crops (name, crop_type) VALUES ('ニンニク', 'ねぎ類')")
    loc = _exec(app, "INSERT INTO locations (name, location_type, canvas_top_direction) VALUES ('東の畑', '畑', '東')")
    placed = _exec(app, "INSERT INTO plantings (location_id, crop_id, status, planted_date) VALUES (?, ?, 'active', '2026-10-20')", (loc, crop))
    unplaced = _exec(app, "INSERT INTO plantings (location_id, crop_id, status, planted_date) VALUES (?, ?, 'active', '2026-10-21')", (loc, crop))
    ended = _exec(app, "INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'ended')", (loc, crop))
    snapshot = {'version': '2.0', 'placements': [{'locationCropId': ended, 'x': 700, 'y': 700}]}
    _exec(app, 'UPDATE plantings SET canvas_snapshot = ? WHERE id = ?', (json.dumps(snapshot), ended))
    canvas = {'version': '2.0', 'placements': [{'locationCropId': placed, 'x': 0, 'y': 0},
                                               {'locationCropId': placed, 'x': 300, 'y': 0}]}
    _exec(app, 'UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), loc))
    return {'loc': loc, 'placed': placed, 'unplaced': unplaced, 'ended': ended}


def test_area_map(app, garden):
    with app.app_context():
        areas = Planting.area_map()
        by_loc = Planting.area_map(garden['loc'])
    assert areas[garden['placed']] == ['北東', '東']
    assert areas.get(garden['unplaced'], []) == []
    assert areas[garden['ended']] == ['南西']     # スナップショットから
    assert by_loc == areas


def test_area_map_survives_broken_canvas(app, garden):
    _exec(app, "UPDATE locations SET canvas_data = 'broken' WHERE id = ?", (garden['loc'],))
    with app.app_context():
        assert Planting.area_map().get(garden['placed'], []) == []


def test_planting_list_and_detail_show_badge(client, garden):
    assert 'planting-area-badge">北東・東<' in client.get('/plantings/?status=all').get_data(as_text=True)
    assert 'planting-area-badge">北東・東<' in client.get(f'/plantings/{garden["placed"]}').get_data(as_text=True)
    assert 'planting-area-badge' not in client.get(f'/plantings/{garden["unplaced"]}').get_data(as_text=True)


def test_select_modal_and_related_card_show_badge(client, app, garden):
    html = client.get('/diary/new').get_data(as_text=True)
    assert 'planting-area-badge">北東・東<' in html
    diary = _exec(app, "INSERT INTO diary_entries (title, entry_date) VALUES ('日記', '2026-10-21')")
    _exec(app, "INSERT INTO diary_relations (diary_id, relation_type, location_crop_id) VALUES (?, 'location_crop', ?)",
          (diary, garden['placed']))
    assert 'planting-area-badge">北東・東<' in client.get(f'/diary/{diary}').get_data(as_text=True)
