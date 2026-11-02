-- 見取り図の背景画像の作り直し: 場所の背景を新しい名前に付け替える
-- Migration: 028_rename_location_bg_images
--
-- 連番の bg_image_NNN.webp（21 枚）をやめ、中身が分かる名前の 13 枚にした。既定は soil.webp。
-- 表にない古い名前（bg_image_001 など、bg_image_default）と NULL は soil.webp にする。
-- 起動のたびに実行されるので、古い名前と NULL だけを対象にする（新しい名前・将来足した名前は書き換えない）。
UPDATE locations SET bg_image = CASE bg_image
    WHEN 'bg_image_005.webp' THEN 'soil.webp'
    WHEN 'bg_image_012.webp' THEN 'ridges_3.webp'
    WHEN 'bg_image_008.webp' THEN 'ridges_6.webp'
    WHEN 'bg_image_015.webp' THEN 'weeds.webp'
    WHEN 'bg_image_014.webp' THEN 'grass_edge.webp'
    WHEN 'bg_image_010.webp' THEN 'brick_bed.webp'
    WHEN 'bg_image_011.webp' THEN 'greenhouse.webp'
    WHEN 'bg_image_018.webp' THEN 'planter_long.webp'
    WHEN 'bg_image_019.webp' THEN 'planter_round.webp'
    WHEN 'bg_image_020.webp' THEN 'seedling_tray.webp'
    ELSE 'soil.webp'
END
WHERE bg_image IS NULL OR bg_image GLOB 'bg_image_*';
