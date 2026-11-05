"""植え付けの削除（画面）: 見取り図からその植え付けのアイコンも取り除く"""
import json

from app.database import get_db


def test_remove_crop_route_unplaces_only_that_planting(app, client):
    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ニンニク', 'ネギ科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        deleted_id = db.execute('INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
                                (location_id, crop_id)).lastrowid
        kept_id = db.execute('INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
                             (location_id, crop_id)).lastrowid
        canvas = {'version': '2.0', 'placements': [
            {'locationCropId': deleted_id, 'x': 1, 'y': 2},
            {'locationCropId': kept_id, 'x': 3, 'y': 4},
        ]}
        db.execute('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), location_id))
        db.commit()

    res = client.post(f'/locations/{location_id}/remove/{deleted_id}')
    assert res.status_code == 302

    with app.app_context():
        db = get_db()
        assert db.execute('SELECT 1 FROM plantings WHERE id = ?', (deleted_id,)).fetchone() is None
        loc = db.execute('SELECT canvas_data FROM locations WHERE id = ?', (location_id,)).fetchone()
        assert [p['locationCropId'] for p in json.loads(loc['canvas_data'])['placements']] == [kept_id]
