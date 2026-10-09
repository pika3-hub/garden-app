import pytest

from tests.api.helpers import file_part, image_bytes, multipart


@pytest.fixture
def ids(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    planting = sql("INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')",
                   (location, variety))
    harvest = sql("INSERT INTO harvests (location_crop_id, harvest_date, quantity, unit) "
                  "VALUES (?, '2026-07-01', 300, 'g')", (planting,))
    return {'crop': crop, 'variety': variety, 'location': location, 'planting': planting, 'harvest': harvest}


def test_create_diary_with_relations(api, ids):
    res = api.post('/api/v1/diary_entries', json={
        'title': '初収穫', 'entry_date': '2026-07-01', 'weather': '晴れ',
        'relations': {'crop_ids': [ids['crop']], 'variety_ids': [ids['variety']],
                      'location_ids': [ids['location']], 'planting_ids': [ids['planting']],
                      'harvest_ids': [ids['harvest'], ids['harvest']]}})
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['status'] == 'published'
    assert data['relations'] == {'crop_ids': [ids['crop']], 'variety_ids': [ids['variety']],
                                 'location_ids': [ids['location']], 'planting_ids': [ids['planting']],
                                 'harvest_ids': [ids['harvest']]}  # 重複は1件にまとめる
    names = {(i['type'], i['display_name']) for i in data['relation_items']}
    assert ('variety', 'アイコ（トマト）') in names
    assert ('planting', 'アイコ（トマト） / 南の畑（2026-05-01 植え付け）') in names
    assert ('harvest', 'アイコ（トマト） 2026-07-01 300g') in names
    assert data['web_url'].endswith(f'/diary/{data["id"]}')


def test_patch_replaces_only_sent_relation_keys(api, ids):
    diary = api.post('/api/v1/diary_entries', json={
        'title': 'a', 'entry_date': '2026-07-01',
        'relations': {'crop_ids': [ids['crop']], 'harvest_ids': [ids['harvest']]}}).get_json()['data']
    data = api.patch(f'/api/v1/diary_entries/{diary["id"]}',
                     json={'relations': {'harvest_ids': []}}).get_json()['data']
    assert data['relations']['crop_ids'] == [ids['crop']]
    assert data['relations']['harvest_ids'] == []
    data = api.patch(f'/api/v1/diary_entries/{diary["id"]}', json={'title': 'b'}).get_json()['data']
    assert data['relations']['crop_ids'] == [ids['crop']]  # relations を送らなければ変わらない


def test_relation_validation(api, ids):
    res = api.post('/api/v1/diary_entries', json={
        'title': 'a', 'entry_date': '2026-07-01',
        'relations': {'crop_ids': [999], 'plant_ids': [1], 'variety_ids': 3}})
    assert res.status_code == 422
    fields = {d['field'] for d in res.get_json()['error']['details']}
    assert fields == {'relations.crop_ids[0]', 'relations.plant_ids', 'relations.variety_ids'}


def test_cooking_has_no_location_relation(api, ids):
    res = api.post('/api/v1/cooking_records', json={
        'title': 'トマトサラダ', 'cooked_date': '2026-07-02', 'relations': {'location_ids': [ids['location']]}})
    assert res.status_code == 422
    res = api.post('/api/v1/cooking_records', json={
        'title': 'トマトサラダ', 'cooked_date': '2026-07-02', 'category': 'サラダ',
        'relations': {'harvest_ids': [ids['harvest']]}})
    assert res.status_code == 201
    assert res.get_json()['data']['web_url'].endswith('/cooking/1')


def test_task_status_and_images(api, ids):
    task = api.post('/api/v1/tasks', json={'title': '追肥', 'due_date': '2026-10-10',
                                          'relations': {'planting_ids': [ids['planting']]}}).get_json()['data']
    assert task['status'] == 'pending'
    assert 'image_url' not in task
    res = api.patch(f'/api/v1/tasks/{task["id"]}', json={'status': 'done'})
    assert res.status_code == 422
    assert api.patch(f'/api/v1/tasks/{task["id"]}', json={'status': 'completed'}).get_json()['data']['status'] == 'completed'
    form = multipart({'title': '支柱立て'}, image=file_part(image_bytes(), 'a.png'))
    assert api.post('/api/v1/tasks', data=form, content_type='multipart/form-data').status_code == 422
    form = multipart({'title': '支柱立て'}, extra_images=file_part(image_bytes(), 'a.png'))
    res = api.post('/api/v1/tasks', data=form, content_type='multipart/form-data')
    assert res.status_code == 201
    assert len(res.get_json()['data']['extra_images']) == 1


def test_lists(api, ids):
    api.post('/api/v1/diary_entries', json={'title': '芽が出た', 'entry_date': '2026-05-10'})
    api.post('/api/v1/diary_entries', json={'title': '初収穫', 'entry_date': '2026-07-01', 'content': 'おいしい'})
    titles = lambda url: [d['title'] for d in api.get(url).get_json()['data']]  # noqa: E731
    assert titles('/api/v1/diary_entries') == ['初収穫', '芽が出た']
    assert titles('/api/v1/diary_entries?q=おいしい') == ['初収穫']
    assert titles('/api/v1/diary_entries?date_to=2026-06-01') == ['芽が出た']
    api.post('/api/v1/tasks', json={'title': '追肥', 'due_date': '2026-10-10'})
    api.post('/api/v1/tasks', json={'title': '水やり', 'status': 'completed'})
    assert titles('/api/v1/tasks?status=pending') == ['追肥']
