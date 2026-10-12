import io
import json

from PIL import Image

TOKEN = 'test-token-' + 'x' * 32


def image_bytes(fmt='PNG', size=(8, 8)):
    """テスト用の小さな画像（バイト列）"""
    buf = io.BytesIO()
    Image.new('RGB', size, (200, 50, 50)).save(buf, fmt)
    return buf.getvalue()


def file_part(data, filename):
    """test_client の multipart 用ファイル指定"""
    return (io.BytesIO(data), filename)


def multipart(payload=None, **files):
    """{'data': JSON文字列, <ファイル名>: (stream, filename) or [...]} を作る"""
    form = dict(files)
    if payload is not None:
        form['data'] = json.dumps(payload, ensure_ascii=False)
    return form


def _set_gps(exif):
    gps = exif.get_ifd(0x8825)
    gps[1] = 'N'                      # GPSLatitudeRef
    gps[2] = (35.0, 40.0, 12.5)       # GPSLatitude


def jpeg_bytes(size=(40, 20), taken_at=None, gps=False, icc=None):
    """テスト用の JPEG（撮影日時・GPS・色プロファイルを任意で付ける）"""
    image = Image.new('RGB', size, (220, 30, 30))
    image.paste((30, 30, 220), (size[0] // 2, 0, size[0], size[1]))
    exif = Image.Exif()
    if taken_at:
        exif.get_ifd(0x8769)[0x9003] = taken_at  # DateTimeOriginal
    if gps:
        _set_gps(exif)
    kwargs = {'exif': exif.tobytes()}
    if icc:
        kwargs['icc_profile'] = icc
    buf = io.BytesIO()
    image.save(buf, 'JPEG', quality=90, **kwargs)
    return buf.getvalue()


def heic_bytes(size=(40, 20), orientation=None, taken_at=None, icc=None, gps=False):
    """テスト用の HEIC（pillow_heif が必要。呼ぶテストは importorskip しておく）

    左半分を赤、右半分を青にして、向きの反映を画素で確かめられるようにする。
    """
    import pillow_heif
    pillow_heif.register_heif_opener()
    image = Image.new('RGB', size, (220, 30, 30))
    image.paste((30, 30, 220), (size[0] // 2, 0, size[0], size[1]))
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if taken_at:
        exif.get_ifd(0x8769)[0x9003] = taken_at  # DateTimeOriginal
    if gps:
        _set_gps(exif)
    kwargs = {'exif': exif.tobytes()}
    if icc:
        kwargs['icc_profile'] = icc
    buf = io.BytesIO()
    image.save(buf, format='HEIF', quality=90, **kwargs)
    return buf.getvalue()
