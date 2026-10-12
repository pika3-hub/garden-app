import io
import os

import pytest
from PIL import Image

from tests.api.helpers import file_part, image_bytes, multipart


@pytest.fixture
def record(api, sql):
    """画像付きの栽培記録（元画像 1600×1200、サムネイルは 800×600 になる）"""
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    planting = sql("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                   (location, crop))
    form = multipart({'planting_id': planting, 'recorded_at': '2026-06-01'},
                     image=file_part(image_bytes('JPEG', size=(1600, 1200)), 'leaf.jpg'))
    res = api.post('/api/v1/planting_records', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    return {**res.get_json()['data'], 'crop_id': crop}


def _size(res):
    return Image.open(io.BytesIO(res.data)).size


def test_get_original_image(api, record):
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image')
    assert res.status_code == 200
    assert res.mimetype == 'image/jpeg'
    assert _size(res) == (1600, 1200)


def test_get_thumbnail(api, record):
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image?size=thumb')
    assert res.status_code == 200
    assert res.mimetype == 'image/jpeg'
    assert _size(res) == (800, 600)


def test_thumbnail_falls_back_to_original(api, api_app, record):
    rel = record['image_url'].split('/static/uploads/')[1]
    folder, name = rel.split('/')
    os.remove(os.path.join(api_app.config['UPLOAD_FOLDER'], folder, 'thumbs',
                           os.path.splitext(name)[0] + '.jpg'))
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image?size=thumb')
    assert res.status_code == 200
    assert _size(res) == (1600, 1200)


def test_no_image_is_404(api, record):
    res = api.get(f'/api/v1/crops/{record["crop_id"]}/image')
    assert res.status_code == 404
    assert res.get_json()['error']['code'] == 'no_image'


def test_missing_file_is_404(api, api_app, record):
    rel = record['image_url'].split('/static/uploads/')[1]
    os.remove(os.path.join(api_app.config['UPLOAD_FOLDER'], rel))
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image')
    assert res.status_code == 404
    assert res.get_json()['error']['code'] == 'image_file_missing'


def test_unknown_id_is_404(api, record):
    res = api.get('/api/v1/planting_records/9999/image')
    assert res.status_code == 404
    assert res.get_json()['error']['code'] == 'not_found'


def test_invalid_query_is_422(api, record):
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image?size=large')
    assert res.status_code == 422
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image?foo=1')
    assert res.status_code == 422


def test_requires_token(anon, record):
    assert anon.get(f'/api/v1/planting_records/{record["id"]}/image').status_code == 401


def test_resource_without_image_has_no_route(api, sql):
    task = sql("INSERT INTO tasks (title) VALUES ('水やり')")
    res = api.get(f'/api/v1/tasks/{task}/image')
    assert res.status_code == 404
    assert res.get_json()['error']['code'] == 'not_found'


def test_path_outside_uploads_is_rejected(api, sql, record):
    sql("UPDATE planting_records SET image_path = '../../secret.jpg' WHERE id = ?", (record['id'],))
    res = api.get(f'/api/v1/planting_records/{record["id"]}/image')
    assert res.status_code == 404


def test_get_photo_pool_image(api):
    res = api.post('/api/v1/photos', data={'files': [file_part(image_bytes('PNG', size=(1000, 1000)), 'a.png')]},
                   content_type='multipart/form-data')
    photo = res.get_json()['data'][0]
    res = api.get(f'/api/v1/photos/{photo["id"]}/image')
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    assert _size(res) == (1000, 1000)
    res = api.get(f'/api/v1/photos/{photo["id"]}/image?size=thumb')
    assert res.mimetype == 'image/jpeg'
    assert _size(res) == (600, 600)
    assert api.get('/api/v1/photos/9999/image').status_code == 404
