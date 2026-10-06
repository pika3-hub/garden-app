"""編集フォームで NULL のカラムが「None」と表示されないこと

以前は `{{ harvest.unit if harvest else '' }}` のように書いていたため、NULL の値が
入力欄に「None」と表示され、そのまま保存すると文字列 'None' が登録されていた。
"""
import pytest

from app.database import get_db


@pytest.fixture
def seeded(app):
    with app.app_context():
        db = get_db()
        crop_id = db.execute(
            "INSERT INTO crops (name, crop_type) VALUES ('トマト', 'トマト')"
        ).lastrowid
        variety_id = db.execute(
            "INSERT INTO varieties (crop_id, name) VALUES (?, 'アイコ')", (crop_id,)
        ).lastrowid
        location_id = db.execute(
            "INSERT INTO locations (name, location_type) VALUES ('畑A', '畑')"
        ).lastrowid
        planting_id = db.execute(
            'INSERT INTO plantings (location_id, crop_id) VALUES (?, ?)',
            (location_id, crop_id),
        ).lastrowid
        harvest_id = db.execute(
            "INSERT INTO harvests (location_crop_id, harvest_date) VALUES (?, '2026-10-01')",
            (planting_id,),
        ).lastrowid
        db.commit()
    return {'crop': crop_id, 'variety': variety_id, 'harvest': harvest_id}


@pytest.mark.parametrize('url', [
    '/harvests/{harvest}/edit',
    '/crops/{crop}/edit',
    '/varieties/{variety}/edit',
])
def test_edit_form_does_not_render_none(client, seeded, url):
    res = client.get(url.format(**seeded))
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'value="None"' not in html
    assert '>None</textarea>' not in html
