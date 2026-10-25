"""写真プールの振り分け画面: AI 下書き"""
import os
import re

import pytest
from PIL import Image

from app.database import get_db
from app.routes import photo_sort_routes
from app.utils.ai_notes import AiNotesError


@pytest.fixture
def setup(app):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'photo_pool')
    os.makedirs(os.path.join(folder, 'thumbs'), exist_ok=True)
    Image.new('RGB', (40, 30), 'green').save(os.path.join(folder, 'p.png'))
    Image.new('RGB', (40, 30), 'green').save(os.path.join(folder, 'thumbs', 't.jpg'))
    with app.app_context():
        db = get_db()
        photo = db.execute("INSERT INTO photo_pool (image_path) VALUES ('photo_pool/t.jpg')").lastrowid
        photo_no_thumb = db.execute("INSERT INTO photo_pool (image_path) VALUES ('photo_pool/p.png')").lastrowid
        crop = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ミニトマト', 'トマト')").lastrowid
        location = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid
        planting = db.execute("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '2026-05-01')",
                              (location, crop)).lastrowid
        # 前回として使うのは写真のある記録だけ（10/18 はメモだけなので飛ばし、10/11 を使う）
        for d, n, img in [('2026-10-11', '第1花房が開花', 'growth_records/prev.jpg'),
                          ('2026-10-18', 'メモだけの記録', None),
                          ('2026-10-26', '未来', 'growth_records/future.jpg')]:
            db.execute('INSERT INTO planting_records (location_crop_id, recorded_at, notes, image_path) '
                       'VALUES (?, ?, ?, ?)', (planting, d, n, img))
        db.commit()
    records = os.path.join(app.config['UPLOAD_FOLDER'], 'growth_records')
    os.makedirs(os.path.join(records, 'thumbs'), exist_ok=True)
    Image.new('RGB', (40, 30), 'red').save(os.path.join(records, 'thumbs', 'prev.jpg'))
    # 元の写真 t.jpg は無くサムネイルだけある状態でも、サムネイルを送る
    return {'photo': photo, 'photo_no_thumb': photo_no_thumb, 'planting': planting, 'location': location}


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake(kind, image_bytes, context, client=None, model=None):
        calls.append({'kind': kind, 'image_bytes': image_bytes, 'context': context})
        return {'notes': '下書き'}

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    monkeypatch.setattr(photo_sort_routes, 'generate_photo_draft', fake)
    return calls


def test_ai_draft_compare_passes_previous_photo_and_notes(client, setup, captured):
    res = client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo'], 'kind': 'planting_record', 'compare': True,
        'location_crop_ids': [setup['planting']], 'date': '2026-10-25'})

    assert res.status_code == 200
    assert res.get_json() == {'ok': True, 'fields': {'notes': '下書き'}}
    ctx = captured[0]['context']
    assert ctx['date'] == '2026-10-25'
    [p] = ctx['plantings']
    assert p['label'] == 'ミニトマト／南の畑'
    assert p['previous']['date'] == '2026-10-11'
    assert p['previous']['notes'] == '第1花房が開花'
    assert p['previous']['image'][:3] == b'\xff\xd8\xff'
    assert captured[0]['image_bytes'][:3] == b'\xff\xd8\xff'


def test_ai_draft_without_compare_sends_no_previous(client, setup, captured):
    client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo'], 'kind': 'planting_record', 'compare': False,
        'location_crop_ids': [setup['planting']], 'date': '2026-10-25'})
    assert captured[0]['context']['plantings'][0]['previous'] is None


def test_ai_draft_no_photo_record_before_date(client, setup, captured):
    client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo'], 'kind': 'planting_record', 'compare': True,
        'location_crop_ids': [setup['planting']], 'date': '2026-10-05'})
    assert captured[0]['context']['plantings'][0]['previous'] is None


def test_ai_draft_harvest_never_sends_previous(client, setup, captured):
    client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo'], 'kind': 'harvest', 'compare': True,
        'location_crop_ids': [setup['planting']], 'date': '2026-10-25'})
    assert captured[0]['context']['plantings'][0]['previous'] is None


def test_compare_checkbox_only_for_planting_record(client, setup, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    html = client.get(f'/photo_pool/sort/?ids={setup["photo"]}&kind=planting_record').get_data(as_text=True)
    assert re.search(r'<input[^>]*data-ai-compare[^>]*checked', html)
    html = client.get(f'/photo_pool/sort/?ids={setup["photo"]}&kind=harvest').get_data(as_text=True)
    assert 'data-ai-compare' not in html


def test_ai_draft_makes_jpeg_when_no_thumbnail(client, setup, captured):
    client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo_no_thumb'], 'kind': 'location', 'name': '南の畑'})
    assert captured[0]['image_bytes'][:3] == b'\xff\xd8\xff'
    assert captured[0]['context']['name'] == '南の畑'


def test_ai_draft_cooking_gets_categories(app, client, setup, captured):
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO cooking (title, category, cooked_date) VALUES ('x', '副菜', '2026-10-01')")
        db.commit()
    client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo'], 'kind': 'cooking', 'date': '2026-10-25', 'related': ['ミニトマト']})
    ctx = captured[0]['context']
    assert ctx['categories'] == ['副菜']
    assert ctx['related'] == ['ミニトマト']


def test_ai_draft_requires_planting_for_record(client, setup, captured):
    res = client.post('/photo_pool/sort/ai-draft', json={
        'photo_id': setup['photo'], 'kind': 'planting_record', 'location_crop_ids': [], 'date': '2026-10-25'})
    assert res.status_code == 400
    assert res.get_json()['error'] == '先に植え付けを選んでください'
    assert captured == []


def test_ai_draft_bad_request(client, setup, captured):
    assert client.post('/photo_pool/sort/ai-draft', json={'photo_id': 999, 'kind': 'location'}).status_code == 400
    assert client.post('/photo_pool/sort/ai-draft', json={'photo_id': setup['photo'], 'kind': 'crop'}).status_code == 400
    assert client.post('/photo_pool/sort/ai-draft', data='x').status_code == 400


def test_ai_draft_without_key_returns_400(client, setup):
    res = client.post('/photo_pool/sort/ai-draft', json={'photo_id': setup['photo'], 'kind': 'location', 'name': 'x'})
    assert res.status_code == 400
    assert 'ANTHROPIC_API_KEY' in res.get_json()['error']


def test_ai_draft_error_returns_502(client, setup, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')

    def fail(*args, **kwargs):
        raise AiNotesError('混み合っています')

    monkeypatch.setattr(photo_sort_routes, 'generate_photo_draft', fail)
    res = client.post('/photo_pool/sort/ai-draft', json={'photo_id': setup['photo'], 'kind': 'location', 'name': 'x'})
    assert res.status_code == 502
    assert res.get_json() == {'ok': False, 'error': '混み合っています'}


@pytest.mark.parametrize('kind', ['location', 'planting', 'planting_record', 'harvest', 'cooking', 'diary'])
def test_ai_button_shown_with_key(client, setup, monkeypatch, kind):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    html = client.get(f'/photo_pool/sort/?ids={setup["photo"]}&kind={kind}').get_data(as_text=True)
    assert 'data-ai-draft-btn' in html


def test_ai_button_hidden_without_key(client, setup):
    html = client.get(f'/photo_pool/sort/?ids={setup["photo"]}&kind=planting_record').get_data(as_text=True)
    assert 'data-ai-draft-btn' not in html
