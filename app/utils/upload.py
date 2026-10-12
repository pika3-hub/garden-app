import functools
import os
import shutil
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

from app.utils.strip_gps import remove_gps, strip_jpeg_gps


THUMBNAIL_SIZE = (800, 600)
THUMBNAIL_QUALITY = 80
HEIF_JPEG_QUALITY = 90
# ISO BMFF の ftyp ボックスの brand（iPhone は heic、Android は mif1 など）
HEIF_BRANDS = {b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis', b'mif1', b'msf1'}


def allowed_file(filename):
    """許可された拡張子かチェック"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def is_heif(stream):
    """ファイルの中身（先頭12バイト）が HEIC/HEIF か。拡張子は見ない"""
    stream.seek(0)
    head = stream.read(12)
    stream.seek(0)
    return head[4:8] == b'ftyp' and head[8:12] in HEIF_BRANDS


@functools.cache
def heif_supported():
    """HEIC を読めるか。読めれば Pillow に HEIF の読み込みを登録する

    pillow_heif のネイティブ DLL は環境によって読み込めない（Windows の Smart App Control
    に止められたことがある）。その場合もアプリは起動させ、HEIC だけを受け付けない。
    """
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        return False
    return True


def _save_heif_as_jpeg(stream, path):
    """HEIC を JPEG で保存する。向きは画素に反映し、撮影場所（GPS）以外の EXIF と色プロファイルは残す"""
    from PIL import Image, ImageOps
    with Image.open(stream) as img:
        icc_profile = img.info.get('icc_profile')
        img = ImageOps.exif_transpose(img)  # Orientation タグも取り除かれる
    if img.mode != 'RGB':
        img = img.convert('RGB')
    save_kwargs = {}
    exif = img.getexif()
    remove_gps(exif)
    if exif:
        save_kwargs['exif'] = exif
    if icc_profile:
        save_kwargs['icc_profile'] = icc_profile
    img.save(path, format='JPEG', quality=HEIF_JPEG_QUALITY, **save_kwargs)


def make_thumbnail(original_path, thumb_path):
    """オリジナルからサムネイル（JPEG）を作る。作ったら True、GIF は作らず False

    色プロファイル（iPhone の写真は Display P3）は引き継ぐ。捨てるとブラウザが
    sRGB として表示し、元画像より色が薄く見える。
    """
    from PIL import Image, ImageOps
    img = Image.open(original_path)
    if img.format == 'GIF':
        return False
    icc_profile = img.info.get('icc_profile')
    img = ImageOps.exif_transpose(img)
    img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    save_kwargs = {'icc_profile': icc_profile} if icc_profile else {}
    img.save(thumb_path, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True, **save_kwargs)
    return True


def _save_thumbnail(original_path, upload_folder, folder, basename):
    """オリジナルからサムネイルを生成して保存。失敗しても例外を上げない"""
    try:
        thumb_path = os.path.join(upload_folder, folder, 'thumbs', f"{basename}.jpg")
        make_thumbnail(original_path, thumb_path)
    except Exception:
        pass  # サムネイル生成失敗はサイレントに無視（オリジナルは保存済み）


def save_image(file, folder):
    """画像を保存してパスを返す

    HEIC/HEIF は中身で判定し、JPEG に変換して .jpg で保存する。
    撮影場所（GPS）は保存しない（JPEG・HEIC。画質は変えない）。

    Args:
        file: FileStorage オブジェクト
        folder: 保存先フォルダ名 ('crops', 'locations', 'diary')

    Returns:
        保存したファイルの相対パス (例: 'crops/uuid.jpg')
        保存失敗時は None
    """
    if not file or file.filename == '':
        return None

    heif = is_heif(file.stream)
    if heif:
        if not heif_supported():
            return None
        ext = 'jpg'
    elif allowed_file(file.filename):
        # 元のファイル名から拡張子を取得
        ext = file.filename.rsplit('.', 1)[1].lower()
    else:
        return None

    # UUIDでユニークなファイル名を生成
    uuid_basename = uuid.uuid4().hex
    filename = f"{uuid_basename}.{ext}"

    # 保存先パスを構築
    upload_folder = current_app.config['UPLOAD_FOLDER']
    folder_path = os.path.join(upload_folder, folder)

    # フォルダが存在しない場合は作成
    os.makedirs(folder_path, exist_ok=True)

    # ファイルを保存
    file_path = os.path.join(folder_path, filename)
    try:
        if heif:
            _save_heif_as_jpeg(file.stream, file_path)
        else:
            file.save(file_path)
            strip_jpeg_gps(file_path)
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        return None

    # サムネイルを生成
    _save_thumbnail(file_path, upload_folder, folder, uuid_basename)

    # 相対パスを返す (uploads/からの相対パス)
    return f"{folder}/{filename}"


def copy_image(source_path, dest_folder):
    """既存の画像を別フォルダへコピーして新しい相対パスを返す

    写真プール機能で、プールの画像を各エンティティ用フォルダへ複製するために使う。
    新しいUUIDでファイル名を付け直し、サムネイルも再生成する。

    Args:
        source_path: コピー元の相対パス (例: 'photo_pool/uuid.jpg')
        dest_folder: コピー先フォルダ名 (例: 'diary', 'crops')

    Returns:
        コピー先の相対パス (例: 'diary/newuuid.jpg')
        失敗時は None
    """
    if not source_path:
        return None

    upload_folder = current_app.config['UPLOAD_FOLDER']
    src_full = os.path.join(upload_folder, source_path)
    if not os.path.exists(src_full):
        return None

    ext = source_path.rsplit('.', 1)[1].lower() if '.' in source_path else 'jpg'
    uuid_basename = uuid.uuid4().hex
    filename = f"{uuid_basename}.{ext}"

    dest_dir = os.path.join(upload_folder, dest_folder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_full = os.path.join(dest_dir, filename)

    shutil.copy2(src_full, dest_full)
    _save_thumbnail(dest_full, upload_folder, dest_folder, uuid_basename)

    return f"{dest_folder}/{filename}"


def delete_image(image_path):
    """画像を削除

    Args:
        image_path: 相対パス (例: 'crops/uuid.jpg')
    """
    if not image_path:
        return

    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, image_path)

    if os.path.exists(file_path):
        os.remove(file_path)

    # サムネイルも削除
    parts = image_path.split('/', 1)
    if len(parts) == 2:
        folder, filename = parts
        basename = os.path.splitext(filename)[0]
        thumb_path = os.path.join(upload_folder, folder, 'thumbs', f"{basename}.jpg")
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
