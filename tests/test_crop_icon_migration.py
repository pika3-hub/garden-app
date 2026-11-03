"""マイグレーション 029: 作物・品種と見取り図のアイコン名を新しい名前に付け替える"""
import json
import os

import pytest

from app.database import get_db, run_migrations

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'static', 'images', 'crop_icons')

# 古い名前 → 新しい名前（設計書の対応表 84 行＋統合 13 行は統合先の新しい名前）
MAPPING = {
    'icon_001.png': 'fruitveg_tomato.png', 'icon_002.png': 'fruitveg_eggplant.png', 'icon_003.png': 'fruitveg_green_pepper.png',
    'icon_004.png': 'fruitveg_paprika.png', 'icon_005.png': 'fruitveg_shishito.png', 'icon_006.png': 'fruitveg_chili.png',
    'icon_007.png': 'fruitveg_cucumber.png', 'icon_008.png': 'fruit_watermelon.png', 'icon_009.png': 'fruitveg_wax_gourd.png',
    'icon_010.png': 'fruitveg_pumpkin_orange.png', 'icon_011.png': 'fruitveg_cucumber_light.png', 'icon_012.png': 'bean_peanut.png',
    'icon_013.png': 'bean_peanut.png', 'icon_014.png': 'bean_edamame.png', 'icon_015.png': 'bean_green.png',
    'icon_016.png': 'bean_kidney.png', 'icon_017.png': 'bean_ingen.png', 'icon_018.png': 'bean_soybean.png',
    'icon_019.png': 'bean_soybean.png', 'icon_020.png': 'bean_fava.png', 'icon_021.png': 'bean_fava.png',
    'icon_022.png': 'bean_snap_pea.png', 'icon_023.png': 'fruitveg_corn.png', 'icon_024.png': 'fruitveg_okra.png',
    'icon_025.png': 'stem_broccoli.png', 'icon_026.png': 'stem_cauliflower.png', 'icon_027.png': 'herb_shiso_red.png',
    'icon_028.png': 'onion_scallion.png', 'icon_029.png': 'stem_cauliflower.png', 'icon_030.png': 'herb_shiso.png',
    'icon_031.png': 'onion_chive.png', 'icon_032.png': 'onion_garlic.png', 'icon_033.png': 'herb_myoga.png',
    'icon_034.png': 'herb_myoga.png', 'icon_035.png': 'fruitveg_zucchini.png', 'icon_036.png': 'leaf_cabbage.png',
    'icon_037.png': 'leaf_chinese_cabbage.png', 'icon_038.png': 'leaf_greens_ruffled.png', 'icon_039.png': 'root_daikon.png',
    'icon_040.png': 'leaf_cabbage.png', 'icon_041.png': 'leaf_chinese_cabbage.png', 'icon_042.png': 'leaf_komatsuna.png',
    'icon_043.png': 'root_daikon.png', 'icon_044.png': 'herb_basil.png', 'icon_045.png': 'herb_basil.png',
    'icon_046.png': 'stem_sprout.png', 'icon_047.png': 'leaf_spinach.png', 'icon_048.png': 'fruitveg_chili_pair.png',
    'icon_049.png': 'stem_bean_sprout.png', 'icon_050.png': 'leaf_greens_round.png', 'icon_051.png': 'herb_mitsuba.png',
    'icon_052.png': 'fruitveg_chili.png', 'icon_053.png': 'leaf_shungiku.png', 'icon_054.png': 'tuber_sweet_potato.png',
    'icon_055.png': 'herb_coriander.png', 'icon_056.png': 'herb_parsley.png', 'icon_057.png': 'leaf_leaf_lettuce.png',
    'icon_058.png': 'leaf_romaine.png', 'icon_059.png': 'leaf_bok_choy.png', 'icon_060.png': 'leaf_lettuce.png',
    'icon_061.png': 'root_burdock.png', 'icon_062.png': 'leaf_kale.png', 'icon_063.png': 'stem_asparagus.png',
    'icon_064.png': 'onion_leek.png', 'icon_065.png': 'onion_spring_onion.png', 'icon_066.png': 'onion_onion.png',
    'icon_067.png': 'stem_bamboo_shoot.png', 'icon_068.png': 'herb_bay_leaf.png', 'icon_069.png': 'root_turnip_purple_small.png',
    'icon_070.png': 'root_turnip_purple.png', 'icon_071.png': 'root_carrot.png', 'icon_072.png': 'root_ginger.png',
    'icon_073.png': 'root_ginger.png', 'icon_074.png': 'tuber_potato.png', 'icon_075.png': 'root_ginger.png',
    'icon_076.png': 'onion_rakkyo.png', 'icon_077.png': 'onion_rakkyo.png', 'icon_078.png': 'mushroom_kikurage.png',
    'icon_079.png': 'mushroom_maitake.png', 'icon_080.png': 'mushroom_enoki.png', 'icon_081.png': 'mushroom_shimeji.png',
    'icon_082.png': 'mushroom_shiitake.png', 'icon_083.png': 'mushroom_nameko.png', 'icon_084.png': 'mushroom_eringi.png',
    'icon_085.png': 'leaf_mizuna.png', 'icon_086.png': 'stem_celery.png', 'icon_087.png': 'stem_broccoli_stick.png',
    'icon_088.png': 'tuber_taro.png', 'icon_089.png': 'root_turnip_white.png', 'icon_090.png': 'fruitveg_tomato_mini.png',
    'icon_091.png': 'fruitveg_pumpkin.png', 'icon_092.png': 'fruitveg_eggplant_long.png', 'icon_093.png': 'fruitveg_eggplant_round.png',
    'icon_094.png': 'onion_red_onion.png', 'icon_095.png': 'leaf_sunny_lettuce.png', 'icon_096.png': 'fruit_mikan.png',
    'icon_097.png': 'fruit_amanatsu.png',
}


def _crop(db, icon_path):
    return db.execute("INSERT INTO crops (name, crop_type, icon_path) VALUES ('作物', '種類', ?)",
                      (icon_path,)).lastrowid


def _variety(db, crop_id, icon_path):
    return db.execute("INSERT INTO varieties (crop_id, name, icon_path) VALUES (?, '品種', ?)",
                      (crop_id, icon_path)).lastrowid


def _value(app, sql, row_id):
    with app.app_context():
        return get_db().execute(sql, (row_id,)).fetchone()[0]


def test_mapping_covers_all_old_names_and_targets_exist():
    assert set(MAPPING) == {f'icon_{n:03d}.png' for n in range(1, 98)}
    assert set(MAPPING.values()) <= set(os.listdir(ICON_DIR))


@pytest.mark.parametrize('old, new', sorted(MAPPING.items()))
def test_migration_renames_crop_and_variety_icon(app, old, new):
    with app.app_context():
        db = get_db()
        crop_id = _crop(db, old)
        variety_id = _variety(db, crop_id, old)
        db.commit()
        run_migrations(app, db)
    assert _value(app, 'SELECT icon_path FROM crops WHERE id = ?', crop_id) == new
    assert _value(app, 'SELECT icon_path FROM varieties WHERE id = ?', variety_id) == new


def test_migration_renames_icons_in_canvas_json(app):
    placements = [
        {'locationCropId': 1, 'cropId': 5, 'x': 10, 'y': 20, 'iconPath': 'icon_003.png',
         'imageColor': '#4CAF50', 'cropName': 'ピーマン', 'variety': '京みどり'},
        {'locationCropId': 2, 'cropId': 6, 'x': 300, 'y': 400, 'iconPath': 'icon_033.png',
         'imageColor': '#E91E63', 'cropName': 'ミョウガ', 'variety': None},
        {'locationCropId': 3, 'cropId': 7, 'x': 500, 'y': 600, 'iconPath': 'fruitveg_tomato.png',
         'imageColor': '#F44336', 'cropName': 'トマト', 'variety': 'アイコ'},
    ]
    canvas = {'version': '2.0', 'placements': placements}
    snapshot = {'version': '2.0', 'placements': [dict(placements[0], iconPath='icon_001.png')]}
    with app.app_context():
        db = get_db()
        location_id = db.execute(
            "INSERT INTO locations (name, location_type, canvas_data) VALUES ('畑', '畑', ?)",
            (json.dumps(canvas, ensure_ascii=False),)).lastrowid
        crop_id = _crop(db, 'fruitveg_tomato.png')
        planting_id = db.execute(
            "INSERT INTO plantings (location_id, crop_id, status, canvas_snapshot) VALUES (?, ?, 'ended', ?)",
            (location_id, crop_id, json.dumps(snapshot, ensure_ascii=False))).lastrowid
        db.commit()
        run_migrations(app, db)

    got = json.loads(_value(app, 'SELECT canvas_data FROM locations WHERE id = ?', location_id))
    expected = [dict(placements[0], iconPath='fruitveg_green_pepper.png'),
                dict(placements[1], iconPath='herb_myoga.png'),
                placements[2]]
    assert got == {'version': '2.0', 'placements': expected}
    snap = json.loads(_value(app, 'SELECT canvas_snapshot FROM plantings WHERE id = ?', planting_id))
    assert snap == {'version': '2.0', 'placements': [dict(placements[0], iconPath='fruitveg_tomato.png')]}


def test_migration_keeps_new_and_unknown_names(app):
    with app.app_context():
        db = get_db()
        ids = {_crop(db, name): name for name in ('fruitveg_tomato.png', 'custom.png')}
        location_id = db.execute("INSERT INTO locations (name, location_type) VALUES ('畑', '畑')").lastrowid
        db.commit()
        run_migrations(app, db)
        run_migrations(app, db)
    assert {i: _value(app, 'SELECT icon_path FROM crops WHERE id = ?', i) for i in ids} == ids
    assert _value(app, 'SELECT canvas_data FROM locations WHERE id = ?', location_id) is None


def test_migration_keeps_null_variety_icon(app):
    with app.app_context():
        db = get_db()
        variety_id = _variety(db, _crop(db, 'icon_001.png'), None)
        db.commit()
        run_migrations(app, db)
    assert _value(app, 'SELECT icon_path FROM varieties WHERE id = ?', variety_id) is None
