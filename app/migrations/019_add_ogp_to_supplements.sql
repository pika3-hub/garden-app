-- OGP キャッシュカラムを supplements に追加
ALTER TABLE supplements ADD COLUMN ogp_image TEXT;
ALTER TABLE supplements ADD COLUMN ogp_title TEXT;
ALTER TABLE supplements ADD COLUMN ogp_description TEXT;
