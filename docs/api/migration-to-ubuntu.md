# Ubuntu（エージェント PC）への移設手順

メイン PC を落としていても API と Web 画面が使えるよう、アプリをエージェント PC（Ubuntu Server、192.168.11.24）へ移す手順。
アプリ側のコードは変更不要で、`.env` とサービス登録だけで移せるように作ってある。

移設後の形:

```
スマホ ──LAN──▶ 0.0.0.0:5000    Web 画面（認証なし）
Hermes ──────▶ 127.0.0.1:5001  API（Bearer 必須。LAN からは見えない）
/opt/garden-app/ … ユーザー garden が所有・0700。Hermes の実行ユーザーは読めない
```

**最重要**: Hermes はシェルを実行できるため、同じ PC にあるものには API を通さずに触れてしまう。次の2つを両方行う。

1. **DB・ファイル**: アプリを専用ユーザー `garden` で動かし、Hermes の実行ユーザーからはアプリのフォルダを読めないようにする（手順 1）
2. **Web 画面（認証なし・削除もできる）**: 同じ PC からは `127.0.0.1:5000` や自分の LAN IP の 5000 番に接続できてしまう（ufw はループバックや自ホスト宛てを止めない）。Hermes の実行ユーザーから 5000 番への接続を OS で拒否する（手順 6）

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

## 6. ファイアウォール（ufw）と Hermes からの Web 画面の遮断

LAN（スマホ）から Web 画面へ:

```bash
sudo ufw allow from 192.168.11.0/24 to any port 5000 proto tcp
```

5001 は 127.0.0.1 で待ち受けるので開けない。

**Hermes の実行ユーザー（以下 `hermes`）から 5000 番への接続を拒否する**。2026-10-10 時点の .24 では、Hermes は専用ユーザーではなく `pika3` のユーザー systemd サービス（`hermes-gateway.service`）で動いている。そのままなら下の `hermes` は `pika3` に読み替える（`pika3` がサーバー上で `localhost:5000` を開けなくなるだけで、スマホからは使える）。`pika3` は sudo できるため `/opt/garden-app` の権限での保護は弱くなる点に注意。ufw の受信ルールは同じ PC 内の通信を止めないため、送信側でユーザー単位に拒否する。`/etc/ufw/before.rules` の `*filter` セクション内、`COMMIT` の直前に追加:

```
# Hermes の実行ユーザーは Web 画面（認証なし）に接続できない。API（5001）だけを使う
-A ufw-before-output -p tcp --dport 5000 -m owner --uid-owner hermes -j REJECT
```

IPv6 でも同じ行を `/etc/ufw/before6.rules` に追加する。その後:

```bash
sudo ufw enable
sudo ufw reload
```

（宛先を限定していないので、`127.0.0.1`・自分の LAN IP・`localhost` のどれで接続しても拒否される。hermes ユーザーがほかの機器の 5000 番を使う予定があれば `-d` で宛先を自ホストに絞る）

## 7. バックアップ

garden ユーザーの crontab（`sudo -u garden crontab -e`）:

```cron
15 3 * * * sqlite3 /opt/garden-app/instance/garden.db ".backup '/var/backups/garden/garden-$(date +\%a).db'"
30 3 * * * rsync -a --delete /opt/garden-app/app/static/uploads/ /var/backups/garden/uploads/
```

（`sudo mkdir -p /var/backups/garden && sudo chown garden:garden /var/backups/garden && sudo chmod 700 /var/backups/garden`。曜日ごとに7世代残る）

## 8. 動作確認と Hermes 側の切り替え

```bash
curl -sS -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/health   # Ubuntu 上で → {"ok": true, ...}
curl -sS -m 5 http://192.168.11.24:5001/                                      # 別の端末から → 接続できない
sudo -u hermes curl -sS -m 5 http://127.0.0.1:5000/                           # → 拒否されること（Connection refused）
sudo -u hermes curl -sS -m 5 http://192.168.11.24:5000/                       # → 拒否されること
sudo -u hermes curl -sS -m 5 -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/health  # → 成功すること
sudo -u hermes ls /opt/garden-app                                             # → Permission denied
```

スマホで `http://192.168.11.24:5000/` を開き、件数が移行前と同じことを確認する。

Hermes 側の環境変数を変更する。Windows 暫定期から、接続情報は `~/.config/garden-api.env`（`GARDEN_API_URL` と `GARDEN_API_TOKEN`、権限 600）に書き、drop-in `~/.config/systemd/user/hermes-gateway.service.d/garden-api.conf`（`[Service]` に `EnvironmentFile=%h/.config/garden-api.env`）で gateway に渡している。URL の行だけ書き換えて再起動する:

```bash
sed -i 's|^GARDEN_API_URL=.*|GARDEN_API_URL=http://127.0.0.1:5001/api/v1|' ~/.config/garden-api.env
systemctl --user restart hermes-gateway.service
```

ターミナルで `hermes` を直接起動するときは、先に `set -a; . ~/.config/garden-api.env; set +a` で読み込む（サービスの設定は読まれない）。

Windows 側のファイアウォールのルール（[`firewall-windows.md`](firewall-windows.md)）は削除してよい。

## 9. 更新の手順

```bash
sudo -u garden -H bash -c 'cd /opt/garden-app && git pull && ~/.local/bin/uv sync'
sudo systemctl restart garden-app
```

起動時にマイグレーションが自動で走るので、更新前にバックアップ（手順 7 のコマンドを手で実行）を取る。
