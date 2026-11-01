"""見取り図の背景画像: 背景を選んでいない場所の既定の背景"""
import os
import re

from app.database import get_db

BG_DIR = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'images', 'location_bg_images')
BG_NAME_RE = re.compile(r'bg_image_[A-Za-z0-9_]+\.[a-z]+')


def _bg_names(text):
    return set(BG_NAME_RE.findall(text))


def test_default_bg_image_exists_on_location_pages(app, client):
    """背景を選んでいない場所の画面が、実在する既定の背景を指す"""
    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        planting_id = db.execute('INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
                                 (location_id, crop_id)).lastrowid
        db.commit()

    for url in (f'/locations/{location_id}', f'/locations/{location_id}/canvas',
                f'/plantings/{planting_id}', f'/plantings/{planting_id}/place'):
        res = client.get(url)
        assert res.status_code == 200, url
        names = _bg_names(res.get_data(as_text=True))
        assert names, url
        for name in names:
            assert os.path.isfile(os.path.join(BG_DIR, name)), f'{url}: {name}'


def test_default_bg_image_exists_in_fullscreen_js():
    path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'js', 'canvas-fullscreen.js')
    with open(path, encoding='utf-8') as f:
        names = _bg_names(f.read())
    assert names
    for name in names:
        assert os.path.isfile(os.path.join(BG_DIR, name)), name

