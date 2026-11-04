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
