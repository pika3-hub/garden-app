"""写真プールの振り分け画面: 保存"""
import os

import pytest
from PIL import Image

from app.database import get_db


@pytest.fixture
def photo(app):
    """写真プールの写真1枚（実ファイルあり）と、まだ撮っていない2枚目の ID"""
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'photo_pool')
    os.makedirs(folder, exist_ok=True)
    Image.new('RGB', (40, 30), 'green').save(os.path.join(folder, 'p.jpg'))
    with app.app_context():
        db = get_db()
        first = db.execute("INSERT INTO photo_pool (image_path, taken_at) VALUES "
                           "('photo_pool/p.jpg', '2026-10-24 09:00:00')").lastrowid
        second = db.execute("INSERT INTO photo_pool (image_path, taken_at) VALUES "
                            "('photo_pool/p.jpg', '2026-10-25 09:00:00')").lastrowid
        db.commit()
    return {'id': first, 'second': second}


@pytest.fixture
def seed(app):
    with app.app_context():
        db = get_db()
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ミニトマト', 'トマト')").lastrowid
        location = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid
        planting = db.execute("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                              (location, crop)).lastrowid
        planting2 = db.execute("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-02')",
                               (location, crop)).lastrowid
        db.commit()
    return {'crop': crop, 'location': location, 'planting': planting, 'planting2': planting2}


def _post(client, photo, kind, fields, action='next'):
    data = {'ids': f'{photo["id"]},{photo["second"]}', 'pos': '0', 'done': '',
            'photo_id': str(photo['id']), 'kind': kind, 'action': action}
    data.update(fields)
    return client.post('/photo_pool/sort/save', data=data)


def _rows(app, sql, params=()):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql, params).fetchall()]


def _usages(app, photo_id):
    return _rows(app, 'SELECT entity_type, entity_id, copied_image_path FROM photo_pool_usages '
                      'WHERE photo_pool_id = ? ORDER BY id', (photo_id,))


SINGLE_CASES = [
    ('crop', {'name': 'ピーマン', 'crop_type': 'ピーマン', 'notes': 'メモ', 'icon_path': '', 'image_color': '#4CAF50'},
     'crops', 'crops', "name = 'ピーマン'"),
    ('variety', {'crop_id': '{crop}', 'name': 'アイコ', 'notes': '', 'icon_path': '', 'image_color': ''},
     'varieties', 'varieties', "name = 'アイコ'"),
    ('location', {'name': '北のプランター', 'location_type': 'プランター', 'area_size': '', 'sun_exposure': '半日',
                  'notes': '日陰が多い'},
     'locations', 'locations', "name = '北のプランター'"),
    ('cooking', {'title': 'トマトのマリネ', 'category': '副菜', 'notes': '', 'cooked_date': '2026-10-25'},
     'cooking', 'cooking', "title = 'トマトのマリネ'"),
    ('diary', {'title': '秋の畑', 'content': '畝全体', 'entry_date': '2026-10-25', 'weather': '晴れ'},
     'diary_entries', 'diary', "title = '秋の畑'"),
]


@pytest.mark.parametrize('kind, fields, table, folder, where', SINGLE_CASES)
def test_save_creates_entity_with_copied_photo(app, client, photo, seed, kind, fields, table, folder, where):
    fields = {k: v.format(**seed) for k, v in fields.items()}
    res = _post(client, photo, kind, fields)

    rows = _rows(app, f'SELECT id, image_path FROM {table} WHERE {where}')
    assert len(rows) == 1
    image_path = rows[0]['image_path']
    assert image_path.startswith(f'{folder}/') and image_path != 'photo_pool/p.jpg'
    assert os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], image_path))
    entity_type = {'diary_entries': 'diary', 'crops': 'crop', 'varieties': 'variety',
                   'locations': 'location', 'cooking': 'cooking'}[table]
    assert _usages(app, photo['id']) == [
        {'entity_type': entity_type, 'entity_id': rows[0]['id'], 'copied_image_path': image_path}]
    assert res.status_code == 302
    assert res.headers['Location'].endswith(
        f'/photo_pool/sort/?ids={photo["id"]},{photo["second"]}&pos=1&done={photo["id"]}')


def test_save_stay_keeps_same_photo(app, client, photo, seed):
    res = _post(client, photo, 'cooking', {'title': 'サラダ', 'cooked_date': '2026-10-25'}, action='stay')
    assert res.headers['Location'].endswith(
        f'/photo_pool/sort/?ids={photo["id"]},{photo["second"]}&pos=0&done={photo["id"]}')


def test_save_validation_error_keeps_values(app, client, photo, seed):
    res = _post(client, photo, 'cooking', {'title': '', 'cooked_date': '2026-10-21', 'notes': '下書き'})
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'タイトルと調理日は必須です' in html
    assert 'value="2026-10-21"' in html
    assert '下書き' in html
    assert _rows(app, 'SELECT id FROM cooking') == []
    assert _usages(app, photo['id']) == []


def test_variety_requires_existing_crop(app, client, photo, seed):
    res = _post(client, photo, 'variety', {'crop_id': '999', 'name': 'アイコ'})
    assert res.status_code == 200
    assert _rows(app, 'SELECT id FROM varieties') == []


def test_cooking_relations_saved(app, client, photo, seed):
    _post(client, photo, 'cooking', {'title': 'マリネ', 'cooked_date': '2026-10-25',
                                     'crop_ids': str(seed['crop']),
                                     'location_crop_ids': str(seed['planting'])})
    rows = _rows(app, 'SELECT relation_type, crop_id, location_crop_id FROM cooking_relations ORDER BY id')
    assert {(r['crop_id'], r['location_crop_id']) for r in rows} == {(seed['crop'], None), (None, seed['planting'])}


def test_diary_relations_saved(app, client, photo, seed):
    _post(client, photo, 'diary', {'title': '日記', 'entry_date': '2026-10-25',
                                   'location_ids': str(seed['location'])})
    rows = _rows(app, 'SELECT location_id FROM diary_relations')
    assert [r['location_id'] for r in rows] == [seed['location']]


def test_unknown_kind_or_photo_returns_to_sort(app, client, photo, seed):
    res = _post(client, photo, 'unknown', {})
    assert res.status_code == 200
    assert '種類を選んでください' in res.get_data(as_text=True)


@pytest.mark.parametrize('kind', ['crop', 'variety', 'location', 'cooking', 'diary'])
def test_fields_render_for_kind(app, client, photo, seed, kind):
    html = client.get(f'/photo_pool/sort/?ids={photo["id"]}&kind={kind}').get_data(as_text=True)
    assert 'action="/photo_pool/sort/save"' in html
    assert 'name="action" value="next"' in html
    assert 'name="action" value="stay"' in html
