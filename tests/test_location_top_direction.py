from app.database import get_db


def test_fresh_db_has_column(app):
    with app.app_context():
        columns = [r['name'] for r in get_db().execute('PRAGMA table_info(locations)')]
    assert 'canvas_top_direction' in columns


def _form(**extra):
    return {'name': '東の畑', 'location_type': '畑', **extra}


def test_create_and_update_from_form(client, app):
    client.post('/locations/create', data=_form(canvas_top_direction='東'))
    with app.app_context():
        row = get_db().execute('SELECT id, canvas_top_direction FROM locations').fetchone()
    assert row['canvas_top_direction'] == '東'
    client.post(f'/locations/{row["id"]}/update', data=_form(canvas_top_direction=''))
    with app.app_context():
        assert get_db().execute('SELECT canvas_top_direction FROM locations').fetchone()[0] is None


def test_unknown_value_is_saved_as_null(client, app):
    client.post('/locations/create', data=_form(canvas_top_direction='北東'))
    with app.app_context():
        assert get_db().execute('SELECT canvas_top_direction FROM locations').fetchone()[0] is None


def test_form_shows_choices(client, app):
    html = client.get('/locations/new').get_data(as_text=True)
    assert '見取り図の上の方角' in html
    assert '設定しない（上・下・左・右で呼ぶ）' in html


def test_detail_shows_direction_only_when_set(client, app):
    client.post('/locations/create', data=_form(canvas_top_direction='東'))
    client.post('/locations/create', data={'name': '無印の畑', 'location_type': '畑'})
    with app.app_context():
        rows = get_db().execute('SELECT id, name FROM locations ORDER BY id').fetchall()
    assert '見取り図の上:' in client.get(f'/locations/{rows[0]["id"]}').get_data(as_text=True)
    assert '見取り図の上:' not in client.get(f'/locations/{rows[1]["id"]}').get_data(as_text=True)
