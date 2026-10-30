import re

from app.database import get_db
from app.models.conversation import Conversation
from app.models.hermes_chat import HermesChat, make_title


def test_get_or_create_active_is_stable(app):
    with app.app_context():
        a = HermesChat.get_or_create_active('planting', 12)
        b = HermesChat.get_or_create_active('planting', 12)
        assert a['session_id'] == b['session_id']
        assert re.fullmatch(r'garden-planting-12-[0-9a-f]{16}', a['session_id'])


def test_targets_are_separate(app):
    with app.app_context():
        assert (HermesChat.get_or_create_active('planting', 12)['session_id']
                != HermesChat.get_or_create_active('planting', 13)['session_id'])


def test_start_new_replaces_active_and_keeps_old(app):
    with app.app_context():
        old = HermesChat.get_or_create_active('crop', 3)
        new = HermesChat.start_new('crop', 3)
        assert new['session_id'] != old['session_id']
        assert HermesChat.get_active('crop', 3)['session_id'] == new['session_id']
        assert set(HermesChat.get_by_session_ids([old['session_id'], new['session_id']])) == \
            {old['session_id'], new['session_id']}


def test_free_chat_has_no_target(app):
    with app.app_context():
        row = HermesChat.get_or_create_active(None, None)
        assert row['entity_type'] is None and row['session_id'].startswith('garden-free-')
        assert HermesChat.get_or_create_active(None, None)['session_id'] == row['session_id']


def test_set_last_run(app):
    with app.app_context():
        row = HermesChat.get_or_create_active('variety', 5)
        HermesChat.set_last_run(row['session_id'], 'run_abc')
        assert HermesChat.get_active('variety', 5)['last_run_id'] == 'run_abc'


def test_touch_keeps_last_run(app):
    with app.app_context():
        row = HermesChat.get_or_create_active('variety', 5)
        HermesChat.set_last_run(row['session_id'], 'run_new')
        HermesChat.touch(row['session_id'])
        assert HermesChat.get_active('variety', 5)['last_run_id'] == 'run_new'


def test_find_by_run_id(app):
    with app.app_context():
        row = HermesChat.get_or_create_active('variety', 5)
        HermesChat.set_last_run(row['session_id'], 'run_abc')
        found = HermesChat.find_by_run_id('run_abc')
        assert found['session_id'] == row['session_id']
        assert HermesChat.find_by_run_id('run_unknown') is None


def _conv(db, hermes_id, parent=None, title='Hermesの題名'):
    cur = db.execute(
        'INSERT INTO conversations (hermes_id, source, title, parent_hermes_id) '
        "VALUES (?, 'api_server', ?, ?)", (hermes_id, title, parent))
    db.commit()
    return cur.lastrowid


def test_create_free_is_not_active_and_many(app):
    with app.app_context():
        a = HermesChat.create_free('オクラ')
        b = HermesChat.create_free('にんにく')
        assert a['session_id'].startswith('garden-free-') and a['active'] == 0
        assert a['id'] != b['id'] and HermesChat.get_active(None, None) is None
        assert HermesChat.get_by_id(a['id'])['title'] == 'オクラ'
        assert HermesChat.get_by_id(999) is None


def test_make_title():
    assert make_title('  来年オクラを\n作りたい  ') == '来年オクラを 作りたい'
    assert make_title('あ' * 40) == 'あ' * 29 + '…'


def test_set_title_if_empty(app):
    with app.app_context():
        row = HermesChat.get_or_create_active('crop', 1)
        HermesChat.set_title_if_empty(row['id'], '最初')
        HermesChat.set_title_if_empty(row['id'], '二度目')
        assert HermesChat.get_by_id(row['id'])['title'] == '最初'


def test_list_for_chat_titles_and_order(app):
    with app.app_context():
        db = get_db()
        panel = HermesChat.get_or_create_active('crop', 1)
        _conv(db, panel['session_id'], title='パネルの題名')
        free = HermesChat.create_free('自由')
        renamed = HermesChat.create_free('旧題')
        db.execute('UPDATE hermes_chats SET custom_title = ? WHERE id = ?', ('変えた', renamed['id']))
        db.execute('UPDATE hermes_chats SET last_used_at = ? WHERE id = ?', ('2026-01-01 00:00:00', panel['id']))
        db.execute('UPDATE hermes_chats SET last_used_at = ? WHERE id = ?', ('2026-01-03 00:00:00', free['id']))
        db.execute('UPDATE hermes_chats SET last_used_at = ? WHERE id = ?', ('2026-01-02 00:00:00', renamed['id']))
        db.commit()
        rows = HermesChat.list_for_chat()
        assert [r['display_title'] for r in rows] == ['自由', '変えた', 'パネルの題名']


def test_rename_updates_conversation_and_child(app):
    with app.app_context():
        db = get_db()
        chat = HermesChat.create_free('旧題')
        _conv(db, chat['session_id'])
        _conv(db, 'child-1', parent=chat['session_id'])
        _conv(db, 'other')
        assert HermesChat.rename(chat['id'], '新題名') is True
        titles = {r['hermes_id']: r['title'] for r in db.execute('SELECT hermes_id, title FROM conversations')}
        assert titles == {chat['session_id']: '新題名', 'child-1': '新題名', 'other': 'Hermesの題名'}
        assert HermesChat.get_by_id(chat['id'])['custom_title'] == '新題名'
        assert HermesChat.rename(999, 'x') is False


def test_upsert_keeps_custom_title_for_child(app):
    with app.app_context():
        chat = HermesChat.create_free('旧題')
        HermesChat.rename(chat['id'], '変えた題名')
        base = {'source': 'api_server', 'started_at': None, 'ended_at': None,
                'last_activity_at': None, 'end_reason': None}
        Conversation.upsert({**base, 'hermes_id': 'child-1', 'parent_hermes_id': chat['session_id'],
                             'title': 'Hermesの題名'})
        Conversation.upsert({**base, 'hermes_id': 'plain', 'parent_hermes_id': None, 'title': '古い'})
        Conversation.upsert({**base, 'hermes_id': 'plain', 'parent_hermes_id': None, 'title': '新しい'})
        db = get_db()
        t = lambda h: db.execute('SELECT title FROM conversations WHERE hermes_id = ?', (h,)).fetchone()['title']
        assert t('child-1') == '変えた題名'
        assert t('plain') == '新しい'


def test_delete_removes_rows_and_remembers_ids(app):
    with app.app_context():
        db = get_db()
        chat = HermesChat.create_free('消す')
        keep_chat = HermesChat.create_free('残す')
        ids = [_conv(db, chat['session_id']), _conv(db, 'child-1', parent=chat['session_id'])]
        keep = _conv(db, keep_chat['session_id'])
        for i, cid in enumerate(ids + [keep]):
            db.execute("INSERT INTO conversation_messages (conversation_id, hermes_message_id, role, content) "
                       "VALUES (?, 1, 'user', 'hi')", (cid,))
            db.execute("INSERT INTO conversation_images (conversation_id, file_name, image_path) "
                       "VALUES (?, 'a.jpg', ?)", (cid, f'conversations/{i}.jpg'))
            db.execute("INSERT INTO conversation_links (conversation_id, entity_type, entity_id, kind) "
                       "VALUES (?, 'crop', 1, 'viewed')", (cid,))
        db.execute("INSERT INTO advices (title, question, answer, advised_on) VALUES ('a', 'q', 'x', '2026-10-30')")
        db.commit()

        paths = HermesChat.delete(chat['id'])

        assert sorted(paths) == ['conversations/0.jpg', 'conversations/1.jpg']
        assert HermesChat.get_by_id(chat['id']) is None
        assert HermesChat.get_by_id(keep_chat['id']) is not None
        count = lambda t, w='1': db.execute(f'SELECT COUNT(*) FROM {t} WHERE {w}').fetchone()[0]
        assert count('conversations') == 1
        assert count('conversation_messages') == 1
        assert count('conversation_images') == 1
        assert count('conversation_links') == 1
        assert count('advices') == 1
        remembered = {r[0] for r in db.execute('SELECT hermes_id FROM deleted_conversations')}
        assert remembered == {chat['session_id'], 'child-1'}
        assert Conversation.is_deleted('child-1', None)
        assert Conversation.is_deleted('new', chat['session_id'])
        assert not Conversation.is_deleted('other', None)


def test_delete_unknown_returns_none(app):
    with app.app_context():
        assert HermesChat.delete(999) is None


def _three_generations(db, chat):
    """本人 → 子 → 孫（Hermes の圧縮が続いた会話）の会話の履歴を作る"""
    _conv(db, chat['session_id'])
    _conv(db, 'child-1', parent=chat['session_id'])
    _conv(db, 'grandchild-1', parent='child-1')
    _conv(db, 'other')


def test_rename_reaches_grandchild(app):
    with app.app_context():
        db = get_db()
        chat = HermesChat.create_free('旧題')
        _three_generations(db, chat)
        HermesChat.rename(chat['id'], '新題名')
        titles = {r['hermes_id']: r['title'] for r in db.execute('SELECT hermes_id, title FROM conversations')}
        assert titles == {chat['session_id']: '新題名', 'child-1': '新題名',
                          'grandchild-1': '新題名', 'other': 'Hermesの題名'}


def test_delete_reaches_grandchild(app):
    with app.app_context():
        db = get_db()
        chat = HermesChat.create_free('消す')
        _three_generations(db, chat)
        gid = db.execute("SELECT id FROM conversations WHERE hermes_id = 'grandchild-1'").fetchone()[0]
        db.execute("INSERT INTO conversation_images (conversation_id, file_name, image_path) "
                   "VALUES (?, 'a.jpg', 'conversations/g.jpg')", (gid,))
        db.commit()
        assert HermesChat.delete(chat['id']) == ['conversations/g.jpg']
        assert [r[0] for r in db.execute('SELECT hermes_id FROM conversations')] == ['other']
        remembered = {r[0] for r in db.execute('SELECT hermes_id FROM deleted_conversations')}
        assert remembered == {chat['session_id'], 'child-1', 'grandchild-1'}


def test_upsert_keeps_custom_title_for_grandchild(app):
    with app.app_context():
        db = get_db()
        chat = HermesChat.create_free('旧題')
        _conv(db, chat['session_id'])
        _conv(db, 'child-1', parent=chat['session_id'])
        HermesChat.rename(chat['id'], '変えた題名')
        base = {'source': 'api_server', 'started_at': None, 'ended_at': None,
                'last_activity_at': None, 'end_reason': None}
        Conversation.upsert({**base, 'hermes_id': 'grandchild-1', 'parent_hermes_id': 'child-1',
                             'title': 'Hermesの題名'})
        assert db.execute("SELECT title FROM conversations WHERE hermes_id = 'grandchild-1'"
                          ).fetchone()['title'] == '変えた題名'


def test_discard_removes_only_chat_row(app):
    with app.app_context():
        db = get_db()
        chat = HermesChat.create_free('捨てる')
        _conv(db, chat['session_id'])
        HermesChat.discard(chat['id'])
        assert HermesChat.get_by_id(chat['id']) is None
        assert db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM deleted_conversations').fetchone()[0] == 0
