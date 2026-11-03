"""作物アイコンの名前（大分類_中身.png）と、大分類ごとの一覧"""
import itertools
import os
import re

from app.utils.crop_icons import CATEGORIES, group_crop_icons, list_crop_icons

ROOT = os.path.dirname(os.path.dirname(__file__))
ICON_DIR = os.path.join(ROOT, 'app', 'static', 'images', 'crop_icons')

# 設計書（2026-11-03 作物アイコンの名前の付け替えと統合）の対応表の「新しい名前」84 個
NEW_NAMES = {
    'fruitveg_chili.png', 'fruitveg_chili_pair.png', 'fruitveg_corn.png', 'fruitveg_cucumber.png',
    'fruitveg_cucumber_light.png', 'fruitveg_eggplant.png', 'fruitveg_eggplant_long.png',
    'fruitveg_eggplant_round.png', 'fruitveg_green_pepper.png', 'fruitveg_okra.png', 'fruitveg_paprika.png',
    'fruitveg_pumpkin.png', 'fruitveg_pumpkin_orange.png', 'fruitveg_shishito.png', 'fruitveg_tomato.png',
    'fruitveg_tomato_mini.png', 'fruitveg_wax_gourd.png', 'fruitveg_zucchini.png',
    'bean_edamame.png', 'bean_fava.png', 'bean_green.png', 'bean_ingen.png', 'bean_kidney.png',
    'bean_peanut.png', 'bean_snap_pea.png', 'bean_soybean.png',
    'leaf_bok_choy.png', 'leaf_cabbage.png', 'leaf_chinese_cabbage.png', 'leaf_greens_round.png',
    'leaf_greens_ruffled.png', 'leaf_kale.png', 'leaf_komatsuna.png', 'leaf_leaf_lettuce.png',
    'leaf_lettuce.png', 'leaf_mizuna.png', 'leaf_romaine.png', 'leaf_shungiku.png', 'leaf_spinach.png',
    'leaf_sunny_lettuce.png',
    'stem_asparagus.png', 'stem_bamboo_shoot.png', 'stem_bean_sprout.png', 'stem_broccoli.png',
    'stem_broccoli_stick.png', 'stem_cauliflower.png', 'stem_celery.png', 'stem_sprout.png',
    'onion_chive.png', 'onion_garlic.png', 'onion_leek.png', 'onion_onion.png', 'onion_rakkyo.png',
    'onion_red_onion.png', 'onion_scallion.png', 'onion_spring_onion.png',
    'root_burdock.png', 'root_carrot.png', 'root_daikon.png', 'root_ginger.png', 'root_turnip_purple.png',
    'root_turnip_purple_small.png', 'root_turnip_white.png',
    'tuber_potato.png', 'tuber_sweet_potato.png', 'tuber_taro.png',
    'herb_basil.png', 'herb_bay_leaf.png', 'herb_coriander.png', 'herb_mitsuba.png', 'herb_myoga.png',
    'herb_parsley.png', 'herb_shiso.png', 'herb_shiso_red.png',
    'mushroom_enoki.png', 'mushroom_eringi.png', 'mushroom_kikurage.png', 'mushroom_maitake.png',
    'mushroom_nameko.png', 'mushroom_shiitake.png', 'mushroom_shimeji.png',
    'fruit_amanatsu.png', 'fruit_mikan.png', 'fruit_watermelon.png',
}

LABELS = ['実の野菜', '豆', '葉の野菜', '茎・花の野菜', 'ねぎ類', '根の野菜', 'いも', 'ハーブ', 'きのこ', '果物']


def test_icon_files_are_new_set():
    assert len(NEW_NAMES) == 84
    assert set(os.listdir(ICON_DIR)) == NEW_NAMES


def test_list_crop_icons_order():
    icons = list_crop_icons()
    assert icons[0] == 'fruitveg_chili.png' and icons[-1] == 'fruit_watermelon.png'
    prefixes = [p for p, _ in itertools.groupby(i.split('_', 1)[0] for i in icons)]
    assert prefixes == [p for p, _ in CATEGORIES]
    for _, files in itertools.groupby(icons, key=lambda i: i.split('_', 1)[0]):
        files = list(files)
        assert files == sorted(files)


def test_group_crop_icons_labels():
    groups = group_crop_icons()
    assert [label for label, _ in groups] == LABELS
    assert sum(len(files) for _, files in groups) == 84


def test_group_unknown_prefix_goes_last():
    groups = group_crop_icons(['custom_x.png', 'bean_peanut.png', 'plain.png', 'fruitveg_tomato.png'])
    assert groups == [('実の野菜', ['fruitveg_tomato.png']), ('豆', ['bean_peanut.png']),
                      ('その他', ['custom_x.png', 'plain.png'])]


def test_no_old_icon_names_outside_migrations():
    old = re.compile(r'icon_\d{3}\.png')
    skip = os.path.join(ROOT, 'app', 'migrations', '029_rename_crop_icons.sql')
    found = []
    for top in ('app', 'tools'):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, top)):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for name in filenames:
                path = os.path.join(dirpath, name)
                if path == skip or os.path.splitext(name)[1] not in {'.py', '.html', '.js', '.css', '.md', '.sql'}:
                    continue
                with open(path, encoding='utf-8') as f:
                    if old.search(f.read()):
                        found.append(os.path.relpath(path, ROOT))
    assert found == []
