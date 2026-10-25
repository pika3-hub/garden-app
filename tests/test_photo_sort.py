"""写真プールの振り分け画面: 表示・並び順・スキップ・終了"""
import re
from datetime import date

from app.database import get_db


def _photo(db, name, taken_at=None, created_at='2026-10-25 08:00:00'):
    return db.execute(
        'INSERT INTO photo_pool (image_path, taken_at, created_at) VALUES (?, ?, ?)',
        (f'photo_pool/{name}.jpg', taken_at, created_at)).lastrowid


def _shown_ids(html):
    """サムネイル列に出た写真 ID（表示順）"""
    return [int(x) for x in re.findall(r'data-sort-photo-id="(\d+)"', html)]


def test_sort_orders_by_taken_at_and_skips_missing(app, client):
    with app.app_context():
        db = get_db()
        a = _photo(db, 'a', '2026-10-25 09:00:00')
        b = _photo(db, 'b', '2026-10-24 17:00:00')
        c = _photo(db, 'c', None, created_at='2026-10-25 07:00:00')
        db.commit()

    res = client.get(f'/photo_pool/sort/?ids={a},{c},999,{b}')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert _shown_ids(html) == [b, a, c]
    assert 'photo_pool/b.jpg' in html  # 最初は一番古い写真
    assert f'ids={b},{a},{c}' in html  # 以降の URL は並べ直し済み・存在しない ID なし
    assert '999' not in re.findall(r'ids=([\d,]+)', html)[0].split(',')


def test_pos_shows_that_photo_and_done_marks(app, client):
    with app.app_context():
        db = get_db()
        a = _photo(db, 'a', '2026-10-24 09:00:00')
        b = _photo(db, 'b', '2026-10-25 09:00:00')
        db.commit()

    html = client.get(f'/photo_pool/sort/?ids={a},{b}&pos=1&done={a}').get_data(as_text=True)
    assert 'uploads/photo_pool/b.jpg' in html
    assert re.search(rf'data-sort-photo-id="{a}"[^>]*data-done="1"', html)


def test_skip_moves_to_next(app, client):
    with app.app_context():
        db = get_db()
        a = _photo(db, 'a', '2026-10-24 09:00:00')
        b = _photo(db, 'b', '2026-10-25 09:00:00')
        db.commit()

    html = client.get(f'/photo_pool/sort/?ids={a},{b}&pos=0').get_data(as_text=True)
    assert f'href="/photo_pool/sort/?ids={a},{b}&amp;pos=1"' in html


def test_finishing_redirects_to_pool_with_count(app, client):
    with app.app_context():
        db = get_db()
        a = _photo(db, 'a', '2026-10-24 09:00:00')
        b = _photo(db, 'b', '2026-10-25 09:00:00')
        db.commit()

    res = client.get(f'/photo_pool/sort/?ids={a},{b}&pos=2&done={a},{b}')
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/photo_pool/')
    html = client.get('/photo_pool/').get_data(as_text=True)
    assert '2枚の写真を登録しました' in html


def test_no_existing_photos_redirects_to_pool(client):
    res = client.get('/photo_pool/sort/?ids=998,999')
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/photo_pool/')


def test_kind_param_selects_kind(app, client):
    with app.app_context():
        db = get_db()
        a = _photo(db, 'a', '2026-10-24 09:00:00')
        db.commit()
    html = client.get(f'/photo_pool/sort/?ids={a}&kind=harvest').get_data(as_text=True)
    assert re.search(r'<option value="harvest"[^>]*selected', html)


def test_default_date_uses_taken_at_or_today(app):
    from datetime import datetime
    from app.routes.photo_sort_routes import default_date
    assert default_date({'taken_at': datetime(2026, 10, 24, 17, 0)}) == '2026-10-24'
    assert default_date({'taken_at': None}) == date.today().isoformat()


def test_sort_url_builds_query(app):
    from app.routes.photo_sort_routes import sort_url
    with app.test_request_context():
        assert sort_url([3, 1], 1, {3}) == '/photo_pool/sort/?ids=3,1&pos=1&done=3'
        assert sort_url([3, 1], 0, set()) == '/photo_pool/sort/?ids=3,1&pos=0'


def test_photo_pool_index_has_sort_button(app, client):
    with app.app_context():
        db = get_db()
        _photo(db, 'a')
        db.commit()
    html = client.get('/photo_pool/').get_data(as_text=True)
    assert 'id="bulk-sort"' in html
    assert '/photo_pool/sort/' in html
