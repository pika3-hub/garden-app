"""スライドショー付きの一覧: カードはサムネイルを遅延読み込みし、スライドショーには元画像を渡す"""
import re

from app.database import get_db


def _create_planting(db):
    crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
    location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
    return db.execute(
        "INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
        (location_id, crop_id)).lastrowid


def _slideshow_imgs(html):
    return re.findall(r'<img[^>]*slideshow-target[^>]*>', html, re.S)


def test_planting_record_cards_use_lazy_thumbnails(app, client):
    with app.app_context():
        db = get_db()
        planting_id = _create_planting(db)
        db.execute(
            "INSERT INTO planting_records (location_crop_id, recorded_at, image_path)"
            " VALUES (?, '2026-06-01', 'growth_records/a.jpeg')",
            (planting_id,))
        db.commit()

    html = client.get(f'/plantings/{planting_id}').get_data(as_text=True)
    imgs = _slideshow_imgs(html)
    assert len(imgs) == 1, '栽培記録のカード画像が一覧に出ていない'
    tag = imgs[0]
    assert 'src="/static/uploads/growth_records/thumbs/a.jpg"' in tag
    assert 'loading="lazy"' in tag
    assert 'data-slideshow-src="/static/uploads/growth_records/a.jpeg"' in tag


def test_harvest_slideshow_uses_original_image(app, client):
    with app.app_context():
        db = get_db()
        planting_id = _create_planting(db)
        db.execute(
            "INSERT INTO harvests (location_crop_id, harvest_date, image_path) VALUES (?, '2026-07-01', 'harvests/a.png')",
            (planting_id,))
        db.commit()

    html = client.get('/harvests/').get_data(as_text=True)
    imgs = _slideshow_imgs(html)
    assert len(imgs) == 1
    assert 'data-slideshow-src="/static/uploads/harvests/a.png"' in imgs[0]
