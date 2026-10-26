"""各詳細画面の「Hermes との会話」欄"""
import pytest

from app.database import get_db
from app.models.conversation import Conversation


def _seed(app):
    """各種データを1件ずつ作り、ID を返す"""
    with app.app_context():
        db = get_db()
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
        ids['task'] = db.execute("INSERT INTO tasks (title) VALUES ('支柱を立てる')").lastrowid
        db.commit()
        return ids


def _link(app, entity_type, entity_id, kind='created'):
    with app.app_context():
        cid, _ = Conversation.upsert({
            'hermes_id': 'h1', 'source': 'matrix', 'title': 'トマトの相談',
            'started_at': '2026-10-25 16:55:29', 'ended_at': None,
            'last_activity_at': '2026-10-25 16:56:00',
            'end_reason': None, 'parent_hermes_id': None})
        Conversation.replace_links(cid, [
            {'entity_type': entity_type, 'entity_id': entity_id, 'kind': kind,
             'hermes_message_id': None}])
        return cid


_URLS = {
    'crop': '/crops/{}', 'variety': '/varieties/{}', 'location': '/locations/{}',
    'planting': '/plantings/{}', 'planting_record': '/plantings/record/{}',
    'harvest': '/harvests/{}', 'cooking': '/cooking/{}', 'diary': '/diary/{}',
    'task': '/tasks/{}',
}


@pytest.mark.parametrize('entity_type', list(_URLS))
def test_section_shows_linked_conversation(app, client, entity_type):
    ids = _seed(app)
    cid = _link(app, entity_type, ids[entity_type])
    res = client.get(_URLS[entity_type].format(ids[entity_type]))
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert 'Hermes との会話' in body
    assert 'トマトの相談' in body
    assert '作った' in body
    assert f'/conversations/{cid}' in body


def test_section_hidden_without_links(app, client):
    ids = _seed(app)
    body = client.get(f'/crops/{ids["crop"]}').get_data(as_text=True)
    assert 'Hermes との会話' not in body


def test_crop_page_excludes_variety_links(app, client):
    ids = _seed(app)
    _link(app, 'variety', ids['variety'])
    body = client.get(f'/crops/{ids["crop"]}').get_data(as_text=True)
    assert 'Hermes との会話' not in body
