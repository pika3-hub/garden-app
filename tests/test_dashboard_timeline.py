"""ダッシュボード: 最近の活動は記録のある直近7日分を新しい順に表示する"""
from app.database import get_db


def test_timeline_shows_latest_7_dates(app, client):
    # 2026-10-01〜10-10 の10日分。表示は 10-04〜10-10 の7日分になるはず
    with app.app_context():
        db = get_db()
        for day in range(1, 11):
            db.execute('INSERT INTO diary_entries (title, entry_date) VALUES (?, ?)',
                       (f'日記{day:02d}', f'2026-10-{day:02d}'))
        # 日付が空文字の植え付け（実データにある）も古い側として扱われ、表示されないこと
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')").lastrowid
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        db.execute("INSERT INTO plantings (location_id, crop_id, planted_date) VALUES (?, ?, '')",
                   (location_id, crop_id))
        db.commit()

    html = client.get('/').get_data(as_text=True)
    for day in range(4, 11):
        assert f'2026年10月{day}日' in html
    for day in range(1, 4):
        assert f'2026年10月{day}日' not in html
    assert '日付不明' not in html
    # 新しい日付が上
    assert html.index('2026年10月10日') < html.index('2026年10月4日')
