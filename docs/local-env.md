# 実環境の固有値（git 管理外）

公開リポジトリの文書では記号で書いている値の実際の値。`.gitignore` 済み。

| 記号 | 実際の値 | 備考 |
|---|---|---|
| `<サーバーのIP>` | 192.168.11.24 | Ubuntu Server（ホスト名 pika3-server）。2026-10-11 から本番（garden-app.service）と Hermes |
| `<メインPCのIP>` | 192.168.11.10 | Windows。開発用（DB は `instance/garden.db.moved-to-ubuntu` に退避済み） |
| ルーター | 192.168.11.1 | DHCP の手動割当で上の2台の IP を固定 |
| `<LANの範囲>` | 192.168.11.0/24 | ufw で 22・5000 を許可 |
| `<user>` / Hermes の実行ユーザー | pika3 | sudo はパスワード必須。ufw の遮断ルールは `--uid-owner pika3` |
| `<リポジトリURL>` | https://github.com/pika3-hub/garden-app | 公開 |
| `<転送用フォルダ>` | D:/garden-transfer（Git Bash では /d/garden-transfer） | 移設時の tar の置き場 |
| `<リポジトリのフォルダ>` | D:\workspace\garden-app | メインPC |
