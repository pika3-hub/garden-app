import os
import shutil
import uuid
from flask import current_app
from werkzeug.utils import secure_filename


THUMBNAIL_SIZE = (800, 600)
THUMBNAIL_QUALITY = 80


def allowed_file(filename):
    """許可された拡張子かチェック"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def _save_thumbnail(original_path, upload_folder, folder, basename):
    """オリジナルからサムネイルを生成して保存。失敗しても例外を上げない"""
    try:
        from PIL import Image, ImageOps
        img = Image.open(original_path)
        if img.format == 'GIF':
            return  # GIF はスキップ
        img = ImageOps.exif_transpose(img)
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        thumbs_dir = os.path.join(upload_folder, folder, 'thumbs')
        os.makedirs(thumbs_dir, exist_ok=True)
        thumb_path = os.path.join(thumbs_dir, f"{basename}.jpg")
        img.save(thumb_path, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
    except Exception:
        pass  # サムネイル生成失敗はサイレントに無視（オリジナルは保存済み）


def save_image(file, folder):
    """画像を保存してパスを返す

    Args:
        file: FileStorage オブジェクト
        folder: 保存先フォルダ名 ('crops', 'locations', 'diary')

    Returns:
        保存したファイルの相対パス (例: 'crops/uuid.jpg')
        保存失敗時は None
    """
    if not file or file.filename == '':
        return None

    if not allowed_file(file.filename):
        return None

    # 元のファイル名から拡張子を取得
    ext = file.filename.rsplit('.', 1)[1].lower()

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
    file.save(file_path)

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
