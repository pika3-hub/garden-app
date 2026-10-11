"""既存画像の一括サムネイル生成スクリプト

uploads/ の各フォルダ（thumbs/ を除く）の画像から thumbs/{basename}.jpg を作る。
既定では既にあるサムネイルは飛ばす。--force で全部作り直す（色プロファイルを
引き継ぐ前に作られたサムネイルの作り直しなど）。

実行: uv run python -m app.utils.generate_thumbnails [--force]
"""
import argparse
import os

from app.utils.upload import make_thumbnail

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}  # GIF はサムネイルを作らない


def regenerate(upload_folder, force=False):
    """サムネイルを作り、作った枚数を返す"""
    total = 0
    for folder in sorted(os.listdir(upload_folder)):
        folder_path = os.path.join(upload_folder, folder)
        if not os.path.isdir(folder_path):
            continue
        for filename in sorted(os.listdir(folder_path)):
            basename, ext = os.path.splitext(filename)
            if ext.lower() not in IMAGE_EXTENSIONS:
                continue
            thumb_path = os.path.join(folder_path, 'thumbs', f"{basename}.jpg")
            if os.path.exists(thumb_path) and not force:
                continue
            try:
                if make_thumbnail(os.path.join(folder_path, filename), thumb_path):
                    total += 1
            except Exception as e:
                print(f"  [ERROR] {folder}/{filename}: {e}")
    return total


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='既存画像のサムネイルを作る')
    parser.add_argument('--force', action='store_true', help='既にあるサムネイルも作り直す')
    args = parser.parse_args()
    count = regenerate(UPLOAD_FOLDER, force=args.force)
    print(f"完了: {count} 件のサムネイルを作りました（{UPLOAD_FOLDER}）")
