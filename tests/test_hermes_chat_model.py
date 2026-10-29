import re

from app.models.hermes_chat import HermesChat


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


def test_find_by_run_id(app):
    with app.app_context():
        row = HermesChat.get_or_create_active('variety', 5)
        HermesChat.set_last_run(row['session_id'], 'run_abc')
        found = HermesChat.find_by_run_id('run_abc')
        assert found['session_id'] == row['session_id']
        assert HermesChat.find_by_run_id('run_unknown') is None
