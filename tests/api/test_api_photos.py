import os

from tests.api.helpers import file_part, image_bytes


def _upload(api, n=1, notes=None):
    form = {'files': [file_part(image_bytes('JPEG'), f'IMG_{i}.jpg') for i in range(n)]}
    if notes:
        form['data'] = '{"notes": "%s"}' % notes
    res = api.post('/api/v1/photos', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_upload_photos(api, api_app):
    photos = _upload(api, 2, notes='畑で撮影')
    assert len(photos) == 2
    assert photos[0]['original_filename'] == 'IMG_0.jpg'
    assert photos[0]['notes'] == '畑で撮影'
    assert photos[0]['usage_count'] == 0
    rel = photos[0]['image_url'].split('/static/uploads/')[1]
    assert rel.startswith('photo_pool/')
    assert os.path.exists(os.path.join(api_app.config['UPLOAD_FOLDER'], rel))


def test_upload_requires_files_and_rejects_heic(api):
    assert api.post('/api/v1/photos', data={}, content_type='multipart/form-data').status_code == 422
    heic = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32
    res = api.post('/api/v1/photos', data={'files': [file_part(heic, 'a.heic')]},
                   content_type='multipart/form-data')
    assert res.status_code == 415


def test_use_pool_photo_for_main_and_extra_images(api, sql):
    p1, p2 = _upload(api, 2)
    res = api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科',
                                          'photo_pool_id': p1['id'], 'extra_photo_pool_ids': [p2['id']]})
    assert res.status_code == 201, res.get_json()
    crop = res.get_json()['data']
    assert '/static/uploads/crops/' in crop['image_url']
    assert len(crop['extra_images']) == 1
    usages = sql('SELECT photo_pool_id, entity_type FROM photo_pool_usages ORDER BY id')
    assert usages == [{'photo_pool_id': p1['id'], 'entity_type': 'crop'},
                      {'photo_pool_id': p2['id'], 'entity_type': 'supplement'}]
    detail = api.get(f'/api/v1/photos/{p1["id"]}').get_json()['data']
    assert detail['usage_count'] == 1
    assert detail['usages'][0]['entity_type'] == 'crop'
    unused = api.get('/api/v1/photos?unused=true').get_json()['data']
    assert unused == []


def test_pool_photo_errors(api, api_app):
    (photo,) = _upload(api)
    form = {'data': '{"name":"a","crop_type":"b","photo_pool_id":%d}' % photo['id'],
            'image': file_part(image_bytes(), 'a.png')}
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 422  # image と photo_pool_id の同時指定
    res = api.post('/api/v1/crops', json={'name': 'a', 'crop_type': 'b', 'photo_pool_id': 999})
    assert res.status_code == 422
    rel = photo['image_url'].split('/static/uploads/')[1]
    os.remove(os.path.join(api_app.config['UPLOAD_FOLDER'], rel))
    res = api.post('/api/v1/crops', json={'name': 'a', 'crop_type': 'b', 'photo_pool_id': photo['id']})
    assert res.status_code == 422
    assert '見つかりません' in res.get_json()['error']['details'][0]['reason']


def test_list_photos_validates_args(api):
    _upload(api)
    body = api.get('/api/v1/photos').get_json()
    assert body['meta']['total'] == 1
    assert api.get('/api/v1/photos?unused=yes').status_code == 422
    assert api.get('/api/v1/photos/999').status_code == 404
