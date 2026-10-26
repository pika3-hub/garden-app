from app.models.conversation import Conversation


def _session(**kw):
    s = {'hermes_id': '20261025_165529_f52993ca', 'source': 'matrix', 'title': 'じゃがいも',
         'started_at': '2026-10-25 16:55:29', 'ended_at': None,
         'last_activity_at': '2026-10-25 16:56:00',
         'end_reason': None, 'parent_hermes_id': None}
    s.update(kw)
    return s


def _msg(mid, role='user', content='こんにちは', ts='2026-10-25 16:55:30', **kw):
    m = {'hermes_message_id': mid, 'role': role, 'content': content, 'timestamp': ts}
    m.update(kw)
    return m


def test_upsert_creates_then_updates(app):
    with app.app_context():
        s = _session()
        cid, created = Conversation.upsert(s)
        assert created is True
        cid2, created2 = Conversation.upsert({**s, 'title': '変更後'})
        assert (cid2, created2) == (cid, False)
        assert Conversation.get_by_id(cid)['title'] == '変更後'
        assert Conversation.get_by_hermes_id(s['hermes_id'])['id'] == cid


def test_upsert_messages_keeps_unsent(app):
    with app.app_context():
        cid, _ = Conversation.upsert(_session())
        Conversation.upsert_messages(cid, [_msg(1045, content='a'), _msg(1046, content='b')])
        Conversation.upsert_messages(cid, [_msg(1046, content='b変更'), _msg(1047, content='c')])
        msgs = Conversation.get_messages(cid, include_tools=True)
        assert [m['hermes_message_id'] for m in msgs] == [1045, 1046, 1047]
        assert msgs[1]['content'] == 'b変更'


def test_get_messages_hides_tools_and_empty(app):
    with app.app_context():
        cid, _ = Conversation.upsert(_session())
        Conversation.upsert_messages(cid, [
            _msg(1, 'user', 'やあ'),
            _msg(2, 'assistant', '', tool_calls='[{"function": {"name": "terminal"}}]'),
            _msg(3, 'tool', '結果', tool_name='terminal'),
            _msg(4, 'assistant', '答え'),
        ])
        assert [m['hermes_message_id'] for m in Conversation.get_messages(cid)] == [1, 4]
        assert len(Conversation.get_messages(cid, include_tools=True)) == 4


def test_get_by_entity_merges_kinds(app):
    with app.app_context():
        cid, _ = Conversation.upsert(_session())
        Conversation.replace_links(cid, [
            {'entity_type': 'planting', 'entity_id': 45, 'kind': 'viewed', 'hermes_message_id': 1},
            {'entity_type': 'planting', 'entity_id': 45, 'kind': 'updated', 'hermes_message_id': 2},
        ])
        rows = Conversation.get_by_entity('planting', 45)
        assert len(rows) == 1
        assert rows[0]['kind'] == 'updated'
        assert rows[0]['id'] == cid
        assert Conversation.get_by_entity('planting', 46) == []


def test_search_matches_title_and_text_not_tools(app):
    with app.app_context():
        cid, _ = Conversation.upsert(_session(title='無題'))
        Conversation.upsert_messages(cid, [
            _msg(1, 'user', 'じゃがいもを植えたい'),
            _msg(2, 'tool', 'skill_view の結果', tool_name='skill_view'),
        ])
        assert [r['id'] for r in Conversation.search('じゃがいも')] == [cid]
        assert Conversation.search('skill_view') == []
        cid2, _ = Conversation.upsert(_session(hermes_id='x2', title='トマトの話'))
        assert [r['id'] for r in Conversation.search('トマト')] == [cid2]
        assert Conversation.search('100%') == []


def test_list_counts(app):
    with app.app_context():
        cid, _ = Conversation.upsert(_session())
        Conversation.upsert_messages(cid, [
            _msg(1, 'user', '写真 [Image attached at: /x/img_a.jpg]'),
            _msg(2, 'assistant', ''),
            _msg(3, 'tool', 'r'),
            _msg(4, 'assistant', 'はい'),
        ])
        Conversation.add_image(cid, 'img_a.jpg', 'conversations/img_a.jpg')
        Conversation.replace_links(cid, [
            {'entity_type': 'crop', 'entity_id': 1, 'kind': 'viewed', 'hermes_message_id': 1},
            {'entity_type': 'crop', 'entity_id': 2, 'kind': 'created', 'hermes_message_id': 4},
        ])
        row = Conversation.get_all()[0]
        assert row['message_count'] == 2
        assert row['image_count'] == 1
        assert row['has_image_marker']
        assert row['link_count'] == 2
        assert Conversation.has_image(cid, 'img_a.jpg')
        assert Conversation.get_images(cid) == {'img_a.jpg': 'conversations/img_a.jpg'}
        assert len(Conversation.get_links(cid)) == 2
        assert Conversation.all_ids() == [cid]


def test_order_and_adjacent(app):
    with app.app_context():
        a, _ = Conversation.upsert(_session(hermes_id='a', last_activity_at='2026-10-01 10:00:00'))
        b, _ = Conversation.upsert(_session(hermes_id='b', last_activity_at='2026-10-02 10:00:00'))
        c, _ = Conversation.upsert(_session(hermes_id='c', last_activity_at=None,
                                            started_at='2026-10-03 10:00:00'))
        assert [r['id'] for r in Conversation.get_all()] == [c, b, a]
        prev, nxt = Conversation.get_adjacent(b)
        assert (prev['id'], nxt['id']) == (a, c)
        assert Conversation.get_adjacent(a)[0] is None
        assert Conversation.get_adjacent(c)[1] is None
        assert Conversation.get_adjacent(999) == (None, None)
