"""画像アップロードの検証・保存（本体画像・追加画像・写真プール）

拡張子は信用せず Pillow で開いて実形式を判定し、保存する拡張子も実形式に合わせる。
"""
import os
import warnings
from dataclasses import dataclass, field

from flask import current_app
from PIL import Image

from app.api.errors import ApiError, detail
from app.api.validation import REF_PHOTO, check_ref_id
from app.models.photo_pool import PhotoPool
from app.models.supplement import Supplement
from app.utils.upload import copy_image, delete_image, save_image

# MPO はスマホの写真に多い複数画像入りの JPEG（先頭は通常の JPEG なので、そのまま .jpg で保存できる）
ALLOWED_FORMATS = {'JPEG': 'jpg', 'MPO': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp'}
MAX_PIXELS = 50_000_000
MAX_FILES_PER_REQUEST = 20
IMAGE_KEYS = ('photo_pool_id', 'remove_image', 'extra_photo_pool_ids')
_HEIF_BRANDS = {b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis', b'mif1', b'msf1'}


@dataclass
class CheckedFile:
    file: object         # werkzeug FileStorage
    ext: str             # 実形式の拡張子（jpg / png / gif / webp）
    original_name: str


@dataclass
class ImageInputs:
    main_file: object = None               # FileStorage → check_files 後は CheckedFile
    main_pool_photo: dict | None = None
    remove: bool = False
    extra_files: list = field(default_factory=list)
    extra_pool_photos: list = field(default_factory=list)


def _too_many_pixels(field_name, name):
    return ApiError(413, 'too_large', f'画像の画素数が多すぎます（{MAX_PIXELS:,} 画素まで）',
                    [detail(field_name, f'{name}: 画素数超過')])


def check_image(file, field_name):
    """アップロード画像を検証して CheckedFile を返す（413 / 415 の ApiError）"""
    name = file.filename
    max_mb = current_app.config['API_MAX_IMAGE_MB']
    stream = file.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size > max_mb * 1024 * 1024:
        raise ApiError(413, 'too_large', f'画像が大きすぎます（1枚 {max_mb}MB まで）',
                       [detail(field_name, f'{name}: {size / 1024 / 1024:.1f}MB')])
    head = stream.read(12)
    stream.seek(0)
    if head[4:8] == b'ftyp' and head[8:12] in _HEIF_BRANDS:
        raise ApiError(415, 'unsupported_image',
                       'HEIC/HEIF 形式は未対応です。JPEG で送ってください（Telegram では「写真」として送ると JPEG になります）',
                       [detail(field_name, f'{name}: HEIC')])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(stream) as image:
                fmt = image.format
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise _too_many_pixels(field_name, name)
                image.verify()
    except ApiError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _too_many_pixels(field_name, name)
    except Exception:
        raise ApiError(415, 'unsupported_image', '画像として読み込めないファイルです（JPEG / PNG / GIF / WebP のみ対応）',
                       [detail(field_name, f'{name}: 読み込み失敗')])
    finally:
        stream.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ApiError(415, 'unsupported_image', f'{fmt} 形式は未対応です（JPEG / PNG / GIF / WebP のみ対応）',
                       [detail(field_name, f'{name}: {fmt}')])
    return CheckedFile(file=file, ext=ALLOWED_FORMATS[fmt], original_name=name)


def _pool_photo(raw, field_name, errors):
    """写真プール ID を検証して写真の dict を返す（ファイルが消えていれば誤り）"""
    photo_id, reason = check_ref_id(REF_PHOTO, raw)
    if reason:
        errors.append(detail(field_name, reason, raw if isinstance(raw, (int, str)) else None))
        return None
    photo = PhotoPool.get_by_id(photo_id)
    full = os.path.join(current_app.config['UPLOAD_FOLDER'], photo['image_path'])
    if not os.path.exists(full):
        errors.append(detail(field_name, f'写真プール ID {photo_id} の画像ファイルが見つかりません'))
        return None
    return photo


def collect_image_inputs(payload, files, errors, res):
    """画像関連の入力を検証して ImageInputs を返す（誤りは errors に積む）"""
    inputs = ImageInputs()
    images = files.get('image', [])
    extras = files.get('extra_images', [])
    pool_id = payload.get('photo_pool_id')
    remove = payload.get('remove_image', False)
    extra_ids = payload.get('extra_photo_pool_ids')

    if not res.image_folder:
        reason = (f'{res.label}は本体画像を持ちません。追加画像（extra_images / extra_photo_pool_ids）を使ってください'
                  if res.supplement_type else f'{res.label}は画像を持ちません')
        for key, present in (('image', images), ('photo_pool_id', pool_id is not None),
                             ('remove_image', 'remove_image' in payload)):
            if present:
                errors.append(detail(key, reason))
    else:
        if len(images) > 1:
            errors.append(detail('image', 'image は1枚だけです。2枚目以降は extra_images で送ってください'))
        if not isinstance(remove, bool):
            errors.append(detail('remove_image', 'true か false で指定してください',
                                 remove if isinstance(remove, (int, str)) else None))
            remove = False
        if images and pool_id is not None:
            errors.append(detail('photo_pool_id', 'image と photo_pool_id は同時に指定できません'))
        if remove and (images or pool_id is not None):
            errors.append(detail('remove_image', '新しい画像の指定と remove_image: true は同時に使えません'))
        if pool_id is not None:
            inputs.main_pool_photo = _pool_photo(pool_id, 'photo_pool_id', errors)
        inputs.main_file = images[0] if images else None
        inputs.remove = remove

    if not res.supplement_type:
        if extras or extra_ids is not None:
            key = 'extra_images' if extras else 'extra_photo_pool_ids'
            errors.append(detail(key, f'{res.label}には追加画像を付けられません{res.extra_images_hint}'))
    else:
        inputs.extra_files = list(extras)
        if extra_ids is not None:
            if not isinstance(extra_ids, list):
                errors.append(detail('extra_photo_pool_ids', 'ID の配列で指定してください（例: [12, 13]）'))
            else:
                for i, raw in enumerate(extra_ids):
                    photo = _pool_photo(raw, f'extra_photo_pool_ids[{i}]', errors)
                    if photo:
                        inputs.extra_pool_photos.append(photo)

    total = len(images) + len(extras)
    if total > MAX_FILES_PER_REQUEST:
        errors.append(detail('extra_images', f'画像は1回のリクエストで{MAX_FILES_PER_REQUEST}枚までです（{total}枚）'))
    return inputs


def check_files(inputs):
    """ファイルの中身を検証する（項目の検証が通った後に呼ぶ）"""
    if inputs.main_file is not None:
        inputs.main_file = check_image(inputs.main_file, 'image')
    inputs.extra_files = [check_image(f, 'extra_images') for f in inputs.extra_files]


class SavedFiles:
    """このリクエストで保存した画像を記録し、DB に書き込む前に失敗したら消す

    DB に書き込んで参照されたファイルは keep() で外す（以降の失敗では消さない）。
    """

    def __init__(self):
        self.pending = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            for path in self.pending:
                delete_image(path)
        return False

    def save_upload(self, checked, folder):
        checked.file.filename = f'upload.{checked.ext}'
        path = save_image(checked.file, folder)
        if not path:
            raise ApiError(500, 'internal_error', '画像の保存に失敗しました')
        self.pending.append(path)
        return path

    def copy_pool(self, photo, folder, field_name):
        path = copy_image(photo['image_path'], folder)
        if not path:
            raise ApiError(422, 'validation_error', '入力内容に誤りがあります（1件）',
                           [detail(field_name, f'写真プール ID {photo["id"]} の画像ファイルが見つかりません')])
        self.pending.append(path)
        return path

    def keep(self, path):
        if path in self.pending:
            self.pending.remove(path)

    def keep_all(self):
        self.pending.clear()


def apply_main_image(inputs, saved, folder, current_path):
    """本体画像の新しい相対パスを返す（変更しないなら current_path）"""
    if inputs.main_file is not None:
        return saved.save_upload(inputs.main_file, folder)
    if inputs.main_pool_photo is not None:
        return saved.copy_pool(inputs.main_pool_photo, folder, 'photo_pool_id')
    if inputs.remove:
        return None
    return current_path


def finish_main_image(inputs, usage_type, entity_id, new_path, old_path):
    """DB 更新後: 写真プールの使用記録と、置き換わった旧ファイルの削除（既存画面と同じ挙動）"""
    if inputs.main_pool_photo is not None and new_path:
        PhotoPool.record_usage(inputs.main_pool_photo['id'], usage_type, entity_id, new_path)
    if old_path and old_path != new_path:
        delete_image(old_path)


def add_extra_images(inputs, saved, entity_type, entity_id):
    """追加画像を補足情報（image 型）として添付する"""
    for checked in inputs.extra_files:
        path = saved.save_upload(checked, 'supplements')
        Supplement.create({'entity_type': entity_type, 'entity_id': entity_id,
                           'supplement_type': 'image', 'title': None, 'content': path})
        saved.keep(path)
    for photo in inputs.extra_pool_photos:
        path = saved.copy_pool(photo, 'supplements', 'extra_photo_pool_ids')
        supplement_id = Supplement.create({'entity_type': entity_type, 'entity_id': entity_id,
                                           'supplement_type': 'image', 'title': None, 'content': path})
        saved.keep(path)
        PhotoPool.record_usage(photo['id'], 'supplement', supplement_id, path)
