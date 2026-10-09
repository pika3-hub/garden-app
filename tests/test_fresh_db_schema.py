"""新規 DB（schema.sql + 全マイグレーション）で必要な列がそろうこと

003 は crops.image_path の追加で duplicate column エラーになり（schema.sql に既にある）、
同じスクリプト内の diary_entries.image_path の追加が実行されていなかった。
"""
from app.database import get_db


def test_fresh_db_has_diary_image_path(app):
    with app.app_context():
        columns = [r['name'] for r in get_db().execute('PRAGMA table_info(diary_entries)')]
    assert 'image_path' in columns
