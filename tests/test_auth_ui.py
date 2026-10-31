"""ログインしていない人には、編集の入口（ボタン・フォーム）を出さない"""
import re

import pytest
from flask import url_for

from app.auth import OWNER_ONLY_GET_ENDPOINTS
from app.database import get_db
from app.models.advice import Advice
from app.models.supplement import Supplement


def _seed(app):
    """各データを1件ずつ作り、見る画面の URL の一覧を返す"""
    with app.app_context():
        db = get_db()
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ミニトマト', 'トマト')").lastrowid
        variety = db.execute("INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop,)).lastrowid
        loc = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid
        planting = db.execute(
            "INSERT INTO plantings (location_id, variety_id, planted_date) VALUES (?, ?, '2026-05-01')",
            (loc, variety)).lastrowid
        record = db.execute(
            "INSERT INTO planting_records (location_crop_id, recorded_at, notes) VALUES (?, '2026-10-25', 'メモ')",
            (planting,)).lastrowid
        harvest = db.execute(
            "INSERT INTO harvests (location_crop_id, harvest_date) VALUES (?, '2026-10-24')",
            (planting,)).lastrowid
        cooking = db.execute(
            "INSERT INTO cooking (title, cooked_date) VALUES ('トマトのマリネ', '2026-10-25')").lastrowid
        diary = db.execute(
            "INSERT INTO diary_entries (title, entry_date) VALUES ('秋の畑', '2026-10-25')").lastrowid
        task = db.execute("INSERT INTO tasks (title) VALUES ('支柱を立てる')").lastrowid
        db.execute("INSERT INTO photo_pool (image_path) VALUES ('photo_pool/p.jpg')")
        db.commit()
        advice = Advice.create({'title': '追肥の時期', 'question': 'いつ？', 'answer': '第3花房',
                                'advised_on': '2026-10-20'})
        Advice.save_relations(advice, {'crop_ids': [crop], 'variety_ids': [variety],
                                       'location_crop_ids': [planting]})
        for etype, eid in (('crop', crop), ('variety', variety), ('location', loc), ('diary', diary),
                           ('task', task), ('harvest', harvest), ('cooking', cooking)):
            Supplement.create({'entity_type': etype, 'entity_id': eid,
                               'supplement_type': 'text', 'title': '補足', 'content': '補足テキスト'})
    return {
        'crop': crop, 'variety': variety, 'location': loc, 'planting': planting, 'record': record,
        'urls': [
            '/', '/crops/', f'/crops/{crop}', '/varieties/', f'/varieties/{variety}',
            '/locations/', f'/locations/{loc}', '/plantings/', f'/plantings/{planting}',
            f'/plantings/record/{record}', '/harvests/', f'/harvests/{harvest}',
            '/cooking/', f'/cooking/{cooking}', '/diary/', f'/diary/{diary}',
            '/tasks/', f'/tasks/{task}', '/advices/', f'/advices/{advice}',
            '/settings/', '/photo_pool/', '/calendar/', '/conversations/',
        ],
    }


def _owner_only_paths(app):
    """編集画面への href の目印（例 /crops/1/edit）を、ダミーの ID で作った正規表現にして返す"""
    patterns = []
    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            if rule.endpoint in OWNER_ONLY_GET_ENDPOINTS and 'GET' in rule.methods:
                path = url_for(rule.endpoint, **{a: 987654 for a in rule.arguments})
                patterns.append(re.escape(path).replace('987654', r'\d+'))
    return patterns


def test_anonymous_sees_no_edit_controls(app, anon_client):
    seeded = _seed(app)
    patterns = _owner_only_paths(app)
    assert patterns
    problems = []
    for url in seeded['urls']:
        res = anon_client.get(url)
        assert res.status_code == 200, url
        body = res.get_data(as_text=True)
        if re.search(r'method\s*=\s*["\']?post', body, re.I):
            problems.append(f'{url}: POST フォームがある')
        for p in patterns:
            m = re.search(r'href\s*=\s*["\'][^"\']*?' + p + r'(?:[?#][^"\']*)?["\']', body)
            if m:
                problems.append(f'{url}: 編集画面へのリンク {m.group(0)}')
    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('kind', ['crop', 'location', 'planting'])
def test_owner_sees_edit_controls(app, client, kind):
    seeded = _seed(app)
    body = client.get({
        'crop': f"/crops/{seeded['crop']}",
        'location': f"/locations/{seeded['location']}",
        'planting': f"/plantings/{seeded['planting']}",
    }[kind]).get_data(as_text=True)
    expect = {
        'crop': f"/crops/{seeded['crop']}/edit",
        'location': f"/locations/{seeded['location']}/edit",
        'planting': f"/plantings/{seeded['planting']}/edit",
    }[kind]
    assert expect in body
    assert 'method="post"' in body.lower()


def test_anonymous_keeps_viewing_controls(app, anon_client):
    seeded = _seed(app)
    body = anon_client.get(f"/crops/{seeded['crop']}").get_data(as_text=True)
    assert 'ログイン' in body
    assert 'ログアウト' not in body


def test_nav_login_logout_icons(app, client, anon_client):
    seeded = _seed(app)
    url = f"/crops/{seeded['crop']}"
    owner = client.get(url).get_data(as_text=True)
    assert 'images/icon_logout.webp' in owner
    assert 'images/icon_login.webp' not in owner
    anon = anon_client.get(url).get_data(as_text=True)
    assert 'images/icon_login.webp' in anon
    assert 'images/icon_logout.webp' not in anon
