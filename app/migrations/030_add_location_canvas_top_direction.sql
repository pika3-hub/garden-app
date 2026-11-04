-- 場所に「見取り図の上の方角」を足す
-- Migration: 030_add_location_canvas_top_direction
--
-- 見取り図の上がどの方角かを北/東/南/西で持つ（NULL は未設定。エリアを上・下・左・右で呼ぶ）。
ALTER TABLE locations ADD COLUMN canvas_top_direction TEXT DEFAULT NULL;
