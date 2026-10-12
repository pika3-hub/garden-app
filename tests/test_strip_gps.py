"""撮影場所（GPS）を落とす: アップロード時と、保存済み画像の一括処理"""
import io
import os
import struct

from PIL import Image, ImageChops
from werkzeug.datastructures import FileStorage

from app.utils import upload
from app.utils.strip_gps import scan, strip_jpeg_gps
from tests.api.helpers import heic_bytes, image_bytes, jpeg_bytes, requires_heif


def _fs(data, name):
    return FileStorage(stream=io.BytesIO(data), filename=name)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _exif(path):
    with Image.open(path) as image:
        return image.getexif()


def test_strip_jpeg_gps_keeps_pixels_and_other_exif(tmp_path):
    path = _write(tmp_path / 'a.jpg', jpeg_bytes(taken_at='2026:06:07 16:51:30', gps=True))
    before = Image.open(path).convert('RGB')
    before.load()

    assert strip_jpeg_gps(str(path)) is True

    exif = _exif(path)
    assert not exif.get_ifd(0x8825)
    assert 0x8825 not in exif
    assert exif.get_ifd(0x8769).get(0x9003) == '2026:06:07 16:51:30'
    after = Image.open(path).convert('RGB')
    assert ImageChops.difference(before, after).getbbox() is None
    assert strip_jpeg_gps(str(path)) is False  # 2回目は何もしない


def test_strip_jpeg_gps_dry_run_does_not_write(tmp_path):
    data = jpeg_bytes(gps=True)
    path = _write(tmp_path / 'a.jpg', data)
    assert strip_jpeg_gps(str(path), apply=False) is True
    assert path.read_bytes() == data


def test_strip_jpeg_gps_ignores_images_without_gps(tmp_path):
    no_gps = _write(tmp_path / 'a.jpg', jpeg_bytes(taken_at='2026:06:07 16:51:30'))
    png = _write(tmp_path / 'b.png', image_bytes('PNG'))
    before = no_gps.read_bytes()
    assert strip_jpeg_gps(str(no_gps)) is False
    assert strip_jpeg_gps(str(png)) is False
    assert no_gps.read_bytes() == before


def test_strip_jpeg_gps_drops_unreadable_exif(tmp_path):
    data = image_bytes('JPEG')  # EXIF なし
    broken = b'Exif\x00\x00' + b'GPS?' * 8  # TIFF ヘッダーのない EXIF
    segment = b'\xff\xe1' + struct.pack('>H', len(broken) + 2) + broken
    path = _write(tmp_path / 'a.jpg', data[:2] + segment + data[2:])

    assert strip_jpeg_gps(str(path)) is True

    assert b'Exif\x00\x00' not in path.read_bytes()
    Image.open(path).load()  # 画像としては読める


def test_save_image_strips_gps_from_jpeg(app):
    data = jpeg_bytes(taken_at='2026:06:07 16:51:30', gps=True)
    with app.app_context():
        rel = upload.save_image(_fs(data, 'IMG_0001.jpg'), 'photo_pool')
    exif = _exif(os.path.join(app.config['UPLOAD_FOLDER'], rel))
    assert not exif.get_ifd(0x8825)
    assert exif.get_ifd(0x8769).get(0x9003) == '2026:06:07 16:51:30'


@requires_heif
def test_save_image_strips_gps_from_heic(app):
    data = heic_bytes(taken_at='2026:06:07 16:51:30', gps=True)
    with app.app_context():
        rel = upload.save_image(_fs(data, 'IMG_0001.HEIC'), 'photo_pool')
    exif = _exif(os.path.join(app.config['UPLOAD_FOLDER'], rel))
    assert not exif.get_ifd(0x8825)
    assert exif.get_ifd(0x8769).get(0x9003) == '2026:06:07 16:51:30'


def _webp_with_gps(path):
    exif = Image.Exif()
    exif.get_ifd(0x8825)[1] = 'N'
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (8, 8)).save(path, 'WEBP', exif=exif.tobytes())
    return path


def test_scan_reports_then_applies(tmp_path):
    with_gps = _write(tmp_path / 'photo_pool' / 'a.jpg', jpeg_bytes(gps=True))
    _write(tmp_path / 'photo_pool' / 'b.jpg', jpeg_bytes())
    _write(tmp_path / 'photo_pool' / 'thumbs' / 'a.jpg', jpeg_bytes(gps=True))  # thumbs は見ない
    _webp_with_gps(tmp_path / 'crops' / 'c.webp')
    original = with_gps.read_bytes()

    result = scan(str(tmp_path), apply=False)
    assert result.jpeg_with_gps == ['photo_pool/a.jpg']
    assert result.other_with_gps == ['crops/c.webp']
    assert with_gps.read_bytes() == original

    scan(str(tmp_path), apply=True)
    assert not _exif(with_gps).get_ifd(0x8825)
    assert scan(str(tmp_path), apply=False).jpeg_with_gps == []
