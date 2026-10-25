"""写真プール: 写真ごとの使用先（登録したデータ）へのリンク"""
from app.database import get_db
from app.models.photo_pool import PhotoPool


def _seed(db):
    """作物・品種・場所・植え付け・栽培記録・収穫・料理・日記を1件ずつ作り、ID を返す"""
    ids = {}
    ids['crop'] = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ミニトマト', 'トマト')").lastrowid
    ids['variety'] = db.execute("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')",
                                (ids['crop'],)).lastrowid
    ids['location'] = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid
    ids['planting'] = db.execute(
        "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')",
        (ids['location'], ids['variety'])).lastrowid
    ids['planting_record'] = db.execute(
        "INSERT INTO planting_records (location_crop_id, recorded_at) VALUES (?, '2026-10-25')",
        (ids['planting'],)).lastrowid
    ids['harvest'] = db.execute(
        "INSERT INTO harvests (location_crop_id, harvest_date) VALUES (?, '2026-10-24')",
        (ids['planting'],)).lastrowid
    ids['cooking'] = db.execute(
        "INSERT INTO cooking (title, cooked_date) VALUES ('トマトのマリネ', '2026-10-25')").lastrowid
    ids['diary'] = db.execute(
        "INSERT INTO diary_entries (title, entry_date) VALUES ('秋の畑', '2026-10-25')").lastrowid
    ids['photo'] = db.execute("INSERT INTO photo_pool (image_path) VALUES ('photo_pool/p.jpg')").lastrowid
    db.commit()
    return ids


def _use(photo_id, entity_type, entity_id):
    PhotoPool.record_usage(photo_id, entity_type, entity_id, f'{entity_type}/copy.jpg')


def test_usage_links_resolve_each_type(app):
    from app.routes.photo_pool_routes import usage_url
    with app.test_request_context():
        db = get_db()
        ids = _seed(db)
        for t in ('crop', 'variety', 'location', 'planting_record', 'harvest', 'cooking', 'diary'):
            _use(ids['photo'], t, ids[t])

        links = PhotoPool.get_usage_links([ids['photo']])[ids['photo']]
        by_type = {link['entity_type']: link for link in links}

        assert by_type['crop']['label'] == 'ミニトマト'
        assert by_type['variety']['label'] == 'ミニトマト（アイコ）'
        assert by_type['location']['label'] == '南の畑'
        assert by_type['planting_record']['label'] == '栽培記録 ミニトマト（アイコ） 2026-10-25'
        assert by_type['harvest']['label'] == '収穫 ミニトマト（アイコ） 2026-10-24'
        assert by_type['cooking']['label'] == 'トマトのマリネ'
        assert by_type['diary']['label'] == '秋の畑'

        assert usage_url(by_type['crop']) == f'/crops/{ids["crop"]}'
        assert usage_url(by_type['variety']) == f'/varieties/{ids["variety"]}'
        assert usage_url(by_type['location']) == f'/locations/{ids["location"]}'
        assert usage_url(by_type['planting_record']) == f'/plantings/record/{ids["planting_record"]}'
        assert usage_url(by_type['harvest']) == f'/harvests/{ids["harvest"]}'
        assert usage_url(by_type['cooking']) == f'/cooking/{ids["cooking"]}'
        assert usage_url(by_type['diary']) == f'/diary/{ids["diary"]}'


def test_usage_link_supplement_points_to_parent(app):
    from app.routes.photo_pool_routes import usage_url
    with app.test_request_context():
        db = get_db()
        ids = _seed(db)
        sup_id = db.execute(
            "INSERT INTO supplements (entity_type, entity_id, supplement_type, content) "
            "VALUES ('diary', ?, 'image', 'supplements/s.jpg')", (ids['diary'],)).lastrowid
        db.commit()
        _use(ids['photo'], 'supplement', sup_id)

        link = PhotoPool.get_usage_links([ids['photo']])[ids['photo']][0]
        assert link['target_type'] == 'diary'
        assert link['target_id'] == ids['diary']
        assert link['label'] == '秋の畑の補足情報'
        assert usage_url(link) == f'/diary/{ids["diary"]}'


def test_usage_link_deleted_entity_has_no_url(app):
    from app.routes.photo_pool_routes import usage_url
    with app.test_request_context():
        db = get_db()
        ids = _seed(db)
        _use(ids['photo'], 'cooking', ids['cooking'])
        db.execute('DELETE FROM cooking WHERE id = ?', (ids['cooking'],))
        db.commit()

        link = PhotoPool.get_usage_links([ids['photo']])[ids['photo']][0]
        assert link['label'] is None
        assert usage_url(link) is None


def test_usage_links_empty_for_unused_photo(app):
    with app.app_context():
        ids = _seed(get_db())
        assert PhotoPool.get_usage_links([ids['photo']]) == {ids['photo']: []}
        assert PhotoPool.get_usage_links([]) == {}


def test_photo_pool_index_shows_links(app, client):
    with app.app_context():
        db = get_db()
        ids = _seed(db)
        _use(ids['photo'], 'crop', ids['crop'])
        _use(ids['photo'], 'diary', ids['diary'])
        db.execute('DELETE FROM diary_entries WHERE id = ?', (ids['diary'],))
        db.commit()

    html = client.get('/photo_pool/').get_data(as_text=True)
    assert f'href="/crops/{ids["crop"]}"' in html
    assert '削除済み' in html
