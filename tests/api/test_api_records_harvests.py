import pytest

from tests.api.helpers import file_part, image_bytes, multipart


@pytest.fixture
def plantings(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    by_crop = sql("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                  (location, crop))
    by_variety = sql("INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-02')",
                     (location, variety))
    return {'crop': crop, 'by_crop': by_crop, 'by_variety': by_variety}


def test_create_record_with_image(api, plantings):
    form = multipart({'planting_id': plantings['by_variety'], 'recorded_at': '2026-06-01', 'notes': '花が咲いた'},
                     image=file_part(image_bytes('JPEG'), 'flower.jpg'))
    res = api.post('/api/v1/planting_records', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['planting'] == {'id': plantings['by_variety'],
                                'display_name': 'アイコ（トマト） / 南の畑（2026-05-02 植え付け）'}
    assert data['days_from_planting'] == 30
    assert '/static/uploads/growth_records/' in data['image_url']
    assert data['web_url'].endswith(f'/plantings/record/{data["id"]}')
    assert 'extra_images' not in data


def test_record_rejects_extra_images(api, plantings):
    form = multipart({'planting_id': plantings['by_crop'], 'recorded_at': '2026-06-01'},
                     extra_images=file_part(image_bytes(), 'a.png'))
    res = api.post('/api/v1/planting_records', data=form, content_type='multipart/form-data')
    assert res.status_code == 422
    assert '複数件作成' in res.get_json()['error']['details'][0]['reason']


def test_record_planting_cannot_change(api, plantings):
    rec = api.post('/api/v1/planting_records', json={'planting_id': plantings['by_crop'],
                                                     'recorded_at': '2026-06-01'}).get_json()['data']
    res = api.patch(f'/api/v1/planting_records/{rec["id"]}', json={'planting_id': plantings['by_variety']})
    assert res.status_code == 422
    res = api.patch(f'/api/v1/planting_records/{rec["id"]}', json={'notes': '実がついた'})
    assert res.get_json()['data']['notes'] == '実がついた'


def test_list_records(api, plantings):
    for pid, day in ((plantings['by_crop'], '2026-06-01'), (plantings['by_variety'], '2026-06-10')):
        api.post('/api/v1/planting_records', json={'planting_id': pid, 'recorded_at': day})
    ids = lambda url: [r['recorded_at'] for r in api.get(url).get_json()['data']]  # noqa: E731
    assert ids(f'/api/v1/planting_records?planting_id={plantings["by_crop"]}') == ['2026-06-01']
    assert ids(f'/api/v1/planting_records?crop_id={plantings["crop"]}') == ['2026-06-10', '2026-06-01']
    assert ids('/api/v1/planting_records?date_from=2026-06-05') == ['2026-06-10']


def test_create_harvest(api, plantings):
    res = api.post('/api/v1/harvests', json={'planting_id': plantings['by_variety'], 'harvest_date': '2026-07-01',
                                             'quantity': '300', 'unit': 'g'})
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['quantity'] == 300
    assert data['unit'] == 'g'
    assert data['planting']['id'] == plantings['by_variety']
    assert data['extra_images'] == []


def test_harvest_validation(api, plantings):
    res = api.post('/api/v1/harvests', json={'planting_id': 999, 'harvest_date': '7/1', 'quantity': '300g'})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'planting_id', 'harvest_date', 'quantity'}


@pytest.mark.parametrize('path, body', [
    ('/api/v1/planting_records', {'recorded_at': '2026-06-01'}),
    ('/api/v1/harvests', {'harvest_date': '2026-07-01'}),
])
def test_cannot_create_for_ended_planting(api, plantings, sql, path, body):
    """画面と同じく、栽培終了した植え付けには新しく作成できない（既存の記録は修正できる）"""
    created = api.post(path, json={'planting_id': plantings['by_crop'], **body}).get_json()['data']
    sql("UPDATE plantings SET status = 'harvested', end_date = '2026-08-01' WHERE id = ?", (plantings['by_crop'],))

    res = api.post(path, json={'planting_id': plantings['by_crop'], **body})
    assert res.status_code == 422
    details = res.get_json()['error']['details']
    assert [d['field'] for d in details] == ['planting_id']
    assert '栽培中ではありません' in details[0]['reason']

    res = api.patch(f'{path}/{created["id"]}', json={'notes': '修正'})
    assert res.status_code == 200, res.get_json()


def test_list_harvests_by_crop(api, plantings):
    api.post('/api/v1/harvests', json={'planting_id': plantings['by_crop'], 'harvest_date': '2026-07-01'})
    api.post('/api/v1/harvests', json={'planting_id': plantings['by_variety'], 'harvest_date': '2026-07-02'})
    data = api.get(f'/api/v1/harvests?crop_id={plantings["crop"]}').get_json()['data']
    assert [h['harvest_date'] for h in data] == ['2026-07-02', '2026-07-01']
    data = api.get('/api/v1/harvests?q=アイコ').get_json()['data']
    assert [h['harvest_date'] for h in data] == ['2026-07-02']
