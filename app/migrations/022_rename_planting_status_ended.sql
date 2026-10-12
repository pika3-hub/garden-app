-- 植え付けの状態「栽培終了」の内部値を harvested から ended に変更
-- Migration: 022_rename_planting_status_ended
--
-- 画面の表記は「栽培終了」なのに内部値が harvested（収穫済み）だったため、
-- API を通して Hermes に「収穫済み」と受け取られていた。何度実行しても結果は同じ。
UPDATE plantings SET status = 'ended' WHERE status = 'harvested';
