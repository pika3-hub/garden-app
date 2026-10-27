"""作物・品種・植え付けの詳細画面の「Hermes のアドバイス」欄"""
from app.database import get_db
from app.models.advice import Advice
from app.models.conversation import Conversation


def _seed(app, answer='## 目安\n- 第3花房\n\n<script>alert(1)</script>'):
    """作物・品種・植え付けを作り、植え付けにアドバイスを1件付ける"""
    with app.app_context():
        db = get_db()
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ミニトマト', 'トマト')").lastrowid
        variety = db.execute("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,)).lastrowid
        loc = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid
        planting = db.execute(
            "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')",
            (loc, variety)).lastrowid
        other = db.execute(
            "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-02')",
            (loc, variety)).lastrowid
        db.commit()
        advice = Advice.create({'title': '追肥の時期', 'question': 'いつ？', 'answer': answer,
                                'advised_on': '2026-10-20'})
        Advice.save_relations(advice, {'location_crop_ids': [planting]})
        return {'crop': crop, 'variety': variety, 'planting': planting, 'other': other,
                'advice': advice}


def _link(app, advice_id, kind='created', hermes_id='h1'):
    with app.app_context():
        cid, _ = Conversation.upsert({
            'hermes_id': hermes_id, 'source': 'matrix', 'title': '追肥の相談',
            'started_at': '2026-10-20 10:00:00', 'ended_at': None,
            'last_activity_at': '2026-10-20 10:05:00',
            'end_reason': None, 'parent_hermes_id': None})
        Conversation.replace_links(cid, [
            {'entity_type': 'advice', 'entity_id': advice_id, 'kind': kind,
             'hermes_message_id': None}])
        return cid


def test_planting_detail_shows_advice_section(app, client):
    ids = _seed(app)
    _link(app, ids['advice'], hermes_id='h9')
    # 会話の欄も出るよう、植え付けにも会話を結び付ける
    with app.app_context():
        cid, _ = Conversation.upsert({
            'hermes_id': 'h8', 'source': 'matrix', 'title': '様子',
            'started_at': '2026-10-20 10:00:00', 'ended_at': None,
            'last_activity_at': None, 'end_reason': None, 'parent_hermes_id': None})
        Conversation.replace_links(cid, [
            {'entity_type': 'planting', 'entity_id': ids['planting'], 'kind': 'viewed',
             'hermes_message_id': None}])
    body = client.get(f'/plantings/{ids["planting"]}').get_data(as_text=True)
    assert 'Hermes のアドバイス' in body
    assert '追肥の時期' in body
    assert '2026-10-20' in body
    assert 'id="hermes-advice"' in body
    assert 'collapse show' not in body.split('id="hermes-advice"')[1].split('id="hermes-conversations"')[0]
    assert body.index('id="hermes-advice"') < body.index('id="hermes-conversations"')


def test_section_hidden_when_empty(app, client):
    ids = _seed(app)
    body = client.get(f'/plantings/{ids["other"]}').get_data(as_text=True)
    assert 'Hermes のアドバイス' not in body


def test_variety_and_crop_detail_include_children(app, client):
    ids = _seed(app)
    for url in (f'/varieties/{ids["variety"]}', f'/crops/{ids["crop"]}'):
        body = client.get(url).get_data(as_text=True)
        assert 'Hermes のアドバイス' in body
        assert '追肥の時期' in body
        assert '植え付け:' in body


def test_section_links_origin_conversation(app, client):
    ids = _seed(app)
    url = f'/plantings/{ids["planting"]}'
    body = client.get(url).get_data(as_text=True)
    assert '元の会話を見る' not in body
    assert f'/advices/{ids["advice"]}' in body
    cid = _link(app, ids['advice'])
    body = client.get(url).get_data(as_text=True)
    assert f'/conversations/{cid}' in body
    assert '元の会話を見る' in body


def test_origin_prefers_created_over_updated(app, client):
    ids = _seed(app)
    created = _link(app, ids['advice'], 'created', 'hc')
    updated = _link(app, ids['advice'], 'updated', 'hu')
    body = client.get(f'/plantings/{ids["planting"]}').get_data(as_text=True)
    assert f'/conversations/{created}' in body
    assert f'/conversations/{updated}' not in body


def test_section_renders_markdown_escaped(app, client):
    ids = _seed(app)
    body = client.get(f'/plantings/{ids["planting"]}').get_data(as_text=True)
    assert '<li>第3花房</li>' in body
    assert '<script>alert(1)</script>' not in body
    assert '&lt;script&gt;' in body
