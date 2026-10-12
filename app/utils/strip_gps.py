"""撮影場所（GPS）を画像から落とす

アップロード時（app.utils.upload.save_image）と、保存済み画像の一括処理で使う。
JPEG は EXIF のセグメントだけを差し替え、画像データには触れない（画質は変わらない）。
撮影日時など GPS 以外の EXIF は残す。

実行: uv run python -m app.utils.strip_gps [--apply]
    既定は GPS を含む画像を数えて表示するだけ。--apply で JPEG から GPS を外す。
    PNG / WebP に GPS があればファイル名を表示する（書き換えはしない）。
"""
import argparse
import os
import shutil
import struct
from dataclasses import dataclass, field

from PIL import Image

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
GPS_IFD = 0x8825
EXIF_IFD = 0x8769
_EXIF_HEADER = b'Exif\x00\x00'


def remove_gps(exif):
    """Image.Exif から GPS を外す。外したら True"""
    if GPS_IFD not in exif:
        return False
    exif.get_ifd(EXIF_IFD)  # 撮影日時などの ExifIFD を読み込んでおく（書き出しで落ちないように）
    del exif[GPS_IFD]
    return True


def _exif_segment(data):
    """JPEG の APP1 Exif セグメントの (開始位置, 終了位置) を返す。JPEG でない・無ければ None"""
    if data[:2] != b'\xff\xd8':
        return None
    pos = 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker in (0xD9, 0xDA):  # EOI / SOS（ここから先は画像データ）
            return None
        end = pos + 2 + struct.unpack('>H', data[pos + 2:pos + 4])[0]
        if marker == 0xE1 and data[pos + 4:pos + 10] == _EXIF_HEADER:
            return pos, end
        pos = end
    return None


def strip_jpeg_gps(path, apply=True):
    """JPEG の EXIF から GPS を外す。GPS があれば True（apply=False なら書き換えずに判定だけ）

    EXIF が壊れていて読めないときは、撮影場所を確実に消すため EXIF をまるごと外す。
    JPEG 以外のファイルは何もせず False。
    """
    with open(path, 'rb') as f:
        data = f.read()
    segment = _exif_segment(data)
    if not segment:
        return False
    start, end = segment
    try:
        if data[start + 10:start + 14] not in (b'II*\x00', b'MM\x00*'):
            raise ValueError('TIFF ヘッダーがない')
        exif = Image.Exif()
        exif.load(data[start + 4:end])
        if not remove_gps(exif):
            return False
        payload = exif.tobytes()
        replacement = b'\xff\xe1' + struct.pack('>H', len(payload) + 2) + payload
    except Exception:
        replacement = b''
    if apply:
        tmp_path = f'{path}.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(data[:start] + replacement + data[end:])
        shutil.copymode(path, tmp_path)
        os.replace(tmp_path, path)
    return True


def _has_gps(path):
    try:
        with Image.open(path) as image:
            return bool(image.getexif().get_ifd(GPS_IFD))
    except Exception:
        return False


@dataclass
class ScanResult:
    jpeg_with_gps: list = field(default_factory=list)   # GPS があった JPEG（apply なら外した）
    other_with_gps: list = field(default_factory=list)  # GPS がある PNG / WebP（書き換えない）


def scan(upload_folder, apply=False):
    """uploads/ の各フォルダ（thumbs/ を除く）を調べる。パスは uploads/ からの相対"""
    result = ScanResult()
    for folder in sorted(os.listdir(upload_folder)):
        folder_path = os.path.join(upload_folder, folder)
        if not os.path.isdir(folder_path):
            continue
        for filename in sorted(os.listdir(folder_path)):
            path = os.path.join(folder_path, filename)
            ext = os.path.splitext(filename)[1].lower()
            rel = f'{folder}/{filename}'
            if ext in ('.jpg', '.jpeg'):
                try:
                    if strip_jpeg_gps(path, apply=apply):
                        result.jpeg_with_gps.append(rel)
                except Exception as e:
                    print(f'  [ERROR] {rel}: {e}')
            elif ext in ('.png', '.webp') and _has_gps(path):
                result.other_with_gps.append(rel)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='保存済み画像から撮影場所（GPS）を外す')
    parser.add_argument('--apply', action='store_true', help='実際に書き換える（既定は数えるだけ）')
    args = parser.parse_args()
    result = scan(UPLOAD_FOLDER, apply=args.apply)
    verb = '外しました' if args.apply else 'あります（--apply で外します）'
    print(f'GPS を含む JPEG: {len(result.jpeg_with_gps)} 件 {verb}（{UPLOAD_FOLDER}）')
    for rel in result.other_with_gps:
        print(f'  [PNG/WebP に GPS あり・未処理] {rel}')
