import json

import pytest


@pytest.fixture
def field(sql):
    crop = sql("INSERT INTO crops (name, crop_type, icon_path, image_color) VALUES ('ニンニク', 'ねぎ類', 'onion_garlic.png', '#B39DDB')")
    north = sql("INSERT INTO locations (name, location_type, canvas_top_direction) VALUES ('北の畑', '畑', '北')")
    plain = sql("INSERT INTO locations (name, location_type) VALUES ('プランター', 'プランター')")
    return {'crop': crop, 'north': north, 'plain': plain}


def _plant(api, location, crop, **extra):
    res = api.post('/api/v1/plantings', json={'location_id': location, 'crop_id': crop, **extra})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def _set_canvas(sql, location, placements):
    sql('UPDATE locations SET canvas_data = ? WHERE id = ?',
        (json.dumps({'version': '2.0', 'placements': placements}), location))


def test_areas_in_detail_and_list(api, sql, field):
    a = _plant(api, field['north'], field['crop'])
    b = _plant(api, field['plain'], field['crop'])
    c = _plant(api, field['north'], field['crop'])
    _set_canvas(sql, field['north'], [{'locationCropId': a['id'], 'x': 0, 'y': 0},
                                      {'locationCropId': a['id'], 'x': 375, 'y': 0}])
    _set_canvas(sql, field['plain'], [{'locationCropId': b['id'], 'x': 750, 'y': 750}])
    assert api.get(f'/api/v1/plantings/{a["id"]}').get_json()['data']['areas'] == ['北西', '北']
    assert api.get(f'/api/v1/plantings/{b["id"]}').get_json()['data']['areas'] == ['右下']
    assert api.get(f'/api/v1/plantings/{c["id"]}').get_json()['data']['areas'] == []
    listed = {p['id']: p['areas'] for p in api.get('/api/v1/plantings').get_json()['data']}
    assert listed == {a['id']: ['北西', '北'], b['id']: ['右下'], c['id']: []}


def test_ended_planting_areas_from_snapshot(api, sql, field):
    a = _plant(api, field['north'], field['crop'])
    _set_canvas(sql, field['north'], [{'locationCropId': a['id'], 'x': 750, 'y': 0}])
    api.post(f'/api/v1/plantings/{a["id"]}/end', json={})
    assert api.get(f'/api/v1/plantings/{a["id"]}').get_json()['data']['areas'] == ['北東']


@pytest.mark.parametrize('area', ['西', '左'])
def test_filter_by_area(api, sql, field, area):
    ids = [_plant(api, field['north'], field['crop'])['id'] for _ in range(4)]
    _set_canvas(sql, field['north'], [{'locationCropId': i, 'x': 0, 'y': 375} for i in ids[:3]]
                + [{'locationCropId': ids[3], 'x': 750, 'y': 375}])
    body = api.get(f'/api/v1/plantings?location_id={field["north"]}&area={area}&limit=2').get_json()
    assert body['meta']['total'] == 3
    assert len(body['data']) == 2
    body = api.get(f'/api/v1/plantings?location_id={field["north"]}&area={area}&limit=2&offset=2').get_json()
    assert [p['id'] for p in body['data']] == [ids[0]]   # 並びは植え付け日 → id の新しい順


def test_filter_by_area_requires_location(api, field):
    res = api.get('/api/v1/plantings?area=北')
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == 'area'


def test_filter_direction_on_location_without_direction(api, field):
    res = api.get(f'/api/v1/plantings?location_id={field["plain"]}&area=北')
    assert res.status_code == 422
    assert '上・左下' in res.get_json()['error']['details'][0]['reason']


def test_filter_area_on_missing_location_is_empty(api, field):
    res = api.get('/api/v1/plantings?location_id=9999&area=左')
    assert res.status_code == 200
    assert res.get_json()['meta']['total'] == 0


def _canvas(sql, location):
    raw = sql('SELECT canvas_data FROM locations WHERE id = ?', (location,))[0]['canvas_data']
    return json.loads(raw)['placements'] if raw else []


def test_create_with_area_places_icon(api, sql, field):
    data = _plant(api, field['north'], field['crop'], area='北')
    assert data['areas'] == ['北']
    assert data['placement'] == {'area': '北', 'x': 375, 'y': 108, 'warning': None}
    [p] = _canvas(sql, field['north'])
    assert p == {'locationCropId': data['id'], 'cropId': field['crop'], 'x': 375, 'y': 108,
                 'iconPath': 'onion_garlic.png', 'imageColor': '#B39DDB', 'cropName': 'ニンニク', 'variety': ''}
    row = sql('SELECT position_x, position_y FROM plantings WHERE id = ?', (data['id'],))[0]
    assert (row['position_x'], row['position_y']) == (375, 108)


def test_create_with_variety_uses_variety_name(api, sql, field):
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'ホワイト六片')", (field['crop'],))
    res = api.post('/api/v1/plantings', json={'location_id': field['north'], 'variety_id': variety, 'area': '上'})
    assert res.status_code == 201
    [p] = _canvas(sql, field['north'])
    assert (p['cropName'], p['variety'], p['cropId']) == ('ニンニク', 'ホワイト六片', field['crop'])


@pytest.mark.parametrize('location_key, area, reason', [
    ('plain', '北', '上・左下'),
    ('north', '北北東', '北西'),
])
def test_create_with_bad_area_creates_nothing(api, sql, field, location_key, area, reason):
    res = api.post('/api/v1/plantings', json={'location_id': field[location_key], 'crop_id': field['crop'], 'area': area})
    assert res.status_code == 422
    assert reason in res.get_json()['error']['details'][0]['reason']
    assert sql('SELECT COUNT(*) AS n FROM plantings')[0]['n'] == 0


def test_place_adds_second_icon_apart(api, sql, field):
    data = _plant(api, field['north'], field['crop'], area='北')
    res = api.post(f'/api/v1/plantings/{data["id"]}/place', json={'area': '北'})
    assert res.status_code == 200
    placed = res.get_json()['data']['placement']
    assert placed['warning'] is None
    first, second = _canvas(sql, field['north'])
    assert ((first['x'] - second['x']) ** 2 + (first['y'] - second['y']) ** 2) ** 0.5 >= 50
    row = sql('SELECT position_x, position_y FROM plantings WHERE id = ?', (data['id'],))[0]
    assert (row['position_x'], row['position_y']) == (first['x'], first['y'])   # 最初の配置のまま


def test_place_crowded_returns_warning(api, sql, field):
    data = _plant(api, field['north'], field['crop'])
    _set_canvas(sql, field['north'], [{'locationCropId': 999, 'x': x - 25, 'y': y - 25}
                                      for x in range(292, 509, 40) for y in range(25, 242, 40)])
    placed = api.post(f'/api/v1/plantings/{data["id"]}/place', json={'area': '北'}).get_json()['data']['placement']
    assert placed['warning'] == '北エリアは混んでいて、ほかのアイコンと重なっています。画面で確かめてください'


def test_place_on_broken_canvas_starts_fresh(api, sql, field):
    data = _plant(api, field['north'], field['crop'])
    sql("UPDATE locations SET canvas_data = 'broken' WHERE id = ?", (field['north'],))
    assert api.post(f'/api/v1/plantings/{data["id"]}/place', json={'area': '中央'}).status_code == 200
    assert len(_canvas(sql, field['north'])) == 1


def test_place_rejects_ended_and_bad_body(api, field):
    data = _plant(api, field['north'], field['crop'])
    assert api.post(f'/api/v1/plantings/{data["id"]}/place', json={}).status_code == 422
    assert api.post(f'/api/v1/plantings/{data["id"]}/place', json={'area': '北', 'x': 1}).status_code == 422
    api.post(f'/api/v1/plantings/{data["id"]}/end', json={})
    res = api.post(f'/api/v1/plantings/{data["id"]}/place', json={'area': '北'})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == 'status'


def test_patch_with_area_points_to_place(api, field):
    data = _plant(api, field['north'], field['crop'])
    res = api.patch(f'/api/v1/plantings/{data["id"]}', json={'area': '北'})
    assert res.status_code == 422
    assert '/place' in res.get_json()['error']['details'][0]['reason']
