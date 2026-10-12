"""栽培終了（画面）: 見取り図のスナップショット保存と配置解除"""
import json

from app.database import get_db


def test_end_cultivation_route_snapshots_and_unplaces(app, client):
    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        planting_id = db.execute('INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
                                 (location_id, crop_id)).lastrowid
        canvas = {'version': '2.0', 'placements': [{'locationCropId': planting_id, 'x': 1, 'y': 2}]}
        db.execute('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), location_id))
        db.commit()

    res = client.post(f'/plantings/{planting_id}/end', data={'end_date': '2026-10-01'})
    assert res.status_code == 302

    with app.app_context():
        db = get_db()
        p = db.execute('SELECT status, end_date, canvas_snapshot FROM plantings WHERE id = ?',
                       (planting_id,)).fetchone()
        assert p['status'] == 'ended'
        assert str(p['end_date']) == '2026-10-01'
        assert json.loads(p['canvas_snapshot'])['placements'][0]['locationCropId'] == planting_id
        loc = db.execute('SELECT canvas_data FROM locations WHERE id = ?', (location_id,)).fetchone()
        assert json.loads(loc['canvas_data'])['placements'] == []


def test_migration_renames_harvested_to_ended(app):
    from app.database import run_migrations

    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        ended_id = db.execute("INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'harvested')",
                              (location_id, crop_id)).lastrowid
        active_id = db.execute('INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
                               (location_id, crop_id)).lastrowid
        db.commit()

        run_migrations(app, db)

        status = {r['id']: r['status'] for r in db.execute('SELECT id, status FROM plantings')}
        assert status == {ended_id: 'ended', active_id: 'active'}
