"""詳細画面の写真: 表示はサムネイル、拡大表示（lightbox）には元画像を data-full で渡す"""
import re

from app.database import get_db


def _lightbox_imgs(html):
    return re.findall(r'<img[^>]*lightbox-target[^>]*>', html, re.S)


def _assert_thumb_with_full(tag, folder, name, ext):
    assert f'src="/static/uploads/{folder}/thumbs/{name}.jpg"' in tag
    assert f'data-full="/static/uploads/{folder}/{name}.{ext}"' in tag
    # GIF などサムネイルが無い画像は元画像に戻す
    assert 'onerror="this.onerror=null; this.src=this.dataset.full"' in tag


def _create_crop(db, image_path=None):
    return db.execute(
        "INSERT INTO crops (name, crop_type, image_path) VALUES ('トマト', 'ナス科', ?)",
        (image_path,)).lastrowid


def _create_planting(db):
    crop_id = _create_crop(db)
    location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
    return db.execute(
        "INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
        (location_id, crop_id)).lastrowid


def test_planting_detail_hero_uses_thumbnail(app, client):
    with app.app_context():
        db = get_db()
        planting_id = _create_planting(db)
        db.execute(
            "INSERT INTO planting_records (location_crop_id, recorded_at, image_path)"
            " VALUES (?, '2026-06-01', 'growth_records/hero.jpeg')",
            (planting_id,))
        db.commit()

    html = client.get(f'/plantings/{planting_id}').get_data(as_text=True)
    imgs = _lightbox_imgs(html)
    assert len(imgs) == 1, '上部の写真が出ていない'
    _assert_thumb_with_full(imgs[0], 'growth_records', 'hero', 'jpeg')


def test_planting_record_detail_uses_thumbnail(app, client):
    with app.app_context():
        db = get_db()
        planting_id = _create_planting(db)
        record_id = db.execute(
            "INSERT INTO planting_records (location_crop_id, recorded_at, image_path)"
            " VALUES (?, '2026-06-01', 'growth_records/rec.png')",
            (planting_id,)).lastrowid
        db.commit()

    html = client.get(f'/plantings/record/{record_id}').get_data(as_text=True)
    imgs = _lightbox_imgs(html)
    assert len(imgs) == 1
    _assert_thumb_with_full(imgs[0], 'growth_records', 'rec', 'png')


def test_crop_detail_and_supplement_image_use_thumbnail(app, client):
    with app.app_context():
        db = get_db()
        crop_id = _create_crop(db, 'crops/c.jpg')
        db.execute(
            "INSERT INTO supplements (entity_type, entity_id, supplement_type, content, sort_order)"
            " VALUES ('crop', ?, 'image', 'supplements/s.webp', 0)",
            (crop_id,))
        db.commit()

    html = client.get(f'/crops/{crop_id}').get_data(as_text=True)
    imgs = _lightbox_imgs(html)
    assert len(imgs) == 2
    _assert_thumb_with_full(imgs[0], 'crops', 'c', 'jpg')
    _assert_thumb_with_full(imgs[1], 'supplements', 's', 'webp')
