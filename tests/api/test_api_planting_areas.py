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
