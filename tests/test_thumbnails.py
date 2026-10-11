"""サムネイル生成: 色プロファイルの引き継ぎと、既存画像の作り直し"""
from PIL import Image, ImageCms

from app.utils.generate_thumbnails import regenerate
from app.utils.upload import make_thumbnail


def _icc_profile():
    # 中身は問わない（引き継がれるかだけを見る）。実物の写真は Display P3
    return ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()


def _save_jpeg(path, size=(1600, 1200), icc=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {'icc_profile': icc} if icc else {}
    Image.new('RGB', size, (40, 160, 60)).save(path, 'JPEG', **kwargs)


def test_make_thumbnail_keeps_icc_profile(tmp_path):
    icc = _icc_profile()
    src = tmp_path / 'growth_records' / 'a.jpeg'
    _save_jpeg(src, icc=icc)
    dest = tmp_path / 'growth_records' / 'thumbs' / 'a.jpg'

    make_thumbnail(str(src), str(dest))

    thumb = Image.open(dest)
    assert thumb.size == (800, 600)
    assert thumb.info.get('icc_profile') == icc


def test_make_thumbnail_without_profile(tmp_path):
    src = tmp_path / 'crops' / 'b.png'
    src.parent.mkdir(parents=True)
    Image.new('RGBA', (400, 300), (1, 2, 3, 128)).save(src)
    dest = tmp_path / 'crops' / 'thumbs' / 'b.jpg'

    make_thumbnail(str(src), str(dest))

    thumb = Image.open(dest)
    assert thumb.format == 'JPEG'
    assert 'icc_profile' not in thumb.info


def test_regenerate_skips_existing_unless_forced(tmp_path):
    icc = _icc_profile()
    _save_jpeg(tmp_path / 'diary' / 'c.jpeg', icc=icc)
    _save_jpeg(tmp_path / 'photo_pool' / 'd.jpg')
    # 色プロファイル無しで作られた古いサムネイル
    old_thumb = tmp_path / 'diary' / 'thumbs' / 'c.jpg'
    _save_jpeg(old_thumb, size=(800, 600))

    assert regenerate(str(tmp_path), force=False) == 1  # d だけ新規に作る
    assert 'icc_profile' not in Image.open(old_thumb).info
    assert (tmp_path / 'photo_pool' / 'thumbs' / 'd.jpg').exists()

    assert regenerate(str(tmp_path), force=True) == 2
    assert Image.open(old_thumb).info.get('icc_profile') == icc


def test_regenerate_skips_gif(tmp_path):
    gif = tmp_path / 'crops' / 'e.gif'
    gif.parent.mkdir(parents=True)
    Image.new('P', (10, 10)).save(gif)

    assert regenerate(str(tmp_path), force=True) == 0
    assert not (tmp_path / 'crops' / 'thumbs').exists()
