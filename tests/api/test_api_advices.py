import pytest

from app.utils.timezone import get_jst_now


@pytest.fixture
def ids(sql):
    crop = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    variety = sql("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,))
    location = sql("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    planting = sql("INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')",
                   (location, variety))
    return {'crop': crop, 'variety': variety, 'location': location, 'planting': planting}


def post(api, **body):
    return api.post('/api/v1/advices', json={'title': 't', 'answer': 'a', **body})


def test_create_with_relations(api, ids):
    res = api.post('/api/v1/advices', json={
        'title': '2回目の追肥はいつ？', 'question': 'いつ追肥する？', 'answer': '## 目安\n- 第3花房',
        'advised_on': '2026-10-20', 'relations': {'planting_ids': [ids['planting']]}})
    assert res.status_code == 201, res.get_json()
    data = res.get_json()['data']
    assert data['relations'] == {'crop_ids': [], 'variety_ids': [], 'planting_ids': [ids['planting']]}
    assert data['advised_on'] == '2026-10-20'
    assert data['web_url'].endswith(f'/advices/{data["id"]}')
    assert 'extra_images' not in data


def test_create_defaults_advised_on_today(api):
    data = post(api).get_json()['data']
    assert data['advised_on'] == get_jst_now()[:10]


def test_create_requires_title_and_answer(api):
    for body, field in (({'answer': 'a'}, 'title'), ({'title': 't'}, 'answer')):
        res = api.post('/api/v1/advices', json=body)
        assert res.status_code == 422
        assert field in {d['field'] for d in res.get_json()['error']['details']}


def test_patch_answer_only_keeps_others(api, ids):
    created = post(api, advised_on='2026-10-20', question='q',
                   relations={'crop_ids': [ids['crop']]}).get_json()['data']
    res = api.patch(f'/api/v1/advices/{created["id"]}', json={'answer': '更新'})
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['answer'] == '更新'
    assert data['title'] == 't' and data['question'] == 'q'
    assert data['advised_on'] == '2026-10-20'
    assert data['relations']['crop_ids'] == [ids['crop']]


def test_list_filters_by_scope(api, sql, ids):
    other = sql("INSERT INTO crops (name, crop_type) VALUES ('なす', 'ナス科')")
    a = post(api, relations={'planting_ids': [ids['planting']]}).get_json()['data']['id']
    post(api, title='unrelated')
    for query in (f'variety_id={ids["variety"]}', f'crop_id={ids["crop"]}', f'planting_id={ids["planting"]}'):
        body = api.get(f'/api/v1/advices?{query}').get_json()
        assert [i['id'] for i in body['data']] == [a], query
        assert body['meta']['total'] == 1
    body = api.get(f'/api/v1/advices?crop_id={other}').get_json()
    assert body['data'] == [] and body['meta']['total'] == 0
    assert api.get('/api/v1/advices?crop_id=0').status_code == 422


def test_list_q_and_dates(api):
    post(api, title='a1', question='追肥のタイミング', advised_on='2026-10-01')
    post(api, title='a2', question='別の話', advised_on='2026-10-20')
    titles = [i['title'] for i in api.get('/api/v1/advices?q=追肥').get_json()['data']]
    assert titles == ['a1']
    titles = [i['title'] for i in api.get('/api/v1/advices?date_from=2026-10-10&date_to=2026-10-31').get_json()['data']]
    assert titles == ['a2']


def test_no_delete(api):
    assert api.delete('/api/v1/advices/1').status_code == 405


def test_meta_lists_advices(api):
    data = api.get('/api/v1/meta').get_json()['data']
    assert data['relation_keys']['advices'] == ['crop_ids', 'variety_ids', 'planting_ids']
