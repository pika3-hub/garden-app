import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename):
    """許可された拡張子かチェック"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']


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
    filename = f"{uuid.uuid4().hex}.{ext}"

    # 保存先パスを構築
    upload_folder = current_app.config['UPLOAD_FOLDER']
    folder_path = os.path.join(upload_folder, folder)

    # フォルダが存在しない場合は作成
    os.makedirs(folder_path, exist_ok=True)

    # ファイルを保存
    file_path = os.path.join(folder_path, filename)
    file.save(file_path)

    # 相対パスを返す (uploads/からの相対パス)
    return f"{folder}/{filename}"


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
