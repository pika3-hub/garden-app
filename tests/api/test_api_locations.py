import json


def _create(api, **payload):
    res = api.post('/api/v1/locations', json={'name': '南の畑', 'location_type': '畑', **payload})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_location(api):
    data = _create(api, area_size='12.5', sun_exposure='全日')
    assert data['area_size'] == 12.5
    assert data['sun_exposure'] == '全日'
    assert data['active_plantings'] == []
    assert 'canvas_data' not in data


def test_create_location_validation(api):
    res = api.post('/api/v1/locations', json={
        'name': '畑', 'location_type': '畑', 'area_size': -1, 'sun_exposure': '晴れ',
        'bg_image': 'nope.webp', 'canvas_data': '{}'})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'area_size', 'sun_exposure', 'bg_image', 'canvas_data'}


def test_patch_keeps_canvas_data(api, sql):
    location = _create(api)
    canvas = json.dumps({'version': '2.0', 'placements': []})
    sql('UPDATE locations SET canvas_data = ? WHERE id = ?', (canvas, location['id']))
    res = api.patch(f'/api/v1/locations/{location["id"]}', json={'name': '北の畑'})
    assert res.get_json()['data']['name'] == '北の畑'
    assert sql('SELECT canvas_data FROM locations WHERE id = ?', (location['id'],))[0]['canvas_data'] == canvas


def test_location_lists_active_plantings(api, sql):
    location = _create(api)
    crop_id = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    planting_id = sql("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                      (location['id'], crop_id))
    sql("INSERT INTO plantings (location_id, crop_id, status) VALUES (?, ?, 'harvested')",
        (location['id'], crop_id))
    data = api.get(f'/api/v1/locations/{location["id"]}').get_json()['data']
    assert data['active_plantings'] == [
        {'id': planting_id, 'display_name': 'トマト / 南の畑（2026-05-01 植え付け）'}]


def test_list_locations(api):
    _create(api, name='南の畑')
    _create(api, name='ベランダ', location_type='プランター')
    names = [l['name'] for l in api.get('/api/v1/locations?location_type=プランター').get_json()['data']]
    assert names == ['ベランダ']
