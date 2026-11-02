"""見取り図の背景画像: 画像のそろい方、既定の背景（soil.webp）、一覧の並び"""
import os

from PIL import Image

from app.api.choices import bg_images
from app.database import get_db
from app.models.location import Location, order_bg_images

APP_DIR = os.path.join(os.path.dirname(__file__), '..', 'app')
BG_DIR = os.path.join(APP_DIR, 'static', 'images', 'location_bg_images')
NEW_NAMES = {'soil.webp', 'ridges_3.webp', 'ridges_4.webp', 'ridges_5.webp', 'ridges_6.webp', 'weeds.webp',
             'grass_edge.webp', 'brick_bed.webp', 'wood_bed.webp', 'greenhouse.webp', 'planter_long.webp',
             'planter_round.webp', 'seedling_tray.webp'}


def test_bg_images_are_new_set():
    assert set(os.listdir(BG_DIR)) == NEW_NAMES


def test_bg_images_are_1024_square_webp():
    for name in os.listdir(BG_DIR):
        with Image.open(os.path.join(BG_DIR, name)) as im:
            assert (im.format, im.size) == ('WEBP', (1024, 1024)), name


def test_bg_image_list_starts_with_soil(app):
    with app.app_context():
        names = Location.get_bg_images()
    assert names[0] == 'soil.webp' and names[1:] == sorted(names[1:])
    assert bg_images() == names


def test_order_bg_images():
    assert order_bg_images(['b.webp', 'soil.webp', 'a.webp']) == ['soil.webp', 'a.webp', 'b.webp']
    assert order_bg_images(['b.webp', 'a.webp']) == ['a.webp', 'b.webp']


def test_default_bg_image_exists_on_location_pages(app, client):
    """背景が NULL の場所の画面は soil.webp を指す"""
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
        html = res.get_data(as_text=True)
        assert 'soil.webp' in html, url
        assert 'bg_image_default' not in html, url


def test_default_bg_image_exists_in_fullscreen_js():
    with open(os.path.join(APP_DIR, 'static', 'js', 'canvas-fullscreen.js'), encoding='utf-8') as f:
        js = f.read()
    assert "'soil.webp'" in js
    assert 'bg_image_default' not in js


def test_no_old_default_name_in_app():
    for root, _dirs, files in os.walk(APP_DIR):
        for name in files:
            if os.path.splitext(name)[1] not in {'.py', '.html', '.js', '.css'}:
                continue
            with open(os.path.join(root, name), encoding='utf-8') as f:
                assert 'bg_image_default' not in f.read(), os.path.join(root, name)
