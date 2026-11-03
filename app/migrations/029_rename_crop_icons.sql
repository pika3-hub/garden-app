-- 作物アイコンの名前の付け替えと統合: 作物・品種と見取り図のアイコン名を新しい名前にする
-- Migration: 029_rename_crop_icons
--
-- 連番の icon_NNN.png（97 枚）をやめ、「大分類_中身.png」の 84 枚にした（似ている 13 枚は統合先の名前にする）。
-- アイコン名は crops / varieties の icon_path と、見取り図の JSON（locations.canvas_data、
-- plantings.canvas_snapshot）の "iconPath" に入っている。JSON は引用符まで含めて置き換える。
-- 起動のたびに実行されるので、古い 97 個の名前だけを対象にする（新しい名前・将来足した名前は書き換えない）。
UPDATE crops SET icon_path = CASE icon_path
    WHEN 'icon_001.png' THEN 'fruitveg_tomato.png'
    WHEN 'icon_002.png' THEN 'fruitveg_eggplant.png'
    WHEN 'icon_003.png' THEN 'fruitveg_green_pepper.png'
    WHEN 'icon_004.png' THEN 'fruitveg_paprika.png'
    WHEN 'icon_005.png' THEN 'fruitveg_shishito.png'
    WHEN 'icon_006.png' THEN 'fruitveg_chili.png'
    WHEN 'icon_007.png' THEN 'fruitveg_cucumber.png'
    WHEN 'icon_008.png' THEN 'fruit_watermelon.png'
    WHEN 'icon_009.png' THEN 'fruitveg_wax_gourd.png'
    WHEN 'icon_010.png' THEN 'fruitveg_pumpkin_orange.png'
    WHEN 'icon_011.png' THEN 'fruitveg_cucumber_light.png'
    WHEN 'icon_012.png' THEN 'bean_peanut.png'
    WHEN 'icon_013.png' THEN 'bean_peanut.png'
    WHEN 'icon_014.png' THEN 'bean_edamame.png'
    WHEN 'icon_015.png' THEN 'bean_green.png'
    WHEN 'icon_016.png' THEN 'bean_kidney.png'
    WHEN 'icon_017.png' THEN 'bean_ingen.png'
    WHEN 'icon_018.png' THEN 'bean_soybean.png'
    WHEN 'icon_019.png' THEN 'bean_soybean.png'
    WHEN 'icon_020.png' THEN 'bean_fava.png'
    WHEN 'icon_021.png' THEN 'bean_fava.png'
    WHEN 'icon_022.png' THEN 'bean_snap_pea.png'
    WHEN 'icon_023.png' THEN 'fruitveg_corn.png'
    WHEN 'icon_024.png' THEN 'fruitveg_okra.png'
    WHEN 'icon_025.png' THEN 'stem_broccoli.png'
    WHEN 'icon_026.png' THEN 'stem_cauliflower.png'
    WHEN 'icon_027.png' THEN 'herb_shiso_red.png'
    WHEN 'icon_028.png' THEN 'onion_scallion.png'
    WHEN 'icon_029.png' THEN 'stem_cauliflower.png'
    WHEN 'icon_030.png' THEN 'herb_shiso.png'
    WHEN 'icon_031.png' THEN 'onion_chive.png'
    WHEN 'icon_032.png' THEN 'onion_garlic.png'
    WHEN 'icon_033.png' THEN 'herb_myoga.png'
    WHEN 'icon_034.png' THEN 'herb_myoga.png'
    WHEN 'icon_035.png' THEN 'fruitveg_zucchini.png'
    WHEN 'icon_036.png' THEN 'leaf_cabbage.png'
    WHEN 'icon_037.png' THEN 'leaf_chinese_cabbage.png'
    WHEN 'icon_038.png' THEN 'leaf_greens_ruffled.png'
    WHEN 'icon_039.png' THEN 'root_daikon.png'
    WHEN 'icon_040.png' THEN 'leaf_cabbage.png'
    WHEN 'icon_041.png' THEN 'leaf_chinese_cabbage.png'
    WHEN 'icon_042.png' THEN 'leaf_komatsuna.png'
    WHEN 'icon_043.png' THEN 'root_daikon.png'
    WHEN 'icon_044.png' THEN 'herb_basil.png'
    WHEN 'icon_045.png' THEN 'herb_basil.png'
    WHEN 'icon_046.png' THEN 'stem_sprout.png'
    WHEN 'icon_047.png' THEN 'leaf_spinach.png'
    WHEN 'icon_048.png' THEN 'fruitveg_chili_pair.png'
    WHEN 'icon_049.png' THEN 'stem_bean_sprout.png'
    WHEN 'icon_050.png' THEN 'leaf_greens_round.png'
    WHEN 'icon_051.png' THEN 'herb_mitsuba.png'
    WHEN 'icon_052.png' THEN 'fruitveg_chili.png'
    WHEN 'icon_053.png' THEN 'leaf_shungiku.png'
    WHEN 'icon_054.png' THEN 'tuber_sweet_potato.png'
    WHEN 'icon_055.png' THEN 'herb_coriander.png'
    WHEN 'icon_056.png' THEN 'herb_parsley.png'
    WHEN 'icon_057.png' THEN 'leaf_leaf_lettuce.png'
    WHEN 'icon_058.png' THEN 'leaf_romaine.png'
    WHEN 'icon_059.png' THEN 'leaf_bok_choy.png'
    WHEN 'icon_060.png' THEN 'leaf_lettuce.png'
    WHEN 'icon_061.png' THEN 'root_burdock.png'
    WHEN 'icon_062.png' THEN 'leaf_kale.png'
    WHEN 'icon_063.png' THEN 'stem_asparagus.png'
    WHEN 'icon_064.png' THEN 'onion_leek.png'
    WHEN 'icon_065.png' THEN 'onion_spring_onion.png'
    WHEN 'icon_066.png' THEN 'onion_onion.png'
    WHEN 'icon_067.png' THEN 'stem_bamboo_shoot.png'
    WHEN 'icon_068.png' THEN 'herb_bay_leaf.png'
    WHEN 'icon_069.png' THEN 'root_turnip_purple_small.png'
    WHEN 'icon_070.png' THEN 'root_turnip_purple.png'
    WHEN 'icon_071.png' THEN 'root_carrot.png'
    WHEN 'icon_072.png' THEN 'root_ginger.png'
    WHEN 'icon_073.png' THEN 'root_ginger.png'
    WHEN 'icon_074.png' THEN 'tuber_potato.png'
    WHEN 'icon_075.png' THEN 'root_ginger.png'
    WHEN 'icon_076.png' THEN 'onion_rakkyo.png'
    WHEN 'icon_077.png' THEN 'onion_rakkyo.png'
    WHEN 'icon_078.png' THEN 'mushroom_kikurage.png'
    WHEN 'icon_079.png' THEN 'mushroom_maitake.png'
    WHEN 'icon_080.png' THEN 'mushroom_enoki.png'
    WHEN 'icon_081.png' THEN 'mushroom_shimeji.png'
    WHEN 'icon_082.png' THEN 'mushroom_shiitake.png'
    WHEN 'icon_083.png' THEN 'mushroom_nameko.png'
    WHEN 'icon_084.png' THEN 'mushroom_eringi.png'
    WHEN 'icon_085.png' THEN 'leaf_mizuna.png'
    WHEN 'icon_086.png' THEN 'stem_celery.png'
    WHEN 'icon_087.png' THEN 'stem_broccoli_stick.png'
    WHEN 'icon_088.png' THEN 'tuber_taro.png'
    WHEN 'icon_089.png' THEN 'root_turnip_white.png'
    WHEN 'icon_090.png' THEN 'fruitveg_tomato_mini.png'
    WHEN 'icon_091.png' THEN 'fruitveg_pumpkin.png'
    WHEN 'icon_092.png' THEN 'fruitveg_eggplant_long.png'
    WHEN 'icon_093.png' THEN 'fruitveg_eggplant_round.png'
    WHEN 'icon_094.png' THEN 'onion_red_onion.png'
    WHEN 'icon_095.png' THEN 'leaf_sunny_lettuce.png'
    WHEN 'icon_096.png' THEN 'fruit_mikan.png'
    WHEN 'icon_097.png' THEN 'fruit_amanatsu.png'
END
WHERE icon_path IN ('icon_001.png', 'icon_002.png', 'icon_003.png', 'icon_004.png', 'icon_005.png', 'icon_006.png', 'icon_007.png', 'icon_008.png', 'icon_009.png', 'icon_010.png', 'icon_011.png', 'icon_012.png', 'icon_013.png', 'icon_014.png', 'icon_015.png', 'icon_016.png', 'icon_017.png', 'icon_018.png', 'icon_019.png', 'icon_020.png', 'icon_021.png', 'icon_022.png', 'icon_023.png', 'icon_024.png', 'icon_025.png', 'icon_026.png', 'icon_027.png', 'icon_028.png', 'icon_029.png', 'icon_030.png', 'icon_031.png', 'icon_032.png', 'icon_033.png', 'icon_034.png', 'icon_035.png', 'icon_036.png', 'icon_037.png', 'icon_038.png', 'icon_039.png', 'icon_040.png', 'icon_041.png', 'icon_042.png', 'icon_043.png', 'icon_044.png', 'icon_045.png', 'icon_046.png', 'icon_047.png', 'icon_048.png', 'icon_049.png', 'icon_050.png', 'icon_051.png', 'icon_052.png', 'icon_053.png', 'icon_054.png', 'icon_055.png', 'icon_056.png', 'icon_057.png', 'icon_058.png', 'icon_059.png', 'icon_060.png', 'icon_061.png', 'icon_062.png', 'icon_063.png', 'icon_064.png', 'icon_065.png', 'icon_066.png', 'icon_067.png', 'icon_068.png', 'icon_069.png', 'icon_070.png', 'icon_071.png', 'icon_072.png', 'icon_073.png', 'icon_074.png', 'icon_075.png', 'icon_076.png', 'icon_077.png', 'icon_078.png', 'icon_079.png', 'icon_080.png', 'icon_081.png', 'icon_082.png', 'icon_083.png', 'icon_084.png', 'icon_085.png', 'icon_086.png', 'icon_087.png', 'icon_088.png', 'icon_089.png', 'icon_090.png', 'icon_091.png', 'icon_092.png', 'icon_093.png', 'icon_094.png', 'icon_095.png', 'icon_096.png', 'icon_097.png');

UPDATE varieties SET icon_path = CASE icon_path
    WHEN 'icon_001.png' THEN 'fruitveg_tomato.png'
    WHEN 'icon_002.png' THEN 'fruitveg_eggplant.png'
    WHEN 'icon_003.png' THEN 'fruitveg_green_pepper.png'
    WHEN 'icon_004.png' THEN 'fruitveg_paprika.png'
    WHEN 'icon_005.png' THEN 'fruitveg_shishito.png'
    WHEN 'icon_006.png' THEN 'fruitveg_chili.png'
    WHEN 'icon_007.png' THEN 'fruitveg_cucumber.png'
    WHEN 'icon_008.png' THEN 'fruit_watermelon.png'
    WHEN 'icon_009.png' THEN 'fruitveg_wax_gourd.png'
    WHEN 'icon_010.png' THEN 'fruitveg_pumpkin_orange.png'
    WHEN 'icon_011.png' THEN 'fruitveg_cucumber_light.png'
    WHEN 'icon_012.png' THEN 'bean_peanut.png'
    WHEN 'icon_013.png' THEN 'bean_peanut.png'
    WHEN 'icon_014.png' THEN 'bean_edamame.png'
    WHEN 'icon_015.png' THEN 'bean_green.png'
    WHEN 'icon_016.png' THEN 'bean_kidney.png'
    WHEN 'icon_017.png' THEN 'bean_ingen.png'
    WHEN 'icon_018.png' THEN 'bean_soybean.png'
    WHEN 'icon_019.png' THEN 'bean_soybean.png'
    WHEN 'icon_020.png' THEN 'bean_fava.png'
    WHEN 'icon_021.png' THEN 'bean_fava.png'
    WHEN 'icon_022.png' THEN 'bean_snap_pea.png'
    WHEN 'icon_023.png' THEN 'fruitveg_corn.png'
    WHEN 'icon_024.png' THEN 'fruitveg_okra.png'
    WHEN 'icon_025.png' THEN 'stem_broccoli.png'
    WHEN 'icon_026.png' THEN 'stem_cauliflower.png'
    WHEN 'icon_027.png' THEN 'herb_shiso_red.png'
    WHEN 'icon_028.png' THEN 'onion_scallion.png'
    WHEN 'icon_029.png' THEN 'stem_cauliflower.png'
    WHEN 'icon_030.png' THEN 'herb_shiso.png'
    WHEN 'icon_031.png' THEN 'onion_chive.png'
    WHEN 'icon_032.png' THEN 'onion_garlic.png'
    WHEN 'icon_033.png' THEN 'herb_myoga.png'
    WHEN 'icon_034.png' THEN 'herb_myoga.png'
    WHEN 'icon_035.png' THEN 'fruitveg_zucchini.png'
    WHEN 'icon_036.png' THEN 'leaf_cabbage.png'
    WHEN 'icon_037.png' THEN 'leaf_chinese_cabbage.png'
    WHEN 'icon_038.png' THEN 'leaf_greens_ruffled.png'
    WHEN 'icon_039.png' THEN 'root_daikon.png'
    WHEN 'icon_040.png' THEN 'leaf_cabbage.png'
    WHEN 'icon_041.png' THEN 'leaf_chinese_cabbage.png'
    WHEN 'icon_042.png' THEN 'leaf_komatsuna.png'
    WHEN 'icon_043.png' THEN 'root_daikon.png'
    WHEN 'icon_044.png' THEN 'herb_basil.png'
    WHEN 'icon_045.png' THEN 'herb_basil.png'
    WHEN 'icon_046.png' THEN 'stem_sprout.png'
    WHEN 'icon_047.png' THEN 'leaf_spinach.png'
    WHEN 'icon_048.png' THEN 'fruitveg_chili_pair.png'
    WHEN 'icon_049.png' THEN 'stem_bean_sprout.png'
    WHEN 'icon_050.png' THEN 'leaf_greens_round.png'
    WHEN 'icon_051.png' THEN 'herb_mitsuba.png'
    WHEN 'icon_052.png' THEN 'fruitveg_chili.png'
    WHEN 'icon_053.png' THEN 'leaf_shungiku.png'
    WHEN 'icon_054.png' THEN 'tuber_sweet_potato.png'
    WHEN 'icon_055.png' THEN 'herb_coriander.png'
    WHEN 'icon_056.png' THEN 'herb_parsley.png'
    WHEN 'icon_057.png' THEN 'leaf_leaf_lettuce.png'
    WHEN 'icon_058.png' THEN 'leaf_romaine.png'
    WHEN 'icon_059.png' THEN 'leaf_bok_choy.png'
    WHEN 'icon_060.png' THEN 'leaf_lettuce.png'
    WHEN 'icon_061.png' THEN 'root_burdock.png'
    WHEN 'icon_062.png' THEN 'leaf_kale.png'
    WHEN 'icon_063.png' THEN 'stem_asparagus.png'
    WHEN 'icon_064.png' THEN 'onion_leek.png'
    WHEN 'icon_065.png' THEN 'onion_spring_onion.png'
    WHEN 'icon_066.png' THEN 'onion_onion.png'
    WHEN 'icon_067.png' THEN 'stem_bamboo_shoot.png'
    WHEN 'icon_068.png' THEN 'herb_bay_leaf.png'
    WHEN 'icon_069.png' THEN 'root_turnip_purple_small.png'
    WHEN 'icon_070.png' THEN 'root_turnip_purple.png'
    WHEN 'icon_071.png' THEN 'root_carrot.png'
    WHEN 'icon_072.png' THEN 'root_ginger.png'
    WHEN 'icon_073.png' THEN 'root_ginger.png'
    WHEN 'icon_074.png' THEN 'tuber_potato.png'
    WHEN 'icon_075.png' THEN 'root_ginger.png'
    WHEN 'icon_076.png' THEN 'onion_rakkyo.png'
    WHEN 'icon_077.png' THEN 'onion_rakkyo.png'
    WHEN 'icon_078.png' THEN 'mushroom_kikurage.png'
    WHEN 'icon_079.png' THEN 'mushroom_maitake.png'
    WHEN 'icon_080.png' THEN 'mushroom_enoki.png'
    WHEN 'icon_081.png' THEN 'mushroom_shimeji.png'
    WHEN 'icon_082.png' THEN 'mushroom_shiitake.png'
    WHEN 'icon_083.png' THEN 'mushroom_nameko.png'
    WHEN 'icon_084.png' THEN 'mushroom_eringi.png'
    WHEN 'icon_085.png' THEN 'leaf_mizuna.png'
    WHEN 'icon_086.png' THEN 'stem_celery.png'
    WHEN 'icon_087.png' THEN 'stem_broccoli_stick.png'
    WHEN 'icon_088.png' THEN 'tuber_taro.png'
    WHEN 'icon_089.png' THEN 'root_turnip_white.png'
    WHEN 'icon_090.png' THEN 'fruitveg_tomato_mini.png'
    WHEN 'icon_091.png' THEN 'fruitveg_pumpkin.png'
    WHEN 'icon_092.png' THEN 'fruitveg_eggplant_long.png'
    WHEN 'icon_093.png' THEN 'fruitveg_eggplant_round.png'
    WHEN 'icon_094.png' THEN 'onion_red_onion.png'
    WHEN 'icon_095.png' THEN 'leaf_sunny_lettuce.png'
    WHEN 'icon_096.png' THEN 'fruit_mikan.png'
    WHEN 'icon_097.png' THEN 'fruit_amanatsu.png'
END
WHERE icon_path IN ('icon_001.png', 'icon_002.png', 'icon_003.png', 'icon_004.png', 'icon_005.png', 'icon_006.png', 'icon_007.png', 'icon_008.png', 'icon_009.png', 'icon_010.png', 'icon_011.png', 'icon_012.png', 'icon_013.png', 'icon_014.png', 'icon_015.png', 'icon_016.png', 'icon_017.png', 'icon_018.png', 'icon_019.png', 'icon_020.png', 'icon_021.png', 'icon_022.png', 'icon_023.png', 'icon_024.png', 'icon_025.png', 'icon_026.png', 'icon_027.png', 'icon_028.png', 'icon_029.png', 'icon_030.png', 'icon_031.png', 'icon_032.png', 'icon_033.png', 'icon_034.png', 'icon_035.png', 'icon_036.png', 'icon_037.png', 'icon_038.png', 'icon_039.png', 'icon_040.png', 'icon_041.png', 'icon_042.png', 'icon_043.png', 'icon_044.png', 'icon_045.png', 'icon_046.png', 'icon_047.png', 'icon_048.png', 'icon_049.png', 'icon_050.png', 'icon_051.png', 'icon_052.png', 'icon_053.png', 'icon_054.png', 'icon_055.png', 'icon_056.png', 'icon_057.png', 'icon_058.png', 'icon_059.png', 'icon_060.png', 'icon_061.png', 'icon_062.png', 'icon_063.png', 'icon_064.png', 'icon_065.png', 'icon_066.png', 'icon_067.png', 'icon_068.png', 'icon_069.png', 'icon_070.png', 'icon_071.png', 'icon_072.png', 'icon_073.png', 'icon_074.png', 'icon_075.png', 'icon_076.png', 'icon_077.png', 'icon_078.png', 'icon_079.png', 'icon_080.png', 'icon_081.png', 'icon_082.png', 'icon_083.png', 'icon_084.png', 'icon_085.png', 'icon_086.png', 'icon_087.png', 'icon_088.png', 'icon_089.png', 'icon_090.png', 'icon_091.png', 'icon_092.png', 'icon_093.png', 'icon_094.png', 'icon_095.png', 'icon_096.png', 'icon_097.png');

UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_001.png"', '"fruitveg_tomato.png"') WHERE instr(canvas_data, '"icon_001.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_002.png"', '"fruitveg_eggplant.png"') WHERE instr(canvas_data, '"icon_002.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_003.png"', '"fruitveg_green_pepper.png"') WHERE instr(canvas_data, '"icon_003.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_004.png"', '"fruitveg_paprika.png"') WHERE instr(canvas_data, '"icon_004.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_005.png"', '"fruitveg_shishito.png"') WHERE instr(canvas_data, '"icon_005.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_006.png"', '"fruitveg_chili.png"') WHERE instr(canvas_data, '"icon_006.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_007.png"', '"fruitveg_cucumber.png"') WHERE instr(canvas_data, '"icon_007.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_008.png"', '"fruit_watermelon.png"') WHERE instr(canvas_data, '"icon_008.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_009.png"', '"fruitveg_wax_gourd.png"') WHERE instr(canvas_data, '"icon_009.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_010.png"', '"fruitveg_pumpkin_orange.png"') WHERE instr(canvas_data, '"icon_010.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_011.png"', '"fruitveg_cucumber_light.png"') WHERE instr(canvas_data, '"icon_011.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_012.png"', '"bean_peanut.png"') WHERE instr(canvas_data, '"icon_012.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_013.png"', '"bean_peanut.png"') WHERE instr(canvas_data, '"icon_013.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_014.png"', '"bean_edamame.png"') WHERE instr(canvas_data, '"icon_014.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_015.png"', '"bean_green.png"') WHERE instr(canvas_data, '"icon_015.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_016.png"', '"bean_kidney.png"') WHERE instr(canvas_data, '"icon_016.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_017.png"', '"bean_ingen.png"') WHERE instr(canvas_data, '"icon_017.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_018.png"', '"bean_soybean.png"') WHERE instr(canvas_data, '"icon_018.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_019.png"', '"bean_soybean.png"') WHERE instr(canvas_data, '"icon_019.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_020.png"', '"bean_fava.png"') WHERE instr(canvas_data, '"icon_020.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_021.png"', '"bean_fava.png"') WHERE instr(canvas_data, '"icon_021.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_022.png"', '"bean_snap_pea.png"') WHERE instr(canvas_data, '"icon_022.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_023.png"', '"fruitveg_corn.png"') WHERE instr(canvas_data, '"icon_023.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_024.png"', '"fruitveg_okra.png"') WHERE instr(canvas_data, '"icon_024.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_025.png"', '"stem_broccoli.png"') WHERE instr(canvas_data, '"icon_025.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_026.png"', '"stem_cauliflower.png"') WHERE instr(canvas_data, '"icon_026.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_027.png"', '"herb_shiso_red.png"') WHERE instr(canvas_data, '"icon_027.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_028.png"', '"onion_scallion.png"') WHERE instr(canvas_data, '"icon_028.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_029.png"', '"stem_cauliflower.png"') WHERE instr(canvas_data, '"icon_029.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_030.png"', '"herb_shiso.png"') WHERE instr(canvas_data, '"icon_030.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_031.png"', '"onion_chive.png"') WHERE instr(canvas_data, '"icon_031.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_032.png"', '"onion_garlic.png"') WHERE instr(canvas_data, '"icon_032.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_033.png"', '"herb_myoga.png"') WHERE instr(canvas_data, '"icon_033.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_034.png"', '"herb_myoga.png"') WHERE instr(canvas_data, '"icon_034.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_035.png"', '"fruitveg_zucchini.png"') WHERE instr(canvas_data, '"icon_035.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_036.png"', '"leaf_cabbage.png"') WHERE instr(canvas_data, '"icon_036.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_037.png"', '"leaf_chinese_cabbage.png"') WHERE instr(canvas_data, '"icon_037.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_038.png"', '"leaf_greens_ruffled.png"') WHERE instr(canvas_data, '"icon_038.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_039.png"', '"root_daikon.png"') WHERE instr(canvas_data, '"icon_039.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_040.png"', '"leaf_cabbage.png"') WHERE instr(canvas_data, '"icon_040.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_041.png"', '"leaf_chinese_cabbage.png"') WHERE instr(canvas_data, '"icon_041.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_042.png"', '"leaf_komatsuna.png"') WHERE instr(canvas_data, '"icon_042.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_043.png"', '"root_daikon.png"') WHERE instr(canvas_data, '"icon_043.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_044.png"', '"herb_basil.png"') WHERE instr(canvas_data, '"icon_044.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_045.png"', '"herb_basil.png"') WHERE instr(canvas_data, '"icon_045.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_046.png"', '"stem_sprout.png"') WHERE instr(canvas_data, '"icon_046.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_047.png"', '"leaf_spinach.png"') WHERE instr(canvas_data, '"icon_047.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_048.png"', '"fruitveg_chili_pair.png"') WHERE instr(canvas_data, '"icon_048.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_049.png"', '"stem_bean_sprout.png"') WHERE instr(canvas_data, '"icon_049.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_050.png"', '"leaf_greens_round.png"') WHERE instr(canvas_data, '"icon_050.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_051.png"', '"herb_mitsuba.png"') WHERE instr(canvas_data, '"icon_051.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_052.png"', '"fruitveg_chili.png"') WHERE instr(canvas_data, '"icon_052.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_053.png"', '"leaf_shungiku.png"') WHERE instr(canvas_data, '"icon_053.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_054.png"', '"tuber_sweet_potato.png"') WHERE instr(canvas_data, '"icon_054.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_055.png"', '"herb_coriander.png"') WHERE instr(canvas_data, '"icon_055.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_056.png"', '"herb_parsley.png"') WHERE instr(canvas_data, '"icon_056.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_057.png"', '"leaf_leaf_lettuce.png"') WHERE instr(canvas_data, '"icon_057.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_058.png"', '"leaf_romaine.png"') WHERE instr(canvas_data, '"icon_058.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_059.png"', '"leaf_bok_choy.png"') WHERE instr(canvas_data, '"icon_059.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_060.png"', '"leaf_lettuce.png"') WHERE instr(canvas_data, '"icon_060.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_061.png"', '"root_burdock.png"') WHERE instr(canvas_data, '"icon_061.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_062.png"', '"leaf_kale.png"') WHERE instr(canvas_data, '"icon_062.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_063.png"', '"stem_asparagus.png"') WHERE instr(canvas_data, '"icon_063.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_064.png"', '"onion_leek.png"') WHERE instr(canvas_data, '"icon_064.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_065.png"', '"onion_spring_onion.png"') WHERE instr(canvas_data, '"icon_065.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_066.png"', '"onion_onion.png"') WHERE instr(canvas_data, '"icon_066.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_067.png"', '"stem_bamboo_shoot.png"') WHERE instr(canvas_data, '"icon_067.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_068.png"', '"herb_bay_leaf.png"') WHERE instr(canvas_data, '"icon_068.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_069.png"', '"root_turnip_purple_small.png"') WHERE instr(canvas_data, '"icon_069.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_070.png"', '"root_turnip_purple.png"') WHERE instr(canvas_data, '"icon_070.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_071.png"', '"root_carrot.png"') WHERE instr(canvas_data, '"icon_071.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_072.png"', '"root_ginger.png"') WHERE instr(canvas_data, '"icon_072.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_073.png"', '"root_ginger.png"') WHERE instr(canvas_data, '"icon_073.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_074.png"', '"tuber_potato.png"') WHERE instr(canvas_data, '"icon_074.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_075.png"', '"root_ginger.png"') WHERE instr(canvas_data, '"icon_075.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_076.png"', '"onion_rakkyo.png"') WHERE instr(canvas_data, '"icon_076.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_077.png"', '"onion_rakkyo.png"') WHERE instr(canvas_data, '"icon_077.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_078.png"', '"mushroom_kikurage.png"') WHERE instr(canvas_data, '"icon_078.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_079.png"', '"mushroom_maitake.png"') WHERE instr(canvas_data, '"icon_079.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_080.png"', '"mushroom_enoki.png"') WHERE instr(canvas_data, '"icon_080.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_081.png"', '"mushroom_shimeji.png"') WHERE instr(canvas_data, '"icon_081.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_082.png"', '"mushroom_shiitake.png"') WHERE instr(canvas_data, '"icon_082.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_083.png"', '"mushroom_nameko.png"') WHERE instr(canvas_data, '"icon_083.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_084.png"', '"mushroom_eringi.png"') WHERE instr(canvas_data, '"icon_084.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_085.png"', '"leaf_mizuna.png"') WHERE instr(canvas_data, '"icon_085.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_086.png"', '"stem_celery.png"') WHERE instr(canvas_data, '"icon_086.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_087.png"', '"stem_broccoli_stick.png"') WHERE instr(canvas_data, '"icon_087.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_088.png"', '"tuber_taro.png"') WHERE instr(canvas_data, '"icon_088.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_089.png"', '"root_turnip_white.png"') WHERE instr(canvas_data, '"icon_089.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_090.png"', '"fruitveg_tomato_mini.png"') WHERE instr(canvas_data, '"icon_090.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_091.png"', '"fruitveg_pumpkin.png"') WHERE instr(canvas_data, '"icon_091.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_092.png"', '"fruitveg_eggplant_long.png"') WHERE instr(canvas_data, '"icon_092.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_093.png"', '"fruitveg_eggplant_round.png"') WHERE instr(canvas_data, '"icon_093.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_094.png"', '"onion_red_onion.png"') WHERE instr(canvas_data, '"icon_094.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_095.png"', '"leaf_sunny_lettuce.png"') WHERE instr(canvas_data, '"icon_095.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_096.png"', '"fruit_mikan.png"') WHERE instr(canvas_data, '"icon_096.png"') > 0;
UPDATE locations SET canvas_data = REPLACE(canvas_data, '"icon_097.png"', '"fruit_amanatsu.png"') WHERE instr(canvas_data, '"icon_097.png"') > 0;

UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_001.png"', '"fruitveg_tomato.png"') WHERE instr(canvas_snapshot, '"icon_001.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_002.png"', '"fruitveg_eggplant.png"') WHERE instr(canvas_snapshot, '"icon_002.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_003.png"', '"fruitveg_green_pepper.png"') WHERE instr(canvas_snapshot, '"icon_003.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_004.png"', '"fruitveg_paprika.png"') WHERE instr(canvas_snapshot, '"icon_004.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_005.png"', '"fruitveg_shishito.png"') WHERE instr(canvas_snapshot, '"icon_005.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_006.png"', '"fruitveg_chili.png"') WHERE instr(canvas_snapshot, '"icon_006.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_007.png"', '"fruitveg_cucumber.png"') WHERE instr(canvas_snapshot, '"icon_007.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_008.png"', '"fruit_watermelon.png"') WHERE instr(canvas_snapshot, '"icon_008.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_009.png"', '"fruitveg_wax_gourd.png"') WHERE instr(canvas_snapshot, '"icon_009.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_010.png"', '"fruitveg_pumpkin_orange.png"') WHERE instr(canvas_snapshot, '"icon_010.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_011.png"', '"fruitveg_cucumber_light.png"') WHERE instr(canvas_snapshot, '"icon_011.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_012.png"', '"bean_peanut.png"') WHERE instr(canvas_snapshot, '"icon_012.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_013.png"', '"bean_peanut.png"') WHERE instr(canvas_snapshot, '"icon_013.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_014.png"', '"bean_edamame.png"') WHERE instr(canvas_snapshot, '"icon_014.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_015.png"', '"bean_green.png"') WHERE instr(canvas_snapshot, '"icon_015.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_016.png"', '"bean_kidney.png"') WHERE instr(canvas_snapshot, '"icon_016.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_017.png"', '"bean_ingen.png"') WHERE instr(canvas_snapshot, '"icon_017.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_018.png"', '"bean_soybean.png"') WHERE instr(canvas_snapshot, '"icon_018.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_019.png"', '"bean_soybean.png"') WHERE instr(canvas_snapshot, '"icon_019.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_020.png"', '"bean_fava.png"') WHERE instr(canvas_snapshot, '"icon_020.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_021.png"', '"bean_fava.png"') WHERE instr(canvas_snapshot, '"icon_021.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_022.png"', '"bean_snap_pea.png"') WHERE instr(canvas_snapshot, '"icon_022.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_023.png"', '"fruitveg_corn.png"') WHERE instr(canvas_snapshot, '"icon_023.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_024.png"', '"fruitveg_okra.png"') WHERE instr(canvas_snapshot, '"icon_024.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_025.png"', '"stem_broccoli.png"') WHERE instr(canvas_snapshot, '"icon_025.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_026.png"', '"stem_cauliflower.png"') WHERE instr(canvas_snapshot, '"icon_026.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_027.png"', '"herb_shiso_red.png"') WHERE instr(canvas_snapshot, '"icon_027.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_028.png"', '"onion_scallion.png"') WHERE instr(canvas_snapshot, '"icon_028.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_029.png"', '"stem_cauliflower.png"') WHERE instr(canvas_snapshot, '"icon_029.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_030.png"', '"herb_shiso.png"') WHERE instr(canvas_snapshot, '"icon_030.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_031.png"', '"onion_chive.png"') WHERE instr(canvas_snapshot, '"icon_031.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_032.png"', '"onion_garlic.png"') WHERE instr(canvas_snapshot, '"icon_032.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_033.png"', '"herb_myoga.png"') WHERE instr(canvas_snapshot, '"icon_033.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_034.png"', '"herb_myoga.png"') WHERE instr(canvas_snapshot, '"icon_034.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_035.png"', '"fruitveg_zucchini.png"') WHERE instr(canvas_snapshot, '"icon_035.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_036.png"', '"leaf_cabbage.png"') WHERE instr(canvas_snapshot, '"icon_036.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_037.png"', '"leaf_chinese_cabbage.png"') WHERE instr(canvas_snapshot, '"icon_037.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_038.png"', '"leaf_greens_ruffled.png"') WHERE instr(canvas_snapshot, '"icon_038.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_039.png"', '"root_daikon.png"') WHERE instr(canvas_snapshot, '"icon_039.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_040.png"', '"leaf_cabbage.png"') WHERE instr(canvas_snapshot, '"icon_040.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_041.png"', '"leaf_chinese_cabbage.png"') WHERE instr(canvas_snapshot, '"icon_041.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_042.png"', '"leaf_komatsuna.png"') WHERE instr(canvas_snapshot, '"icon_042.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_043.png"', '"root_daikon.png"') WHERE instr(canvas_snapshot, '"icon_043.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_044.png"', '"herb_basil.png"') WHERE instr(canvas_snapshot, '"icon_044.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_045.png"', '"herb_basil.png"') WHERE instr(canvas_snapshot, '"icon_045.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_046.png"', '"stem_sprout.png"') WHERE instr(canvas_snapshot, '"icon_046.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_047.png"', '"leaf_spinach.png"') WHERE instr(canvas_snapshot, '"icon_047.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_048.png"', '"fruitveg_chili_pair.png"') WHERE instr(canvas_snapshot, '"icon_048.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_049.png"', '"stem_bean_sprout.png"') WHERE instr(canvas_snapshot, '"icon_049.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_050.png"', '"leaf_greens_round.png"') WHERE instr(canvas_snapshot, '"icon_050.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_051.png"', '"herb_mitsuba.png"') WHERE instr(canvas_snapshot, '"icon_051.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_052.png"', '"fruitveg_chili.png"') WHERE instr(canvas_snapshot, '"icon_052.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_053.png"', '"leaf_shungiku.png"') WHERE instr(canvas_snapshot, '"icon_053.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_054.png"', '"tuber_sweet_potato.png"') WHERE instr(canvas_snapshot, '"icon_054.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_055.png"', '"herb_coriander.png"') WHERE instr(canvas_snapshot, '"icon_055.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_056.png"', '"herb_parsley.png"') WHERE instr(canvas_snapshot, '"icon_056.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_057.png"', '"leaf_leaf_lettuce.png"') WHERE instr(canvas_snapshot, '"icon_057.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_058.png"', '"leaf_romaine.png"') WHERE instr(canvas_snapshot, '"icon_058.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_059.png"', '"leaf_bok_choy.png"') WHERE instr(canvas_snapshot, '"icon_059.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_060.png"', '"leaf_lettuce.png"') WHERE instr(canvas_snapshot, '"icon_060.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_061.png"', '"root_burdock.png"') WHERE instr(canvas_snapshot, '"icon_061.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_062.png"', '"leaf_kale.png"') WHERE instr(canvas_snapshot, '"icon_062.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_063.png"', '"stem_asparagus.png"') WHERE instr(canvas_snapshot, '"icon_063.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_064.png"', '"onion_leek.png"') WHERE instr(canvas_snapshot, '"icon_064.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_065.png"', '"onion_spring_onion.png"') WHERE instr(canvas_snapshot, '"icon_065.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_066.png"', '"onion_onion.png"') WHERE instr(canvas_snapshot, '"icon_066.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_067.png"', '"stem_bamboo_shoot.png"') WHERE instr(canvas_snapshot, '"icon_067.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_068.png"', '"herb_bay_leaf.png"') WHERE instr(canvas_snapshot, '"icon_068.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_069.png"', '"root_turnip_purple_small.png"') WHERE instr(canvas_snapshot, '"icon_069.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_070.png"', '"root_turnip_purple.png"') WHERE instr(canvas_snapshot, '"icon_070.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_071.png"', '"root_carrot.png"') WHERE instr(canvas_snapshot, '"icon_071.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_072.png"', '"root_ginger.png"') WHERE instr(canvas_snapshot, '"icon_072.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_073.png"', '"root_ginger.png"') WHERE instr(canvas_snapshot, '"icon_073.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_074.png"', '"tuber_potato.png"') WHERE instr(canvas_snapshot, '"icon_074.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_075.png"', '"root_ginger.png"') WHERE instr(canvas_snapshot, '"icon_075.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_076.png"', '"onion_rakkyo.png"') WHERE instr(canvas_snapshot, '"icon_076.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_077.png"', '"onion_rakkyo.png"') WHERE instr(canvas_snapshot, '"icon_077.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_078.png"', '"mushroom_kikurage.png"') WHERE instr(canvas_snapshot, '"icon_078.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_079.png"', '"mushroom_maitake.png"') WHERE instr(canvas_snapshot, '"icon_079.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_080.png"', '"mushroom_enoki.png"') WHERE instr(canvas_snapshot, '"icon_080.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_081.png"', '"mushroom_shimeji.png"') WHERE instr(canvas_snapshot, '"icon_081.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_082.png"', '"mushroom_shiitake.png"') WHERE instr(canvas_snapshot, '"icon_082.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_083.png"', '"mushroom_nameko.png"') WHERE instr(canvas_snapshot, '"icon_083.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_084.png"', '"mushroom_eringi.png"') WHERE instr(canvas_snapshot, '"icon_084.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_085.png"', '"leaf_mizuna.png"') WHERE instr(canvas_snapshot, '"icon_085.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_086.png"', '"stem_celery.png"') WHERE instr(canvas_snapshot, '"icon_086.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_087.png"', '"stem_broccoli_stick.png"') WHERE instr(canvas_snapshot, '"icon_087.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_088.png"', '"tuber_taro.png"') WHERE instr(canvas_snapshot, '"icon_088.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_089.png"', '"root_turnip_white.png"') WHERE instr(canvas_snapshot, '"icon_089.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_090.png"', '"fruitveg_tomato_mini.png"') WHERE instr(canvas_snapshot, '"icon_090.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_091.png"', '"fruitveg_pumpkin.png"') WHERE instr(canvas_snapshot, '"icon_091.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_092.png"', '"fruitveg_eggplant_long.png"') WHERE instr(canvas_snapshot, '"icon_092.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_093.png"', '"fruitveg_eggplant_round.png"') WHERE instr(canvas_snapshot, '"icon_093.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_094.png"', '"onion_red_onion.png"') WHERE instr(canvas_snapshot, '"icon_094.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_095.png"', '"leaf_sunny_lettuce.png"') WHERE instr(canvas_snapshot, '"icon_095.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_096.png"', '"fruit_mikan.png"') WHERE instr(canvas_snapshot, '"icon_096.png"') > 0;
UPDATE plantings SET canvas_snapshot = REPLACE(canvas_snapshot, '"icon_097.png"', '"fruit_amanatsu.png"') WHERE instr(canvas_snapshot, '"icon_097.png"') > 0;
