# Ubuntu（エージェント PC）への移設手順

メイン PC を落としていても API と Web 画面が使えるよう、アプリをエージェント PC（Ubuntu Server、<サーバーのIP>）へ移す手順。
アプリ側のコードは変更不要で、`.env` とサービス登録だけで移せるように作ってある。

**2026-10-11 にこの手順で移設済み**（Hermes は専用ユーザーにせず、ログイン用のユーザーのまま）。以下は実施時に直した内容を反映している。やり直す・別の PC へ移すときもこの手順でよい。

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
sudo apt-get update && sudo apt-get install -y sqlite3   # 手順 7 のバックアップで使う（Ubuntu Server には入っていない）
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

Hermes を sudo できるユーザー（ログイン用のユーザーなど）で動かす場合は、`sudo -n true` が失敗する（パスワード無しで sudo できない、`NOPASSWD` が無い）ことを確認する。Hermes はパスワードを知らないので、これで `/opt/garden-app` は読めない。

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
WEB_BASE_URL=http://<サーバーのIP>:5000
ANTHROPIC_API_KEY=<使う場合>
```

秘密の値を画面と履歴に残さずに作る例（`API_TOKEN` は Hermes 用の `~/.config/garden-api.env` と同じものを流用。`SECRET_KEY` はその場で生成）:

```bash
read -rsp "ANTHROPIC_API_KEY: " AK; echo
TOKEN=$(grep '^GARDEN_API_TOKEN=' ~/.config/garden-api.env | cut -d= -f2- | tr -d '"'"'")
SK=$(openssl rand -hex 32)
sudo -u garden sh -c 'umask 077; cat > /opt/garden-app/.env' <<EOF
FLASK_ENV=production
SECRET_KEY=$SK
...（上の残りの行。API_TOKEN=$TOKEN、ANTHROPIC_API_KEY=$AK）
EOF
unset AK TOKEN SK
```

## 4. データの移行

1. Windows 側で `server.py` を停止する（以後 Windows 側では起動しない。二重運用でデータが分岐するため）
2. Windows 側で DB と写真を1つの tar にまとめ、sha256 を取る（写真は 2026-10 時点で約 6.5GB・3293 枚。Git Bash に rsync は無く、`scp -r` は途中で切れると再開できないため）:

   ```bash
   # Windows の Git Bash から（リポジトリのルートで）
   mkdir -p <転送用フォルダ>
   tar -cf <転送用フォルダ>/garden-data.tar instance/garden.db app/static/uploads
   sha256sum <転送用フォルダ>/garden-data.tar
   ```

3. sftp で送る。受け取り先は `~/garden-transfer`（**`/tmp` は tmpfs でメモリ上なので置かない**）。切れたら接続し直して `put` の代わりに `reput` で続きから送れる:

   ```
   sftp <user>@<サーバーのIP>
   cd garden-transfer
   lcd <転送用フォルダ>
   put garden-data.tar
   ```

4. Ubuntu 側で sha256 を照合してから展開し、所有者を変更:

   ```bash
   echo "<sha256>  garden-data.tar" | (cd ~/garden-transfer && sha256sum -c -)
   sudo tar -xf ~/garden-transfer/garden-data.tar -C /opt/garden-app --no-same-owner
   sudo chown -R garden:garden /opt/garden-app
   sudo -u garden sqlite3 -readonly /opt/garden-app/instance/garden.db "PRAGMA integrity_check;"
   ```

   件数・ファイル数を移行前と比べる。ファイル数は `.gitkeep`（リポジトリにも入っている）を除いて数える（`find ... -type f ! -name .gitkeep`）

5. Windows 側の DB は誤って起動しないよう名前を変えて退避する（例 `garden.db.moved-to-ubuntu`）

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

移設前のサーバーは ufw が無効だった。有効にすると許可していない受信がすべて止まるので、先に `sudo ss -ltnup` で LAN から使っているポートを確認し、**ssh を許可してから**有効にする（作業中の ssh 接続は閉じずに残し、有効にした後で新しい接続ができることを確かめる）。

**Hermes の実行ユーザー（以下 `hermes`）から 5000 番への接続を拒否する**。2026-10-11 時点のサーバーでは、Hermes は専用ユーザーではなく、ログイン用のユーザーのユーザー systemd サービス（`hermes-gateway.service`）で動いているので、下の `hermes` はそのユーザー名に読み替える（そのユーザーがサーバー上で `localhost:5000` を開けなくなるだけで、スマホからは使える）。ufw の受信ルールは同じ PC 内の通信を止めないため、送信側でユーザー単位に拒否する。

**置き場所に注意**: `before.rules` の先頭近くに `-A ufw-before-output -o lo -j ACCEPT`（ループバックは全部許可）があり、自ホスト宛ての通信は LAN IP 宛ても含めて `lo` を通る。末尾（`COMMIT` の直前）に足すとこの行に先に当たって**効かない**（実際に一度そうなった）。必ずこの行の**直前**に入れる。IPv6 の `before6.rules` はチェーン名が `ufw6-before-output` になる:

```bash
sudo -v
for f in /etc/ufw/before.rules /etc/ufw/before6.rules; do
  case "$f" in *before6*) chain=ufw6-before-output ;; *) chain=ufw-before-output ;; esac
  n=$(sudo grep -c -- "^-A $chain -o lo -j ACCEPT\$" "$f"); echo "$f lo=$n"
  [ "$n" = 1 ] || { echo "中止: $f"; break; }
  sudo cp -p "$f" "$f.bak-garden"
  sudo sed -i "/^-A $chain -o lo -j ACCEPT\$/i # Hermes(hermes) は Web 画面(5000)に接続できない。API(5001)だけを使う。lo の ACCEPT より前に置くこと\n-A $chain -p tcp --dport 5000 -m owner --uid-owner hermes -j REJECT --reject-with tcp-reset" "$f"
done
sudo grep -n -E 'uid-owner|-o lo -j ACCEPT' /etc/ufw/before.rules /etc/ufw/before6.rules
```

LAN から ssh と Web 画面を許可して有効にする（5001 は 127.0.0.1 で待ち受けるので開けない）:

```bash
sudo ufw allow from <LANの範囲> to any port 22 proto tcp
sudo ufw allow from <LANの範囲> to any port 5000 proto tcp
sudo ufw enable
sudo iptables -S ufw-before-output | head -3   # 遮断ルールが -o lo の ACCEPT より上にあること
```

（宛先を限定していないので、`127.0.0.1`・自分の LAN IP・`localhost` のどれで接続しても拒否される。hermes ユーザーがほかの機器の 5000 番を使う予定があれば `-d` で宛先を自ホストに絞る）

Hermes を後で専用ユーザーへ移すときは、`~/.hermes`・Telegram の `.env`・`~/.config/garden-api.env`・systemd の設定を移し、上の `--uid-owner` を新しいユーザーに書き換えて `sudo ufw reload` する。

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
curl -sS -m 5 http://<サーバーのIP>:5001/                                      # 別の端末から → 接続できない
sudo -u hermes curl -sS -m 5 http://127.0.0.1:5000/                           # → 拒否されること（Connection refused）
sudo -u hermes curl -sS -m 5 http://<サーバーのIP>:5000/                       # → 拒否されること
sudo -u hermes curl -sS -m 5 -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/health  # → 成功すること
sudo -u hermes ls /opt/garden-app                                             # → Permission denied
```

スマホで `http://<サーバーのIP>:5000/` を開き、件数が移行前と同じことを確認する。

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
