import json

import pytest

from app.database import get_db

MESSAGE = '開いたあとに配置が変わっています。読み込み直してください'


@pytest.fixture
def loc(app):
    with app.app_context():
        db = get_db()
        loc_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        db.commit()
    return loc_id


def _canvas(*xs):
    return {'version': '2.0', 'placements': [{'locationCropId': 1, 'x': x, 'y': 0} for x in xs]}


def test_save_with_current_revision(client, loc):
    rev = client.get(f'/locations/{loc}/canvas/data').headers['X-Canvas-Revision']
    res = client.post(f'/locations/{loc}/canvas/save', json=_canvas(10), headers={'X-Canvas-Revision': rev})
    assert res.status_code == 200
    new_rev = res.get_json()['revision']
    assert new_rev != rev
    assert client.get(f'/locations/{loc}/canvas/data').headers['X-Canvas-Revision'] == new_rev
    # 続けて保存できる（エディターは返ったリビジョンを使う）
    assert client.post(f'/locations/{loc}/canvas/save', json=_canvas(20),
                       headers={'X-Canvas-Revision': new_rev}).status_code == 200


def test_save_after_change_is_rejected(client, app, loc):
    rev = client.get(f'/locations/{loc}/canvas/data').headers['X-Canvas-Revision']
    with app.app_context():
        db = get_db()
        db.execute('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(_canvas(99)), loc))
        db.commit()
    res = client.post(f'/locations/{loc}/canvas/save', json=_canvas(10), headers={'X-Canvas-Revision': rev})
    assert res.status_code == 409
    assert res.get_json() == {'status': 'conflict', 'message': MESSAGE}
    assert client.get(f'/locations/{loc}/canvas/data').get_json()['placements'][0]['x'] == 99


def test_save_without_revision_is_rejected(client, loc):
    assert client.post(f'/locations/{loc}/canvas/save', json=_canvas(10)).status_code == 409


def test_api_placement_changes_revision(client, app, loc):
    from app.models.planting import Planting
    with app.app_context():
        db = get_db()
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ニンニク', 'ねぎ類')").lastrowid
        planting = db.execute("INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'active')", (loc, crop)).lastrowid
        db.commit()
    rev = client.get(f'/locations/{loc}/canvas/data').headers['X-Canvas-Revision']
    with app.app_context():
        Planting.place_in_area(planting, (1, 1))
    res = client.post(f'/locations/{loc}/canvas/save', json=_canvas(10), headers={'X-Canvas-Revision': rev})
    assert res.status_code == 409


def _interfere_once(monkeypatch, app, loc, canvas):
    """canvas_text で読んだ直後に、ほかの保存が割り込んだことにする（1回だけ）"""
    from app.models.location import Location
    original = Location.canvas_text
    state = {'done': False}

    def reading(location_id):
        text = original(location_id)
        if not state['done']:
            state['done'] = True
            db = get_db()
            db.execute('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), loc))
            db.commit()
        return text
    monkeypatch.setattr(Location, 'canvas_text', staticmethod(reading))


def test_save_rejected_when_changed_after_revision_check(client, app, loc, monkeypatch):
    rev = client.get(f'/locations/{loc}/canvas/data').headers['X-Canvas-Revision']
    _interfere_once(monkeypatch, app, loc, _canvas(99))
    res = client.post(f'/locations/{loc}/canvas/save', json=_canvas(10), headers={'X-Canvas-Revision': rev})
    assert res.status_code == 409
    assert res.get_json() == {'status': 'conflict', 'message': MESSAGE}
    monkeypatch.undo()
    assert client.get(f'/locations/{loc}/canvas/data').get_json()['placements'][0]['x'] == 99


def test_place_in_area_retries_and_keeps_both(app, loc, monkeypatch):
    from app.models.planting import Planting
    with app.app_context():
        db = get_db()
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ニンニク', 'ねぎ類')").lastrowid
        planting = db.execute("INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'active')",
                              (loc, crop)).lastrowid
        db.commit()
        other = {'version': '2.0', 'placements': [{'locationCropId': 999, 'x': 0, 'y': 0}]}
        _interfere_once(monkeypatch, app, loc, other)
        spot = Planting.place_in_area(planting, (1, 1))
        placements = json.loads(db.execute('SELECT canvas_data FROM locations WHERE id = ?',
                                           (loc,)).fetchone()['canvas_data'])['placements']
        assert [p['locationCropId'] for p in placements] == [999, planting]
        row = db.execute('SELECT position_x, position_y FROM plantings WHERE id = ?', (planting,)).fetchone()
        assert (row['position_x'], row['position_y']) == (spot.x, spot.y)
