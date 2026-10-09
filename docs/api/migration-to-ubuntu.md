# Ubuntu（エージェント PC）への移設手順

メイン PC を落としていても API と Web 画面が使えるよう、アプリをエージェント PC（Ubuntu Server、192.168.11.24）へ移す手順。
アプリ側のコードは変更不要で、`.env` とサービス登録だけで移せるように作ってある。

移設後の形:

```
スマホ ──LAN──▶ 0.0.0.0:5000    Web 画面（認証なし）
Hermes ──────▶ 127.0.0.1:5001  API（Bearer 必須。LAN からは見えない）
/opt/garden-app/ … ユーザー garden が所有・0700。Hermes の実行ユーザーは読めない
```

**最重要**: Hermes はシェルを実行できるため、同じ PC に DB があると API を通さずに読み書き・削除できてしまう。
アプリを専用ユーザー `garden` で動かし、Hermes の実行ユーザーからはアプリのフォルダを読めないようにする。

## 1. 専用ユーザーとフォルダ

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin garden
sudo mkdir -p /opt/garden-app
sudo chown garden:garden /opt/garden-app
sudo chmod 700 /opt/garden-app
```

Hermes の実行ユーザー（以下 `hermes`）で確認:

```bash
ls /opt/garden-app        # → Permission denied であること
sudo -l                   # → sudo の権限が無いこと（あれば外す）
```

## 2. コードと依存関係

```bash
sudo -u garden -H bash -c '
  curl -LsSf https://astral.sh/uv/install.sh | sh
  git clone <リポジトリURL> /opt/garden-app
  cd /opt/garden-app && ~/.local/bin/uv sync
'
```

## 3. `.env`

`/opt/garden-app/.env`（所有者 garden、`chmod 600`）:

```
FLASK_ENV=production
SECRET_KEY=<ランダムな文字列>
HOST=0.0.0.0
API_HOST=127.0.0.1
API_PORT=5001
API_TOKEN=<32文字以上のトークン>
DATABASE=/opt/garden-app/instance/garden.db
WEB_BASE_URL=http://192.168.11.24:5000
ANTHROPIC_API_KEY=<使う場合>
```

## 4. データの移行

1. Windows 側で `server.py` を停止する（以後 Windows 側では起動しない。二重運用でデータが分岐するため）
2. Windows 側の `instance/garden.db` と `app/static/uploads/` を Ubuntu へコピー:

   ```bash
   # Windows の Git Bash から
   scp instance/garden.db <user>@192.168.11.24:/tmp/
   scp -r app/static/uploads <user>@192.168.11.24:/tmp/uploads
   ```

3. Ubuntu 側で配置して所有者を変更:

   ```bash
   sudo mkdir -p /opt/garden-app/instance
   sudo mv /tmp/garden.db /opt/garden-app/instance/
   sudo rsync -a /tmp/uploads/ /opt/garden-app/app/static/uploads/
   sudo chown -R garden:garden /opt/garden-app
   ```

4. Windows 側の DB は誤って起動しないよう名前を変えて退避する（例 `garden.db.moved-to-ubuntu`）

## 5. systemd

`/etc/systemd/system/garden-app.service`:

```ini
[Unit]
Description=Garden app (web :5000 / api 127.0.0.1:5001)
After=network.target

[Service]
User=garden
Group=garden
WorkingDirectory=/opt/garden-app
EnvironmentFile=/opt/garden-app/.env
ExecStart=/home/garden/.local/bin/uv run python server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now garden-app
journalctl -u garden-app -f      # 監査ログ（app.api）もここに出る
```

## 6. ファイアウォール（ufw）

```bash
sudo ufw allow from 192.168.11.0/24 to any port 5000 proto tcp
sudo ufw enable
```

5001 は 127.0.0.1 で待ち受けるので開けない。

## 7. バックアップ

garden ユーザーの crontab（`sudo -u garden crontab -e`）:

```cron
15 3 * * * sqlite3 /opt/garden-app/instance/garden.db ".backup '/var/backups/garden/garden-$(date +\%a).db'"
30 3 * * * rsync -a --delete /opt/garden-app/app/static/uploads/ /var/backups/garden/uploads/
```

（`sudo mkdir -p /var/backups/garden && sudo chown garden:garden /var/backups/garden && sudo chmod 700 /var/backups/garden`。曜日ごとに7世代残る）

## 8. 動作確認と Hermes 側の切り替え

```bash
curl -sS -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/health   # Ubuntu 上で
curl -sS -m 5 http://192.168.11.24:5001/                                      # 別の端末から → 接続できない
```

スマホで `http://192.168.11.24:5000/` を開き、件数が移行前と同じことを確認する。

Hermes 側の環境変数を変更する:

```
GARDEN_API_URL=http://127.0.0.1:5001/api/v1
```

Windows 側のファイアウォールのルール（[`firewall-windows.md`](firewall-windows.md)）は削除してよい。

## 9. 更新の手順

```bash
sudo -u garden -H bash -c 'cd /opt/garden-app && git pull && ~/.local/bin/uv sync'
sudo systemctl restart garden-app
```

起動時にマイグレーションが自動で走るので、更新前にバックアップ（手順 7 のコマンドを手で実行）を取る。
