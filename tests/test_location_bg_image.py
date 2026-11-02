"""見取り図の背景画像: 画像のそろい方、既定の背景（soil.webp）、一覧の並び"""
import os
import re

import pytest

from PIL import Image

from app.api.choices import bg_images
from app.database import get_db, run_migrations
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


def _bg_of(app, location_id):
    with app.app_context():
        return get_db().execute('SELECT bg_image FROM locations WHERE id = ?', (location_id,)).fetchone()['bg_image']


def test_create_without_bg_image_becomes_soil(app):
    with app.app_context():
        location_id = Location.create({'name': '畑', 'location_type': '畑'})
    assert _bg_of(app, location_id) == 'soil.webp'


def test_update_with_empty_bg_image_becomes_soil(app):
    with app.app_context():
        location_id = Location.create({'name': '畑', 'location_type': '畑', 'bg_image': 'weeds.webp'})
        Location.update(location_id, {'name': '畑', 'location_type': '畑', 'bg_image': ''})
    assert _bg_of(app, location_id) == 'soil.webp'


def _selected_options(html):
    return re.findall(r'class="bg-image-option selected"\s+data-value="([^"]*)"', html)


def test_form_new_preselects_soil_and_has_no_none(client):
    html = client.get('/locations/new').get_data(as_text=True)
    assert 'data-value=""' not in html
    assert 'name="bg_image" id="bg_image" value="soil.webp"' in html
    assert _selected_options(html) == ['soil.webp']


def test_form_edit_preselects_current_bg(app, client):
    with app.app_context():
        location_id = Location.create({'name': '畑', 'location_type': '畑', 'bg_image': 'weeds.webp'})
    html = client.get(f'/locations/{location_id}/edit').get_data(as_text=True)
    assert 'name="bg_image" id="bg_image" value="weeds.webp"' in html
    assert _selected_options(html) == ['weeds.webp']


def test_photo_sort_location_gets_soil(app, client):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'photo_pool')
    os.makedirs(folder, exist_ok=True)
    Image.new('RGB', (40, 30), 'green').save(os.path.join(folder, 'p.jpg'))
    with app.app_context():
        db = get_db()
        photo_id = db.execute("INSERT INTO photo_pool (image_path, taken_at) VALUES "
                              "('photo_pool/p.jpg', '2026-10-24 09:00:00')").lastrowid
        db.commit()
    client.post('/photo_pool/sort/save', data={
        'ids': str(photo_id), 'pos': '0', 'done': '', 'photo_id': str(photo_id), 'kind': 'location',
        'action': 'next', 'name': '北のプランター', 'location_type': 'プランター', 'area_size': '',
        'sun_exposure': '半日', 'notes': ''})
    with app.app_context():
        row = get_db().execute("SELECT bg_image FROM locations WHERE name = '北のプランター'").fetchone()
    assert row['bg_image'] == 'soil.webp'


def _location_with_bg(db, bg_image):
    return db.execute("INSERT INTO locations (name, location_type, bg_image) VALUES ('畑', '畑', ?)",
                      (bg_image,)).lastrowid


@pytest.mark.parametrize('old, new', [
    ('bg_image_005.webp', 'soil.webp'), ('bg_image_012.webp', 'ridges_3.webp'), ('bg_image_008.webp', 'ridges_6.webp'),
    ('bg_image_015.webp', 'weeds.webp'), ('bg_image_014.webp', 'grass_edge.webp'), ('bg_image_010.webp', 'brick_bed.webp'),
    ('bg_image_011.webp', 'greenhouse.webp'), ('bg_image_018.webp', 'planter_long.webp'),
    ('bg_image_019.webp', 'planter_round.webp'), ('bg_image_020.webp', 'seedling_tray.webp'),
    ('bg_image_001.webp', 'soil.webp'), ('bg_image_default.webp', 'soil.webp'), (None, 'soil.webp'),
])
def test_migration_renames_bg_image(app, old, new):
    with app.app_context():
        db = get_db()
        location_id = _location_with_bg(db, old)
        db.commit()
        run_migrations(app, db)
    assert _bg_of(app, location_id) == new


def test_migration_keeps_new_names(app):
    with app.app_context():
        db = get_db()
        ids = {_location_with_bg(db, name): name for name in ('weeds.webp', 'custom_field.webp')}
        db.commit()
        run_migrations(app, db)
        run_migrations(app, db)
    assert {i: _bg_of(app, i) for i in ids} == ids


def test_form_thumbnails_are_square_and_not_dimmed(client):
    html = client.get('/locations/new').get_data(as_text=True)
    assert 'width:100px;height:100px;' in html
    assert 'height:75px' not in html
    assert 'opacity' not in html.split('bg-image-option {', 1)[1].split('}', 1)[0]
