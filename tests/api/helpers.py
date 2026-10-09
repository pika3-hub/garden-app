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
