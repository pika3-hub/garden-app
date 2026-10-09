"""リクエスト本文（JSON / multipart）の読み取り"""
import json

from flask import request

from app.api.errors import ApiError, detail, validation_error


def parse_request(file_fields=()):
    """(payload, files) を返す

    - JSON: Content-Type: application/json の本文
    - multipart: `data` パーツを JSON として読み、file_fields に挙げた名前のファイルを受け付ける
    - files は {名前: [FileStorage, ...]}（空のファイル指定は除く）
    """
    files = {name: [] for name in file_fields}
    if request.mimetype == 'multipart/form-data':
        unknown = [k for k in request.form if k != 'data'] + [k for k in request.files if k not in files]
        if unknown:
            usable = ', '.join(['data', *file_fields])
            raise validation_error([detail(k, f'未知のパーツです。使えるパーツ: {usable}') for k in unknown])
        raw = request.form.get('data', '')
        payload = _load_json(raw, 'data パーツ') if raw.strip() else {}
        for name in file_fields:
            files[name] = [f for f in request.files.getlist(name) if f and f.filename]
    elif request.mimetype == 'application/json':
        payload = _load_json(request.get_data(as_text=True), '本文')
    elif not request.get_data():
        payload = {}
    else:
        raise ApiError(400, 'bad_request', 'Content-Type は application/json か multipart/form-data にしてください')
    if not isinstance(payload, dict):
        raise ApiError(400, 'bad_request', 'JSON はオブジェクト（{...}）で送ってください')
    return payload, files


def _load_json(text, where):
    try:
        return json.loads(text)
    except ValueError as e:
        raise ApiError(400, 'bad_request', f'{where}の JSON を読み取れません: {e}')
