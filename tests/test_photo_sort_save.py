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


# --- 植え付けに結び付く種類（Task 5） ---

def test_planting_creates_planting_and_first_record(app, client, photo, seed):
    res = _post(client, photo, 'planting', {
        'crop_variety': f'crop:{seed["crop"]}', 'location_id': str(seed['location']),
        'planted_date': '2026-10-20', 'quantity': '3', 'planting_notes': '苗3株', 'notes': '本葉4枚'})

    plantings = _rows(app, "SELECT id, crop_id, variety_id, position_x, notes, quantity FROM plantings "
                           "WHERE planted_date = '2026-10-20'")
    assert len(plantings) == 1
    p = plantings[0]
    assert (p['crop_id'], p['variety_id'], p['position_x'], p['notes'], p['quantity']) == \
        (seed['crop'], None, None, '苗3株', 3)
    records = _rows(app, 'SELECT id, recorded_at, notes, image_path FROM planting_records WHERE location_crop_id = ?',
                    (p['id'],))
    assert len(records) == 1
    assert str(records[0]['recorded_at']) == '2026-10-20'
    assert records[0]['notes'] == '本葉4枚'
    assert records[0]['image_path'].startswith('growth_records/')
    assert _usages(app, photo['id']) == [{'entity_type': 'planting_record', 'entity_id': records[0]['id'],
                                          'copied_image_path': records[0]['image_path']}]
    assert '/place' not in res.headers['Location']
    assert '/photo_pool/sort/' in res.headers['Location']


def test_planting_with_variety(app, client, photo, seed):
    with app.app_context():
        db = get_db()
        variety = db.execute("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (seed['crop'],)).lastrowid
        db.commit()
    _post(client, photo, 'planting', {'crop_variety': f'variety:{variety}', 'location_id': str(seed['location']),
                                      'planted_date': '2026-10-20'})
    rows = _rows(app, "SELECT crop_id, variety_id FROM plantings WHERE planted_date = '2026-10-20'")
    assert rows == [{'crop_id': None, 'variety_id': variety}]


def test_planting_requires_location_and_crop(app, client, photo, seed):
    res = _post(client, photo, 'planting', {'crop_variety': '', 'location_id': str(seed['location']),
                                            'planted_date': '2026-10-20', 'notes': '下書き'})
    assert res.status_code == 200
    assert '場所と作物（または品種）は必須です' in res.get_data(as_text=True)
    assert _rows(app, "SELECT id FROM plantings WHERE planted_date = '2026-10-20'") == []


def test_planting_record_multiple_plantings_share_notes(app, client, photo, seed):
    res = client.post('/photo_pool/sort/save', data={
        'ids': str(photo['id']), 'pos': '0', 'photo_id': str(photo['id']), 'kind': 'planting_record',
        'action': 'next', 'recorded_at': '2026-10-25', 'notes': '花が咲いた',
        'location_crop_id': [str(seed['planting']), str(seed['planting2'])]})
    assert res.status_code == 302
    rows = _rows(app, 'SELECT id, location_crop_id, notes, image_path FROM planting_records ORDER BY id')
    assert [r['location_crop_id'] for r in rows] == [seed['planting'], seed['planting2']]
    assert {r['notes'] for r in rows} == {'花が咲いた'}
    assert rows[0]['image_path'] != rows[1]['image_path']
    assert [u['entity_id'] for u in _usages(app, photo['id'])] == [rows[0]['id'], rows[1]['id']]


def test_planting_record_requires_planting(app, client, photo, seed):
    res = _post(client, photo, 'planting_record', {'recorded_at': '2026-10-25', 'notes': '下書き'})
    assert res.status_code == 200
    assert '植え付けを選んでください' in res.get_data(as_text=True)
    assert _rows(app, 'SELECT id FROM planting_records') == []


def test_harvest_quantity_per_planting(app, client, photo, seed):
    a, b = seed['planting'], seed['planting2']
    client.post('/photo_pool/sort/save', data={
        'ids': str(photo['id']), 'pos': '0', 'photo_id': str(photo['id']), 'kind': 'harvest',
        'action': 'next', 'harvest_date': '2026-10-25', 'notes': '赤く熟した',
        'location_crop_id': [str(a), str(b)],
        f'quantity_{a}': '25', f'unit_{a}': '個', f'quantity_{b}': '3', f'unit_{b}': '本'})
    rows = _rows(app, 'SELECT location_crop_id, quantity, unit, notes FROM harvests ORDER BY id')
    assert rows == [
        {'location_crop_id': a, 'quantity': 25, 'unit': '個', 'notes': '赤く熟した'},
        {'location_crop_id': b, 'quantity': 3, 'unit': '本', 'notes': '赤く熟した'},
    ]
    assert len(_usages(app, photo['id'])) == 2


def test_harvest_invalid_quantity_keeps_values(app, client, photo, seed):
    a = seed['planting']
    res = client.post('/photo_pool/sort/save', data={
        'ids': str(photo['id']), 'pos': '0', 'photo_id': str(photo['id']), 'kind': 'harvest',
        'action': 'next', 'harvest_date': '2026-10-21', 'notes': '下書き',
        'location_crop_id': str(a), f'quantity_{a}': 'abc'})
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert '収穫量は数値で入力してください' in html
    assert 'value="abc"' in html and 'value="2026-10-21"' in html
    assert _rows(app, 'SELECT id FROM harvests') == []


def test_harvest_rows_render_for_selected_plantings(app, client, photo, seed):
    a = seed['planting']
    html = client.get(f'/photo_pool/sort/?ids={photo["id"]}&kind=harvest&location_crop_id={a}').get_data(as_text=True)
    assert f'name="quantity_{a}"' in html
    assert f'name="location_crop_id" value="{a}"' in html


@pytest.mark.parametrize('kind', ['planting', 'planting_record', 'harvest'])
def test_planting_kinds_render(app, client, photo, seed, kind):
    html = client.get(f'/photo_pool/sort/?ids={photo["id"]}&kind={kind}').get_data(as_text=True)
    assert 'action="/photo_pool/sort/save"' in html


# --- 最終レビューの指摘 ---

def test_missing_photo_file_is_an_error(app, client, photo, seed):
    with app.app_context():
        db = get_db()
        missing = db.execute("INSERT INTO photo_pool (image_path) VALUES ('photo_pool/missing.jpg')").lastrowid
        db.commit()
    res = client.post('/photo_pool/sort/save', data={
        'ids': str(missing), 'pos': '0', 'photo_id': str(missing), 'kind': 'cooking', 'action': 'next',
        'title': 'マリネ', 'cooked_date': '2026-10-25'})
    assert res.status_code == 200
    assert '写真のファイルが見つかりません' in res.get_data(as_text=True)
    assert _rows(app, 'SELECT id FROM cooking') == []


def test_next_position_follows_saved_photo_when_earlier_photo_deleted(app, client, photo, seed):
    with app.app_context():
        db = get_db()
        earlier = db.execute("INSERT INTO photo_pool (image_path, taken_at) VALUES "
                             "('photo_pool/p.jpg', '2026-10-01 09:00:00')").lastrowid
        db.commit()
    ids = f'{earlier},{photo["id"]},{photo["second"]}'
    with app.app_context():
        db = get_db()
        db.execute('DELETE FROM photo_pool WHERE id = ?', (earlier,))  # 別タブで削除された
        db.commit()
    res = client.post('/photo_pool/sort/save', data={
        'ids': ids, 'pos': '1', 'photo_id': str(photo['id']), 'kind': 'cooking', 'action': 'next',
        'title': 'マリネ', 'cooked_date': '2026-10-25'})
    assert res.headers['Location'].endswith(
        f'/photo_pool/sort/?ids={photo["id"]},{photo["second"]}&pos=1&done={photo["id"]}')
