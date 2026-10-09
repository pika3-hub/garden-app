import logging
import os

from app.api.choices import crop_icons
from tests.api.helpers import TOKEN, file_part, image_bytes, multipart


def _create(api, **payload):
    payload = {'name': 'トマト', 'crop_type': 'ナス科', **payload}
    res = api.post('/api/v1/crops', json=payload)
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_minimal(api):
    data = _create(api)
    assert data['name'] == 'トマト'
    assert data['image_color'] == '#4CAF50'
    assert data['image_url'] is None
    assert data['extra_images'] == []
    assert data['varieties'] == []
    assert data['web_url'] == f'http://garden.test:5000/crops/{data["id"]}'


def test_create_reports_missing_and_unknown_fields(api):
    res = api.post('/api/v1/crops', json={'nmae': 'トマト'})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'nmae', 'name', 'crop_type'}


def test_create_rejects_unknown_icon(api):
    res = api.post('/api/v1/crops', json={'name': 'a', 'crop_type': 'b', 'icon_path': 'nope.png'})
    assert res.status_code == 422
    assert '/api/v1/meta' in res.get_json()['error']['details'][0]['reason']


def test_create_accepts_existing_icon(api):
    icon = crop_icons()[0]
    assert _create(api, icon_path=icon)['icon_path'] == icon


def test_create_with_image_and_extra_images(api, api_app):
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'},
                     image=file_part(image_bytes('JPEG'), 'main.jpg'),
                     extra_images=[file_part(image_bytes(), 'a.png'), file_part(image_bytes(), 'b.png')])
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['image_url'].startswith('http://garden.test:5000/static/uploads/crops/')
    assert len(data['extra_images']) == 2
    uploads = api_app.config['UPLOAD_FOLDER']
    rel = data['image_url'].split('/static/uploads/')[1]
    assert os.path.exists(os.path.join(uploads, rel))
    assert os.path.isdir(os.path.join(uploads, 'crops', 'thumbs'))


def test_invalid_image_creates_nothing(api, api_app, sql):
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'},
                     image=file_part(b'not an image', 'main.jpg'))
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 415
    assert sql('SELECT COUNT(*) AS n FROM crops')[0]['n'] == 0
    assert not os.path.exists(os.path.join(api_app.config['UPLOAD_FOLDER'], 'crops'))


def test_db_failure_removes_saved_image(api, api_app, monkeypatch):
    from app.models.crop import Crop

    def fail(data):
        raise RuntimeError('db down')
    monkeypatch.setattr(Crop, 'create', staticmethod(fail))
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'},
                     image=file_part(image_bytes(), 'main.png'))
    res = api.post('/api/v1/crops', data=form, content_type='multipart/form-data')
    assert res.status_code == 500
    folder = os.path.join(api_app.config['UPLOAD_FOLDER'], 'crops')
    leftover = [f for f in os.listdir(folder) if f != 'thumbs'] if os.path.isdir(folder) else []
    assert leftover == []


def test_patch_changes_only_sent_fields(api):
    crop = _create(api, notes='旧メモ', image_color='#123456')
    res = api.patch(f'/api/v1/crops/{crop["id"]}', json={'notes': '新メモ'})
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['notes'] == '新メモ'
    assert data['name'] == 'トマト'
    assert data['image_color'] == '#123456'


def test_patch_null_on_required_field_is_rejected(api):
    crop = _create(api)
    res = api.patch(f'/api/v1/crops/{crop["id"]}', json={'name': None})
    assert res.status_code == 422
    assert res.get_json()['error']['details'][0] == {'field': 'name', 'reason': '必須項目です'}


def test_patch_replaces_and_removes_image(api, api_app):
    uploads = api_app.config['UPLOAD_FOLDER']
    form = multipart({'name': 'トマト', 'crop_type': 'ナス科'}, image=file_part(image_bytes(), 'a.png'))
    crop = api.post('/api/v1/crops', data=form, content_type='multipart/form-data').get_json()['data']
    old = os.path.join(uploads, crop['image_url'].split('/static/uploads/')[1])

    form = multipart(None, image=file_part(image_bytes('JPEG'), 'b.jpg'))
    data = api.patch(f'/api/v1/crops/{crop["id"]}', data=form,
                     content_type='multipart/form-data').get_json()['data']
    new = os.path.join(uploads, data['image_url'].split('/static/uploads/')[1])
    assert not os.path.exists(old)
    assert os.path.exists(new)

    data = api.patch(f'/api/v1/crops/{crop["id"]}', json={'remove_image': True}).get_json()['data']
    assert data['image_url'] is None
    assert not os.path.exists(new)


def test_get_and_404(api):
    crop = _create(api)
    assert api.get(f'/api/v1/crops/{crop["id"]}').get_json()['data']['id'] == crop['id']
    res = api.get('/api/v1/crops/999')
    assert res.status_code == 404
    assert '作物' in res.get_json()['error']['message']
    assert api.get('/api/v1/crops/99999999999999999999').status_code == 404
    assert api.patch('/api/v1/crops/999', json={'notes': 'x'}).status_code == 404


def test_list_search_filter_and_paging(api):
    _create(api, name='ミニトマト')
    _create(api, name='なす', crop_type='ナス科')
    _create(api, name='きゅうり', crop_type='ウリ科')
    body = api.get('/api/v1/crops?q=トマト').get_json()
    assert [c['name'] for c in body['data']] == ['ミニトマト']
    assert body['meta'] == {'total': 1, 'limit': 50, 'offset': 0}
    body = api.get('/api/v1/crops?crop_type=ウリ科').get_json()
    assert [c['name'] for c in body['data']] == ['きゅうり']
    body = api.get('/api/v1/crops?limit=1&offset=1').get_json()
    assert len(body['data']) == 1
    assert body['meta']['total'] == 3


def test_list_rejects_bad_args(api):
    res = api.get('/api/v1/crops?limit=500&type=x')
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'limit', 'type'}


def test_add_extra_images(api):
    crop = _create(api)
    form = {'extra_images': [file_part(image_bytes(), 'a.png')]}
    res = api.post(f'/api/v1/crops/{crop["id"]}/images', data=form, content_type='multipart/form-data')
    assert res.status_code == 201
    assert len(res.get_json()['data']['extra_images']) == 1
    res = api.post(f'/api/v1/crops/{crop["id"]}/images', json={})
    assert res.status_code == 422


def test_audit_log_records_write_without_token(api, caplog):
    with caplog.at_level(logging.INFO, logger='app.api'):
        crop = _create(api)
    messages = [r.getMessage() for r in caplog.records if r.name == 'app.api']
    assert any(f'POST /api/v1/crops -> 201 id={crop["id"]}' in m for m in messages)
    assert not any(TOKEN in m for m in messages)
