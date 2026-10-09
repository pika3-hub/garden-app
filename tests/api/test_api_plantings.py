import json

import pytest


@pytest.fixture
def base(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    eggplant = sql("INSERT INTO crops (name, crop_type) VALUES ('なす', 'ナス科')")
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    return {'crop': crop, 'variety': variety, 'eggplant': eggplant, 'location': location}


def _plant(api, **payload):
    res = api.post('/api/v1/plantings', json=payload)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_by_crop(api, base):
    data = _plant(api, location_id=base['location'], crop_id=base['crop'],
                  planted_date='2026-05-01', quantity='3')
    assert data['crop'] == {'id': base['crop'], 'name': 'トマト'}
    assert data['variety'] is None
    assert data['display_name'] == 'トマト'
    assert data['location'] == {'id': base['location'], 'name': '南の畑'}
    assert data['status'] == 'active'
    assert data['quantity'] == 3
    assert data['web_url'].endswith(f'/plantings/{data["id"]}')


def test_create_by_variety(api, base):
    data = _plant(api, location_id=base['location'], variety_id=base['variety'])
    assert data['crop_id'] is None
    assert data['variety'] == {'id': base['variety'], 'name': 'アイコ'}
    assert data['crop'] == {'id': base['crop'], 'name': 'トマト'}
    assert data['display_name'] == 'アイコ（トマト）'


@pytest.mark.parametrize('payload, field', [
    ({'crop_id': 'C', 'variety_id': 'V'}, 'variety_id'),   # 両方
    ({}, 'crop_id'),                                       # どちらも無し
])
def test_create_requires_exactly_one_of_crop_or_variety(api, base, payload, field):
    payload = {k: base['crop'] if v == 'C' else base['variety'] for k, v in payload.items()}
    res = api.post('/api/v1/plantings', json={'location_id': base['location'], **payload})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0]['field'] == field


def test_create_rejects_status_and_end_date(api, base):
    res = api.post('/api/v1/plantings', json={'location_id': base['location'], 'crop_id': base['crop'],
                                              'status': 'harvested'})
    assert res.status_code == 422
    res = api.post('/api/v1/plantings', json={'location_id': base['location'], 'crop_id': base['crop'],
                                              'end_date': '2026-10-01'})
    assert res.status_code == 422
    assert '/end' in res.get_json()['error']['details'][0]['reason']


def test_patch_switch_crop_to_variety(api, base):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'], notes='メモ')
    data = api.patch(f'/api/v1/plantings/{planting["id"]}',
                     json={'variety_id': base['variety']}).get_json()['data']
    assert data['crop_id'] is None
    assert data['variety_id'] == base['variety']
    assert data['notes'] == 'メモ'


def test_end_planting(api, base, sql):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'])
    canvas = {'version': '2.0', 'placements': [{'locationCropId': planting['id']}]}
    sql('UPDATE locations SET canvas_data = ? WHERE id = ?', (json.dumps(canvas), base['location']))
    res = api.post(f'/api/v1/plantings/{planting["id"]}/end', json={'end_date': '2026-10-01'})
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['status'] == 'harvested'
    assert data['end_date'] == '2026-10-01'
    canvas_now = json.loads(sql('SELECT canvas_data FROM locations WHERE id = ?', (base['location'],))[0]['canvas_data'])
    assert canvas_now['placements'] == []
    # 2回目は 422（active ではない）
    res = api.post(f'/api/v1/plantings/{planting["id"]}/end', json={})
    assert res.status_code == 422


def test_end_planting_defaults_to_today(api, base):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'])
    data = api.post(f'/api/v1/plantings/{planting["id"]}/end').get_json()['data']
    assert data['end_date'] is not None


def test_patch_end_date_only_when_harvested(api, base):
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'])
    res = api.patch(f'/api/v1/plantings/{planting["id"]}', json={'end_date': '2026-10-02'})
    assert res.status_code == 422
    api.post(f'/api/v1/plantings/{planting["id"]}/end', json={'end_date': '2026-10-01'})
    data = api.patch(f'/api/v1/plantings/{planting["id"]}',
                     json={'end_date': '2026-10-02', 'notes': '終了'}).get_json()['data']
    assert data['end_date'] == '2026-10-02'
    assert data['notes'] == '終了'


def test_list_plantings(api, base):
    a = _plant(api, location_id=base['location'], crop_id=base['crop'], planted_date='2026-05-01')
    b = _plant(api, location_id=base['location'], variety_id=base['variety'], planted_date='2026-05-02')
    c = _plant(api, location_id=base['location'], crop_id=base['eggplant'], planted_date='2026-05-03')
    api.post(f'/api/v1/plantings/{c["id"]}/end')

    ids = lambda url: [p['id'] for p in api.get(url).get_json()['data']]  # noqa: E731
    assert ids('/api/v1/plantings') == [b['id'], a['id']]                        # 既定は active
    assert ids('/api/v1/plantings?status=all') == [c['id'], b['id'], a['id']]
    assert ids(f'/api/v1/plantings?crop_id={base["crop"]}') == [b['id'], a['id']]  # 品種経由も含む
    assert ids('/api/v1/plantings?q=アイコ') == [b['id']]
    assert ids('/api/v1/plantings?status=all&q=南の畑') == [c['id'], b['id'], a['id']]
    assert api.get('/api/v1/plantings?status=done').status_code == 422


def test_patch_planted_date_cannot_be_after_children(api, base, sql):
    """画面と同じく、植え付け日は栽培記録・収穫の日付より後にできない（日数が負になるのを防ぐ）"""
    planting = _plant(api, location_id=base['location'], crop_id=base['crop'], planted_date='2026-05-01')
    sql("INSERT INTO harvests (location_crop_id, harvest_date) VALUES (?, '2026-06-01')", (planting['id'],))
    res = api.patch(f'/api/v1/plantings/{planting["id"]}', json={'planted_date': '2026-09-01'})
    assert res.status_code == 422
    detail = res.get_json()['error']['details'][0]
    assert detail['field'] == 'planted_date'
    assert '2026-06-01' in detail['reason']
    res = api.patch(f'/api/v1/plantings/{planting["id"]}', json={'planted_date': '2026-06-01'})
    assert res.status_code == 200
