"""写真プール API（/api/v1/photos）

写真を先にプールへ上げ、各リソースの作成・更新で photo_pool_id / extra_photo_pool_ids として使う。
登録に失敗しても写真はプールに残り、後で画面からも使える。
"""
import os

from flask import current_app, g, request

from app.api import bp
from app.api.errors import ApiError, detail, ok, validation_error
from app.api.images import MAX_FILES_PER_REQUEST, SavedFiles, check_image
from app.api.payload import parse_request
from app.api.resource import page_arg
from app.api.serialize import image_url, plain, web_url
from app.api.validation import SQLITE_MAX_INT, Field, validate_payload
from app.models.photo_pool import PhotoPool
from app.routes.photo_pool_routes import _extract_taken_at


def serialize_photo(photo, with_usages=False):
    data = {
        'id': photo['id'],
        'image_url': image_url(photo['image_path']),
        'original_filename': photo['original_filename'],
        'file_size': photo['file_size'],
        'taken_at': plain(photo['taken_at']),
        'notes': photo['notes'],
        'usage_count': photo['usage_count'],
        'created_at': plain(photo['created_at']),
        'web_url': web_url('/photo_pool/'),
    }
    if with_usages:
        data['usages'] = [{'entity_type': u['entity_type'], 'entity_id': u['entity_id'],
                           'created_at': plain(u['created_at'])} for u in PhotoPool.get_usages(photo['id'])]
    return data


@bp.get('/photos')
def list_photos():
    args = request.args
    errors = [detail(k, '未知の検索条件です。使える条件: unused, limit, offset')
              for k in args if k not in ('unused', 'limit', 'offset')]
    unused = args.get('unused', 'false')
    if unused not in ('true', 'false'):
        errors.append(detail('unused', 'true か false で指定してください', unused))
    limit = page_arg(args, 'limit', 50, 1, 200, errors)
    offset = page_arg(args, 'offset', 0, 0, None, errors)
    if errors:
        raise validation_error(errors)
    photos = PhotoPool.get_all()
    if unused == 'true':
        photos = [p for p in photos if p['usage_count'] == 0]
    items = [serialize_photo(p) for p in photos[offset:offset + limit]]
    return ok(items, meta={'total': len(photos), 'limit': limit, 'offset': offset})


@bp.get('/photos/<int:photo_id>')
def get_photo(photo_id):
    photo = PhotoPool.get_by_id(photo_id) if photo_id <= SQLITE_MAX_INT else None
    if not photo:
        raise ApiError(404, 'not_found',
                       f'ID {photo_id} の写真プールの写真は存在しません。GET /api/v1/photos で一覧を確認してください')
    return ok(serialize_photo(photo, with_usages=True))


@bp.post('/photos')
def upload_photos():
    payload, files = parse_request(('files',))
    values, errors = validate_payload({'notes': Field('str')}, payload, creating=True)
    uploads = files['files']
    if not uploads:
        errors.append(detail('files', '画像を1枚以上 files パーツで送ってください'))
    if len(uploads) > MAX_FILES_PER_REQUEST:
        errors.append(detail('files', f'画像は1回のリクエストで{MAX_FILES_PER_REQUEST}枚までです（{len(uploads)}枚）'))
    if errors:
        raise validation_error(errors)
    checked = [check_image(f, 'files') for f in uploads]

    created = []
    upload_folder = current_app.config['UPLOAD_FOLDER']
    with SavedFiles() as saved:
        for c in checked:
            path = saved.save_upload(c, 'photo_pool')
            full = os.path.join(upload_folder, path)
            photo_id = PhotoPool.create(image_path=path, original_filename=c.original_name,
                                        file_size=os.path.getsize(full), taken_at=_extract_taken_at(full))
            saved.keep(path)
            if values.get('notes'):
                PhotoPool.update_notes(photo_id, values['notes'])
            created.append(photo_id)
    g.api_target_id = ','.join(map(str, created))
    return ok([serialize_photo(PhotoPool.get_by_id(i)) for i in created], 201)
