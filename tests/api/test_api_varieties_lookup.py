import pytest


@pytest.fixture
def tomato(api):
    return api.post('/api/v1/crops', json={'name': 'トマト', 'crop_type': 'ナス科',
                                           'image_color': '#FF0000'}).get_json()['data']


def _variety(api, crop_id, name='アイコ', **extra):
    res = api.post('/api/v1/varieties', json={'crop_id': crop_id, 'name': name, **extra})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['data']


def test_create_variety_inherits_appearance(api, tomato):
    data = _variety(api, tomato['id'])
    assert data['crop'] == {'id': tomato['id'], 'name': 'トマト'}
    assert data['display_name'] == 'アイコ（トマト）'
    assert data['image_color'] is None
    assert data['effective_image_color'] == '#FF0000'
    assert data['web_url'].endswith(f'/varieties/{data["id"]}')


def test_create_variety_with_unknown_crop(api):
    res = api.post('/api/v1/varieties', json={'crop_id': 999, 'name': 'アイコ'})
    assert res.status_code == 422
    reason = res.get_json()['error']['details'][0]['reason']
    assert 'ID 999 の作物は存在しません' in reason
    assert '/api/v1/lookup' in reason


def test_patch_name_keeps_inherited_fields_null(api, tomato, sql):
    variety = _variety(api, tomato['id'])
    res = api.patch(f'/api/v1/varieties/{variety["id"]}', json={'name': 'アイコ2'})
    assert res.status_code == 200
    row = sql('SELECT icon_path, image_color, image_path FROM varieties WHERE id = ?', (variety['id'],))[0]
    assert row == {'icon_path': None, 'image_color': None, 'image_path': None}


def test_patch_variety_parent(api, tomato):
    other = api.post('/api/v1/crops', json={'name': 'ミニトマト', 'crop_type': 'ナス科'}).get_json()['data']
    variety = _variety(api, tomato['id'])
    data = api.patch(f'/api/v1/varieties/{variety["id"]}', json={'crop_id': other['id']}).get_json()['data']
    assert data['crop']['name'] == 'ミニトマト'


def test_list_varieties_by_crop(api, tomato):
    other = api.post('/api/v1/crops', json={'name': 'なす', 'crop_type': 'ナス科'}).get_json()['data']
    _variety(api, tomato['id'], 'アイコ')
    _variety(api, other['id'], '千両二号')
    names = [v['name'] for v in api.get(f'/api/v1/varieties?crop_id={tomato["id"]}').get_json()['data']]
    assert names == ['アイコ']
    names = [v['name'] for v in api.get('/api/v1/varieties?q=なす').get_json()['data']]
    assert names == ['千両二号']  # 作物名でも検索できる


def test_lookup_ranks_exact_then_prefix_then_partial(api, tomato):
    api.post('/api/v1/crops', json={'name': 'ミニトマト', 'crop_type': 'ナス科'})
    _variety(api, tomato['id'], 'トマトベリー')
    body = api.get('/api/v1/lookup?q=トマト').get_json()
    assert [(i['type'], i['name']) for i in body['data']] == [
        ('crop', 'トマト'), ('variety', 'トマトベリー'), ('crop', 'ミニトマト')]
    berry = body['data'][1]
    assert berry['display_name'] == 'トマトベリー（トマト）'
    assert berry['crop_id'] == tomato['id']


def test_lookup_filters_types_and_validates(api, tomato, sql):
    sql("INSERT INTO locations (name, location_type) VALUES ('トマト棚', 'プランター')")
    body = api.get('/api/v1/lookup?q=トマト&types=location').get_json()
    assert [(i['type'], i['name']) for i in body['data']] == [('location', 'トマト棚')]
    res = api.get('/api/v1/lookup?types=plant')
    assert res.status_code == 422
    assert {d['field'] for d in res.get_json()['error']['details']} == {'q', 'types'}


@pytest.mark.parametrize('q', ['%', '_'])
def test_wildcards_are_literal(api, tomato, q):
    assert api.get(f'/api/v1/lookup?q={q}').get_json()['data'] == []
    assert api.get(f'/api/v1/crops?q={q}').get_json()['data'] == []


def test_meta(api, tomato):
    data = api.get('/api/v1/meta').get_json()['data']
    assert data['crop_types'] == ['ナス科']
    assert data['task_statuses'] == ['pending', 'in_progress', 'completed']
    assert data['planting_statuses'] == ['active', 'harvested', 'removed']
    assert data['sun_exposures'] == ['全日', '半日', '日陰']
    assert len(data['crop_icons']) > 0
    assert data['relation_keys']['cooking_records'] == ['crop_ids', 'variety_ids', 'planting_ids', 'harvest_ids']
    assert 'crops' in data['resources']
