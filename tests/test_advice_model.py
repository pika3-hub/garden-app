import pytest

from app.database import get_db
from app.models.advice import Advice


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


def _ex(db, q, p=()):
    cur = db.execute(q, p)
    db.commit()
    return cur.lastrowid


@pytest.fixture
def ids(db):
    c = _ex(db, "INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    d = _ex(db, "INSERT INTO crops (name, crop_type) VALUES ('なす', 'ナス科')")
    v = _ex(db, "INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (c,))
    w = _ex(db, "INSERT INTO varieties (crop_id, name) VALUES (?, '桃太郎')", (c,))
    x = _ex(db, "INSERT INTO varieties (crop_id, name) VALUES (?, '千両')", (d,))
    loc = _ex(db, "INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')")
    pv = _ex(db, "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')", (loc, v))
    pw = _ex(db, "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')", (loc, w))
    pc = _ex(db, "INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')", (loc, c))
    px = _ex(db, "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')", (loc, x))
    return dict(c=c, d=d, v=v, w=w, x=x, loc=loc, pv=pv, pw=pw, pc=pc, px=px)


def _advice(title='t', on='2026-10-01', **rel):
    aid = Advice.create({'title': title, 'question': 'q', 'answer': 'a', 'advised_on': on})
    Advice.save_relations(aid, rel)
    return aid


def _ids(rows):
    return [r['id'] for r in rows]


def test_create_get_update_delete(db):
    aid = Advice.create({'title': 'タイトル', 'question': '質問', 'answer': '答え', 'advised_on': '2026-10-01'})
    a = Advice.get_by_id(aid)
    assert (a['title'], a['question'], a['answer'], str(a['advised_on'])) == ('タイトル', '質問', '答え', '2026-10-01')
    Advice.update(aid, {'title': 'タイトル', 'question': '質問', 'answer': '新しい答え', 'advised_on': '2026-10-01'})
    a = Advice.get_by_id(aid)
    assert a['answer'] == '新しい答え' and a['updated_at']
    c = _ex(db, "INSERT INTO crops (name, crop_type) VALUES ('x', 'y')")
    Advice.save_relations(aid, {'crop_ids': [str(c)]})
    Advice.delete(aid)
    assert Advice.get_by_id(aid) is None
    assert db.execute('SELECT COUNT(*) FROM advice_relations WHERE advice_id=?', (aid,)).fetchone()[0] == 0


def test_scope_planting(db, ids):
    a = _advice(location_crop_ids=[ids['pv']])
    assert _ids(Advice.get_for_entity('planting', ids['pv'])) == [a]
    assert Advice.get_for_entity('planting', ids['pw']) == []


def test_scope_variety_includes_its_plantings(db, ids):
    a1 = _advice(variety_ids=[ids['v']])
    a2 = _advice(location_crop_ids=[ids['pv']])
    a3 = _advice(variety_ids=[ids['v']], location_crop_ids=[ids['pv']])
    _advice(location_crop_ids=[ids['pw']])
    assert sorted(_ids(Advice.get_for_entity('variety', ids['v']))) == [a1, a2, a3]


def test_scope_crop_includes_varieties_and_plantings(db, ids):
    a1 = _advice(crop_ids=[ids['c']])
    a2 = _advice(variety_ids=[ids['w']])
    a3 = _advice(location_crop_ids=[ids['pc']])
    a4 = _advice(location_crop_ids=[ids['pv']])
    a5 = _advice(crop_ids=[ids['c']], variety_ids=[ids['v']], location_crop_ids=[ids['pv']])
    _advice(location_crop_ids=[ids['px']])
    assert sorted(_ids(Advice.get_for_entity('crop', ids['c']))) == [a1, a2, a3, a4, a5]


def test_scope_clause_unknown():
    with pytest.raises(ValueError):
        Advice.scope_clause('harvest')


def test_scope_order_and_via_labels(db, ids):
    old = _advice(on='2026-09-01', crop_ids=[ids['c']])
    s1 = _advice(on='2026-10-01', location_crop_ids=[ids['pv']])
    s2 = _advice(on='2026-10-01', crop_ids=[ids['c']])
    rows = Advice.get_for_entity('crop', ids['c'])
    assert _ids(rows) == [s2, s1, old]
    by = {r['id']: r for r in rows}
    assert by[s1]['via_labels'] == ['植え付け: アイコ（トマト） 南の畑']
    assert by[s2]['via_labels'] == []
    v = Advice.get_for_entity('variety', ids['v'])
    assert [r['via_labels'] for r in v] == [['植え付け: アイコ（トマト） 南の畑']]
    assert Advice.get_for_entity('planting', ids['pv'])[0]['via_labels'] == []


def test_search_keyword_matches_title_question_answer(db):
    a1 = Advice.create({'title': '追肥', 'question': 'q', 'answer': 'a', 'advised_on': '2026-10-01'})
    a2 = Advice.create({'title': 't', 'question': '追肥は?', 'answer': 'a', 'advised_on': '2026-10-02'})
    a3 = Advice.create({'title': 't', 'question': 'q', 'answer': '追肥する', 'advised_on': '2026-10-03'})
    Advice.create({'title': 't', 'question': 'q', 'answer': '100% good', 'advised_on': '2026-10-04'})
    assert _ids(Advice.search('追肥')) == [a3, a2, a1]
    assert len(Advice.search('%')) == 1


def test_get_adjacent(db):
    a = _advice(on='2026-10-01')
    b = _advice(on='2026-10-02')
    c = _advice(on='2026-10-03')
    prev, nxt = Advice.get_adjacent(b)
    assert prev['id'] == c and nxt['id'] == a
    assert Advice.get_adjacent(c)[0] is None


def test_variety_delete_promotes_relation(db, ids):
    a = _advice(variety_ids=[ids['v']])
    db.execute('DELETE FROM varieties WHERE id=?', (ids['v'],))
    db.commit()
    r = db.execute('SELECT relation_type, crop_id, variety_id FROM advice_relations WHERE advice_id=?', (a,)).fetchall()
    assert [tuple(x) for x in r] == [('crop', ids['c'], None)]
    assert _ids(Advice.get_for_entity('crop', ids['c'])) == [a]


def test_variety_delete_promotes_relation_without_duplicate(db, ids):
    a = _advice(crop_ids=[ids['c']], variety_ids=[ids['v']])
    db.execute('DELETE FROM varieties WHERE id=?', (ids['v'],))
    db.commit()
    n = db.execute('SELECT COUNT(*) FROM advice_relations WHERE advice_id=? AND crop_id=?', (a, ids['c'])).fetchone()[0]
    assert n == 1


def test_orphan_relation_hidden(db, ids):
    a = _advice(location_crop_ids=[ids['pv']])
    db.execute('DELETE FROM plantings WHERE id=?', (ids['pv'],))
    db.commit()
    assert Advice.get_relations(a)['location_crops'] == []
    assert _ids(Advice.get_all()) == [a]
