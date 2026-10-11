"""収穫一覧: 件数が多くても初回表示が重くならないよう、サムネイルは遅延読み込みにする"""
import re

from app.database import get_db


def test_harvest_thumbnails_are_lazy_loaded(app, client):
    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        planting_id = db.execute(
            "INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
            (location_id, crop_id)).lastrowid
        db.execute(
            "INSERT INTO harvests (location_crop_id, harvest_date, image_path) VALUES (?, '2026-07-01', 'harvests/a.jpg')",
            (planting_id,))
        db.commit()

    html = client.get('/harvests/').get_data(as_text=True)
    thumbs = re.findall(r'<img[^>]*harvests/thumbs/a\.jpg[^>]*>', html, re.S)
    assert thumbs, '収穫のサムネイルが一覧に出ていない'
    assert all('loading="lazy"' in tag for tag in thumbs)
