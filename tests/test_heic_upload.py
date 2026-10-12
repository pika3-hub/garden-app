"""HEIC/HEIF のアップロード: JPEG に変換して保存する（向き・撮影日時・色プロファイルを保つ）"""
import io
import os

from PIL import Image, ImageCms
from werkzeug.datastructures import FileStorage

from app.utils import upload
from tests.api.helpers import heic_bytes, image_bytes, requires_heif

# 先頭の ftyp ボックス（brand が heic）だけを持つバイト列。pillow_heif が無くても作れる
HEIC_HEADER = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32


def _fs(data, name):
    return FileStorage(stream=io.BytesIO(data), filename=name)


def _open_saved(app, rel):
    return Image.open(os.path.join(app.config['UPLOAD_FOLDER'], rel))


@requires_heif
def test_save_image_converts_heic_to_jpeg(app):
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    data = heic_bytes(size=(40, 20), orientation=6, taken_at='2026:10:01 09:30:00', icc=icc)
    with app.app_context():
        rel = upload.save_image(_fs(data, 'IMG_0001.HEIC'), 'growth_records')
        assert rel.startswith('growth_records/') and rel.endswith('.jpg')
        saved = _open_saved(app, rel)
        assert saved.format == 'JPEG'
        # 向き（Orientation=6: 右に90度）は画素に反映済みで、タグは残さない
        assert saved.size == (20, 40)
        assert saved.getexif().get(0x0112) in (None, 1)
        r, g, b = saved.convert('RGB').getpixel((10, 5))
        assert r > 150 and b < 100  # 元の左半分（赤）が上に来る
        assert saved.getexif().get_ifd(0x8769).get(0x9003) == '2026:10:01 09:30:00'
        assert saved.info.get('icc_profile') == icc
        thumb = os.path.join(app.config['UPLOAD_FOLDER'], 'growth_records', 'thumbs',
                             os.path.basename(rel))
        assert os.path.exists(thumb)


@requires_heif
def test_save_image_detects_heic_by_content(app):
    with app.app_context():
        rel = upload.save_image(_fs(heic_bytes(), 'photo.jpg'), 'photo_pool')
        assert rel.endswith('.jpg')
        assert _open_saved(app, rel).format == 'JPEG'


def test_save_image_rejects_heic_name_without_heic_content(app):
    with app.app_context():
        assert upload.save_image(_fs(image_bytes('PNG'), 'IMG.HEIC'), 'crops') is None


def test_save_image_skips_heic_when_library_unavailable(app, monkeypatch):
    monkeypatch.setattr(upload, 'heif_supported', lambda: False)
    with app.app_context():
        assert upload.save_image(_fs(HEIC_HEADER, 'IMG.HEIC'), 'crops') is None


@requires_heif
def test_photo_pool_web_upload_accepts_heic(app, client):
    res = client.post('/photo_pool/upload',
                      data={'images': [(io.BytesIO(heic_bytes()), 'IMG_0002.HEIC')]},
                      content_type='multipart/form-data')
    assert res.status_code in (200, 302)
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'photo_pool')
    names = [n for n in os.listdir(folder) if n != 'thumbs']
    assert len(names) == 1 and names[0].endswith('.jpg')
