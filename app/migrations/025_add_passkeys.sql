-- パスキー（WebAuthn の資格情報）の保存テーブル
-- Migration: 025_add_passkeys
--
-- credential_id / public_key は base64url 文字列で保存する。
-- 起動のたびに実行されるので IF NOT EXISTS で何度実行しても同じ結果にする。
CREATE TABLE IF NOT EXISTS passkeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT (datetime('now', '+9 hours')),
    last_used_at TIMESTAMP
);
