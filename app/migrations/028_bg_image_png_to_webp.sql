-- 見取り図の背景画像: png 時代の名前を webp に置き換える
-- Migration: 028_bg_image_png_to_webp
--
-- 背景画像は 2026-03-25 に png から webp に変換した（同じ名前で拡張子だけ変わった）が、
-- locations.bg_image に残った古い名前は置き換えていなかった。同梱の名前（bg_image_*.png）だけを対象にする。
-- 起動のたびに実行されるが、置き換えた後は該当がなくなるので何も変わらない。
UPDATE locations
SET bg_image = substr(bg_image, 1, length(bg_image) - 4) || '.webp'
WHERE bg_image GLOB 'bg_image_*.png';
