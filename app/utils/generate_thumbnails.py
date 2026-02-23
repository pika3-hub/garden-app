"""既存画像の一括サムネイル生成スクリプト
実行: uv run python app/utils/generate_thumbnails.py
"""
import os
import sqlite3
from PIL import Image, ImageOps

DB_PATH = 'instance/garden.db'
UPLOAD_FOLDER = 'app/static/uploads'
THUMBNAIL_SIZE = (800, 600)
THUMBNAIL_QUALITY = 80

TABLES = [
    ('crops', 'image_path'),
    ('locations', 'image_path'),
    ('diary_entries', 'image_path'),
    ('harvests', 'image_path'),
    ('planting_records', 'image_path'),
]


def generate_thumbnail(image_path):
    """1枚の画像からサムネイルを生成"""
    original = os.path.join(UPLOAD_FOLDER, image_path)
    if not os.path.exists(original):
        print(f"  [SKIP] ファイルなし: {original}")
        return False
    parts = image_path.split('/', 1)
    if len(parts) != 2:
        print(f"  [SKIP] パス不正: {image_path}")
        return False
    folder, filename = parts
    basename = os.path.splitext(filename)[0]
    thumbs_dir = os.path.join(UPLOAD_FOLDER, folder, 'thumbs')
    thumb_file = os.path.join(thumbs_dir, f"{basename}.jpg")
    if os.path.exists(thumb_file):
        print(f"  [SKIP] 既存あり: {thumb_file}")
        return False
    try:
        img = Image.open(original)
        if img.format == 'GIF':
            print(f"  [SKIP] GIF: {original}")
            return False
        img = ImageOps.exif_transpose(img)
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        os.makedirs(thumbs_dir, exist_ok=True)
        img.save(thumb_file, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
        print(f"  [OK] {image_path} → thumbs/{basename}.jpg")
        return True
    except Exception as e:
        print(f"  [ERROR] {image_path}: {e}")
        return False


if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    total = 0
    for table, col in TABLES:
        try:
            rows = conn.execute(
                f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
            ).fetchall()
        except sqlite3.OperationalError as e:
            print(f"\n=== {table} [SKIP] テーブルなし: {e} ===")
            continue
        print(f"\n=== {table} ({len(rows)}件) ===")
        for (path,) in rows:
            if generate_thumbnail(path):
                total += 1
    conn.close()
    print(f"\n完了: {total} 件のサムネイルを生成しました")
