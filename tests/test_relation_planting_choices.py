"""関連付け（日記・タスク・料理・アドバイス）の植え付けの選択肢

栽培終了の植え付けも選べる（終了した作物のまとめを書くため）。削除済みは出さないが、
関連付け済みなら編集画面で表示して外せるようにする。
"""
import pytest

from app.database import get_db
from app.models.planting import Planting


def _seed(app):
    """栽培中1・栽培終了2・削除済み1の植え付けと、それぞれに植え付けを関連付けた日記・タスク・料理"""
    with app.app_context():
        db = get_db()
        nasu = db.execute("INSERT INTO crops (name, crop_type) VALUES ('ナス', 'なす')").lastrowid
        tomato = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'トマト')").lastrowid
        loc = db.execute("INSERT INTO locations (name, location_type) VALUES ('南の畑', '畑')").lastrowid

        def planting(crop, planted, status, end=None):
            return db.execute(
                'INSERT INTO plantings (location_id, crop_id, planted_date, status, end_date) VALUES (?, ?, ?, ?, ?)',
                (loc, crop, planted, status, end)).lastrowid

        ids = {
            'active': planting(tomato, '2026-08-01', 'active'),
            # 植え付けは古いが最近終えたもの（終了日の新しい順で先頭に来る）
            'ended_recent': planting(nasu, '2026-04-20', 'ended', '2026-10-25'),
            'ended_old': planting(nasu, '2026-05-10', 'ended', '2026-07-15'),
            'removed': planting(tomato, '2026-06-01', 'removed', '2026-06-10'),
        }
        linked = [ids['ended_recent'], ids['removed']]
        ids['diary'] = db.execute(
            "INSERT INTO diary_entries (title, entry_date) VALUES ('ナスのまとめ', '2026-10-30')").lastrowid
        ids['task'] = db.execute("INSERT INTO tasks (title) VALUES ('片付け')").lastrowid
        ids['cooking'] = db.execute(
            "INSERT INTO cooking (title, cooked_date) VALUES ('焼きなす', '2026-10-26')").lastrowid
        for pid in linked:
            db.execute("INSERT INTO diary_relations (diary_id, relation_type, location_crop_id) "
                       "VALUES (?, 'location_crop', ?)", (ids['diary'], pid))
            db.execute("INSERT INTO task_relations (task_id, relation_type, location_crop_id) "
                       "VALUES (?, 'location_crop', ?)", (ids['task'], pid))
            db.execute("INSERT INTO cooking_relations (cooking_id, relation_type, location_crop_id) "
                       "VALUES (?, 'location_crop', ?)", (ids['cooking'], pid))
        db.commit()
        return ids


def _modal(body):
    return body.split('id="plantingMultiSelectModal"')[1].split('ms-modal-footer')[0]


def _card_order(modal, ids, keys):
    return sorted(keys, key=lambda k: modal.index(f'data-planting-id="{ids[k]}"'))


def test_relation_choices_order_and_removed(app):
    ids = _seed(app)
    with app.app_context():
        choices = Planting.get_relation_choices()
        assert [p['id'] for p in choices] == [ids['ended_recent'], ids['active'], ids['ended_old']]
        assert [p['relation_date'] for p in choices] == ['2026-10-25', '2026-08-01', '2026-07-15']

        # 関連付け済みなら削除済みも入る
        choices = Planting.get_relation_choices([str(ids['removed'])])
        assert ids['removed'] in [p['id'] for p in choices]


@pytest.mark.parametrize('url', ['/diary/new', '/tasks/new', '/cooking/new'])
def test_new_form_lists_ended_plantings(app, client, url):
    ids = _seed(app)
    modal = _modal(client.get(url).get_data(as_text=True))
    assert _card_order(modal, ids, ['active', 'ended_recent', 'ended_old']) == ['ended_recent', 'active', 'ended_old']
    assert f'data-planting-id="{ids["removed"]}"' not in modal
    # 栽培終了は終了日の月で見出しを分け、終了日を出す
    assert '2026年10月' in modal and '2026年7月' in modal
    assert '終了日: 2026-10-25' in modal
    # 状態の絞り込み（種類の絞り込みに「なす」が出るので、ナスだけにも絞れる）
    assert 'data-filter-key="status"' in modal
    assert 'data-ms-filter-group-status="栽培終了"' in modal
    assert 'data-type="なす"' in modal


@pytest.mark.parametrize('kind', ['diary', 'tasks', 'cooking'])
def test_edit_form_shows_linked_ended_and_removed(app, client, kind):
    ids = _seed(app)
    entity_id = ids[{'diary': 'diary', 'tasks': 'task', 'cooking': 'cooking'}[kind]]
    modal = _modal(client.get(f'/{kind}/{entity_id}/edit').get_data(as_text=True))
    for key in ('ended_recent', 'removed'):
        assert f'data-planting-id="{ids[key]}"' in modal
    assert 'data-ms-filter-group-status="削除済み"' in modal


def test_harvest_bulk_keeps_active_only_without_status_filter(app, client):
    ids = _seed(app)
    body = client.get('/harvests/bulk/new').get_data(as_text=True)
    assert f'data-planting-id="{ids["ended_recent"]}"' not in body
    assert 'data-filter-key="status"' not in body
