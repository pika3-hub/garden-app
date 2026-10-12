import os

import pytest
from PIL import Image

from tests.api.helpers import file_part, heic_bytes, image_bytes, jpeg_bytes


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


def test_upload_requires_files(api):
    assert api.post('/api/v1/photos', data={}, content_type='multipart/form-data').status_code == 422


def test_upload_heic_is_saved_as_jpeg(api, api_app):
    pytest.importorskip('pillow_heif')
    res = api.post('/api/v1/photos', data={'files': [file_part(heic_bytes(taken_at='2026:10:01 09:30:00'), 'IMG_0001.HEIC')]},
                   content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    photo = res.get_json()['data'][0]
    assert photo['original_filename'] == 'IMG_0001.HEIC'
    assert photo['taken_at'].startswith('2026-10-01')
    rel = photo['image_url'].split('/static/uploads/')[1]
    assert rel.endswith('.jpg')
    with Image.open(os.path.join(api_app.config['UPLOAD_FOLDER'], rel)) as saved:
        assert saved.format == 'JPEG'


def test_api_upload_strips_gps(api, api_app):
    res = api.post('/api/v1/photos', data={'files': [file_part(jpeg_bytes(gps=True), 'IMG.jpg')]},
                   content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    rel = res.get_json()['data'][0]['image_url'].split('/static/uploads/')[1]
    assert not Image.open(os.path.join(api_app.config['UPLOAD_FOLDER'], rel)).getexif().get_ifd(0x8825)


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
