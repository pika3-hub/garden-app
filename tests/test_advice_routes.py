"""アドバイスの一覧・詳細・編集・削除の画面"""
from app.database import get_db
from app.models.advice import Advice
from app.models.conversation import Conversation


def _seed(app, status='active'):
    with app.app_context():
        db = get_db()
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ミニトマト', 'トマト')").lastrowid
        variety = db.execute("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,)).lastrowid
        loc = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid
        planting = db.execute(
            "INSERT INTO plantings (location_id, variety_id, planted_date, status) VALUES (?, ?, '2026-05-01', ?)",
            (loc, variety, status)).lastrowid
        db.commit()
        advice = Advice.create({'title': '追肥の時期', 'question': 'いつ？',
                                'answer': '## 目安\n- 第3花房\n<script>alert(1)</script>',
                                'advised_on': '2026-10-20'})
        Advice.save_relations(advice, {'crop_ids': [crop], 'variety_ids': [variety],
                                       'location_crop_ids': [planting]})
        return {'crop': crop, 'variety': variety, 'planting': planting, 'advice': advice}


def test_list_shows_and_searches(app, client):
    with app.app_context():
        Advice.create({'title': 'A', 'answer': '液肥を足す', 'advised_on': '2026-10-20'})
        Advice.create({'title': 'B', 'answer': '水やり', 'advised_on': '2026-10-21'})
    body = client.get('/advices/').get_data(as_text=True)
    assert 'アドバイス' in body and '液肥を足す' in body and '水やり' in body
    body = client.get('/advices/?keyword=液肥').get_data(as_text=True)
    assert '液肥を足す' in body and '水やり' not in body


def test_detail_renders_markdown_and_relations(app, client):
    ids = _seed(app)
    body = client.get(f"/advices/{ids['advice']}").get_data(as_text=True)
    assert '<h2>' in body
    assert '<script>alert(1)</script>' not in body
    assert f"/plantings/{ids['planting']}" in body


def test_detail_shows_only_created_updated_conversations(app, client):
    ids = _seed(app)
    with app.app_context():
        for hid, title, kind in (('h1', '作った会話', 'created'), ('h2', '見ただけの会話', 'viewed')):
            cid, _ = Conversation.upsert({
                'hermes_id': hid, 'source': 'matrix', 'title': title,
                'started_at': '2026-10-25 16:55:29', 'ended_at': None,
                'last_activity_at': '2026-10-25 16:56:00',
                'end_reason': None, 'parent_hermes_id': None})
            Conversation.replace_links(cid, [
                {'entity_type': 'advice', 'entity_id': ids['advice'], 'kind': kind,
                 'hermes_message_id': None}])
    body = client.get(f"/advices/{ids['advice']}").get_data(as_text=True)
    assert '作った会話' in body and '見ただけの会話' not in body


def test_update_requires_title_answer_date(app, client):
    ids = _seed(app)
    res = client.post(f"/advices/{ids['advice']}/update",
                      data={'title': '', 'answer': 'x', 'advised_on': '2026-10-20'})
    assert res.status_code == 302 and f"/advices/{ids['advice']}/edit" in res.headers['Location']
    for data in ({'title': 't', 'answer': '', 'advised_on': '2026-10-20'},
                 {'title': 't', 'answer': 'x', 'advised_on': ''}):
        res = client.post(f"/advices/{ids['advice']}/update", data=data)
        assert '/edit' in res.headers['Location']
    with app.app_context():
        assert Advice.get_by_id(ids['advice'])['title'] == '追肥の時期'


def test_update_saves_fields_and_relations(app, client):
    ids = _seed(app)
    res = client.post(f"/advices/{ids['advice']}/update", data={
        'title': '新題', 'question': '新相談', 'answer': '新回答', 'advised_on': '2026-10-22',
        'crop_ids': [str(ids['crop'])]})
    assert res.status_code == 302
    with app.app_context():
        a = Advice.get_by_id(ids['advice'])
        assert (a['title'], a['question'], a['answer'], str(a['advised_on'])) == \
            ('新題', '新相談', '新回答', '2026-10-22')
        rel = Advice.get_relations(ids['advice'])
        assert len(rel['crops']) == 1 and not rel['varieties'] and not rel['location_crops']


def test_edit_keeps_ended_planting_relation(app, client):
    ids = _seed(app, status='ended')
    body = client.get(f"/advices/{ids['advice']}/edit").get_data(as_text=True)
    assert f'data-planting-id="{ids["planting"]}"' in body


def test_edit_after_planting_deleted(app, client):
    ids = _seed(app)
    with app.app_context():
        db = get_db()
        db.execute('DELETE FROM plantings WHERE id = ?', (ids['planting'],))
        db.commit()
    assert client.get(f"/advices/{ids['advice']}").status_code == 200
    assert client.get(f"/advices/{ids['advice']}/edit").status_code == 200


def test_delete(app, client):
    ids = _seed(app)
    res = client.post(f"/advices/{ids['advice']}/delete")
    assert res.status_code == 302
    assert '(0件)' in client.get('/advices/').get_data(as_text=True)
    with app.app_context():
        assert Advice.get_by_id(ids['advice']) is None
        n = get_db().execute('SELECT COUNT(*) FROM advice_relations').fetchone()[0]
        assert n == 0


def test_conversation_detail_links_advice(app, client):
    ids = _seed(app)
    with app.app_context():
        cid, _ = Conversation.upsert({
            'hermes_id': 'h1', 'source': 'matrix', 'title': '相談',
            'started_at': '2026-10-25 16:55:29', 'ended_at': None,
            'last_activity_at': '2026-10-25 16:56:00',
            'end_reason': None, 'parent_hermes_id': None})
        Conversation.replace_links(cid, [
            {'entity_type': 'advice', 'entity_id': ids['advice'], 'kind': 'created',
             'hermes_message_id': None}])
    body = client.get(f'/conversations/{cid}').get_data(as_text=True)
    assert f"/advices/{ids['advice']}" in body and '追肥の時期' in body
