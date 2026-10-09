import io
import json
import os
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from app.api import images as img
from app.api.errors import ApiError
from app.api.payload import parse_request
from tests.api.helpers import image_bytes


def _fs(data, name):
    return FileStorage(stream=io.BytesIO(data), filename=name)


# --- parse_request ---

def test_parse_json(api_app):
    with api_app.test_request_context('/x', method='POST', json={'name': 'トマト'}):
        assert parse_request() == ({'name': 'トマト'}, {})


def test_parse_multipart(api_app):
    data = {'data': json.dumps({'name': 'トマト'}),
            'image': (io.BytesIO(image_bytes()), 'a.png')}
    with api_app.test_request_context('/x', method='POST', data=data,
                                      content_type='multipart/form-data'):
        payload, files = parse_request(('image', 'extra_images'))
    assert payload == {'name': 'トマト'}
    assert len(files['image']) == 1
    assert files['extra_images'] == []


def test_parse_multipart_rejects_unknown_part(api_app):
    data = {'name': 'トマト'}  # data パーツに入れ忘れ
    with api_app.test_request_context('/x', method='POST', data=data,
                                      content_type='multipart/form-data'):
        with pytest.raises(ApiError) as e:
            parse_request(('image',))
    assert e.value.status == 422
    assert e.value.details[0]['field'] == 'name'
    assert 'data, image' in e.value.details[0]['reason']


@pytest.mark.parametrize('body, content_type', [
    ('{broken', 'application/json'),
    ('[1, 2]', 'application/json'),
    ('name=x', 'text/plain'),
])
def test_parse_rejects_bad_body(api_app, body, content_type):
    with api_app.test_request_context('/x', method='POST', data=body, content_type=content_type):
        with pytest.raises(ApiError) as e:
            parse_request()
    assert e.value.status == 400


def test_parse_empty_body(api_app):
    with api_app.test_request_context('/x', method='POST'):
        assert parse_request() == ({}, {})


# --- check_image ---

@pytest.mark.parametrize('fmt, name, ext', [
    ('PNG', 'a.png', 'png'),
    ('JPEG', 'IMG_0001.JPG', 'jpg'),
    ('PNG', 'photo.jpg', 'png'),      # 拡張子と中身が違えば中身に合わせる
    ('JPEG', 'file_123', 'jpg'),      # 拡張子なし（Telegram のファイル送信）
    ('WEBP', 'a.webp', 'webp'),
    ('GIF', 'a.gif', 'gif'),
])
def test_check_image_detects_real_format(api_app, fmt, name, ext):
    with api_app.app_context():
        checked = img.check_image(_fs(image_bytes(fmt), name), 'image')
    assert checked.ext == ext
    assert checked.original_name == name


def test_check_image_accepts_mpo(api_app):
    """スマホの写真に多い MPO（複数画像入りの JPEG）は JPEG として受け付ける"""
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), 'green').save(buf, 'MPO', save_all=True,
                                           append_images=[Image.new('RGB', (4, 4))])
    with Image.open(io.BytesIO(buf.getvalue())) as probe:
        assert probe.format == 'MPO'
    with api_app.app_context():
        checked = img.check_image(_fs(buf.getvalue(), 'test.jpeg'), 'image')
    assert checked.ext == 'jpg'


def test_check_image_rejects_non_image(api_app):
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(b'hello, not an image', 'a.jpg'), 'image')
    assert e.value.status == 415


def test_check_image_rejects_heic(api_app):
    heic = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(heic, 'IMG.HEIC'), 'image')
    assert e.value.status == 415
    assert 'HEIC' in e.value.message


def test_check_image_rejects_large_file(api_app):
    big = image_bytes() + b'\0' * (1024 * 1024)  # テスト設定の上限は 1MB
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(big, 'a.png'), 'image')
    assert e.value.status == 413


def test_check_image_rejects_too_many_pixels(api_app, monkeypatch):
    monkeypatch.setattr(img, 'MAX_PIXELS', 10)
    with api_app.app_context(), pytest.raises(ApiError) as e:
        img.check_image(_fs(image_bytes(size=(8, 8)), 'a.png'), 'image')
    assert e.value.status == 413


# --- collect_image_inputs ---

RES_WITH_IMAGE = SimpleNamespace(image_folder='crops', supplement_type='crop',
                                 label='作物', extra_images_hint='')
RES_RECORD = SimpleNamespace(image_folder='growth_records', supplement_type=None,
                             label='栽培記録', extra_images_hint='。複数枚の写真は栽培記録を複数件作成してください')
RES_TASK = SimpleNamespace(image_folder=None, supplement_type='task',
                           label='タスク', extra_images_hint='')


def _collect(api_app, res, payload, files=None):
    errors = []
    with api_app.app_context():
        inputs = img.collect_image_inputs(payload, files or {}, errors, res)
    return inputs, errors


def test_collect_rejects_two_main_images(api_app):
    files = {'image': [_fs(image_bytes(), 'a.png'), _fs(image_bytes(), 'b.png')]}
    _, errors = _collect(api_app, RES_WITH_IMAGE, {}, files)
    assert 'extra_images' in errors[0]['reason']


def test_collect_rejects_remove_with_new_image(api_app):
    files = {'image': [_fs(image_bytes(), 'a.png')]}
    _, errors = _collect(api_app, RES_WITH_IMAGE, {'remove_image': True}, files)
    assert errors[0]['field'] == 'remove_image'


def test_collect_rejects_unknown_photo_pool_id(api_app):
    _, errors = _collect(api_app, RES_WITH_IMAGE, {'photo_pool_id': 99})
    assert errors[0]['field'] == 'photo_pool_id'
    assert '存在しません' in errors[0]['reason']


def test_collect_rejects_extras_for_planting_record(api_app):
    files = {'extra_images': [_fs(image_bytes(), 'a.png')]}
    _, errors = _collect(api_app, RES_RECORD, {}, files)
    assert '複数件作成' in errors[0]['reason']


def test_collect_rejects_main_image_for_task(api_app):
    files = {'image': [_fs(image_bytes(), 'a.png')]}
    _, errors = _collect(api_app, RES_TASK, {}, files)
    assert errors[0]['field'] == 'image'
    assert 'extra_images' in errors[0]['reason']


def test_collect_limits_file_count(api_app, monkeypatch):
    monkeypatch.setattr(img, 'MAX_FILES_PER_REQUEST', 2)
    files = {'extra_images': [_fs(image_bytes(), f'{i}.png') for i in range(3)]}
    _, errors = _collect(api_app, RES_WITH_IMAGE, {}, files)
    assert '2枚まで' in errors[0]['reason']


# --- SavedFiles ---

def test_saved_files_removes_pending_on_error(api_app):
    with api_app.app_context():
        checked = img.check_image(_fs(image_bytes(), 'a.png'), 'image')
        with pytest.raises(RuntimeError):
            with img.SavedFiles() as saved:
                path = saved.save_upload(checked, 'crops')
                full = os.path.join(api_app.config['UPLOAD_FOLDER'], path)
                assert os.path.exists(full)
                raise RuntimeError('DB 書き込み失敗')
        assert not os.path.exists(full)


def test_saved_files_keeps_committed_files(api_app):
    with api_app.app_context():
        checked = img.check_image(_fs(image_bytes(), 'a.png'), 'image')
        with pytest.raises(RuntimeError):
            with img.SavedFiles() as saved:
                path = saved.save_upload(checked, 'crops')
                saved.keep(path)
                raise RuntimeError('後続の処理で失敗')
        assert os.path.exists(os.path.join(api_app.config['UPLOAD_FOLDER'], path))
        assert path.endswith('.png')
