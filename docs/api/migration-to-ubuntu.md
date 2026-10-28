# Ubuntu（エージェント PC）への移設手順

メイン PC を落としていても API と Web 画面が使えるよう、アプリをエージェント PC（Ubuntu Server、<サーバーのIP>）へ移す手順。
アプリ側のコードは変更不要で、`.env` とサービス登録だけで移せるように作ってある。

**2026-10-11 にこの手順で移設済み**（Hermes は専用ユーザーにせず、ログイン用のユーザーのまま）。以下は実施時に直した内容を反映している。やり直す・別の PC へ移すときもこの手順でよい。

移設後の形:

```
家族 ────LAN──▶ 0.0.0.0:5000    Web 画面（HTTP。誰にとっても閲覧専用）
自分 ────LAN──▶ Caddy :443 ─▶ 127.0.0.1:5000   Web 画面（HTTPS。パスキーでログインすると編集できる。手順 10）
Hermes ──────▶ 127.0.0.1:5001  API（Bearer 必須。LAN からは見えない）
/opt/garden-app/ … ユーザー garden が所有・0700。Hermes の実行ユーザーは読めない
```

**最重要**: Hermes はシェルを実行できるため、同じ PC にあるものには API を通さずに触れてしまう。次の2つを両方行う。

1. **DB・ファイル**: アプリを専用ユーザー `garden` で動かし、Hermes の実行ユーザーからはアプリのフォルダを読めないようにする（手順 1）
2. **Web 画面（ログインすれば削除もできる）**: 同じ PC からは `127.0.0.1:5000` や自分の LAN IP の 5000 番に接続できてしまう（ufw はループバックや自ホスト宛てを止めない）。Hermes の実行ユーザーから 5000 番への接続を OS で拒否する（手順 6）。2026-10-28 からは編集の入口の HTTPS（443番）も同じく拒否する（手順 10）

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

パスキーのログイン用の値（`PASSKEY_RP_ID`・`PASSKEY_ORIGIN`・`OWNER_BASE_URL`）と、`WEB_BASE_URL` の HTTPS への変更は手順 10 で足す。`SECRET_KEY` は固定の値にしておく（無いと再起動のたびにログインが外れる）。

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

> この遮断は「Hermes の実行ユーザーが自分で 5000 番へ接続する」ことだけを止める。別のユーザーで動く常駐ソフト（リバースプロキシなど）を Hermes が操作できると、それ経由ですり抜けられる。2026-10-18 に入れた Caddy は管理用 API を止め、Tuwunel（Hermes がトークンを持つので、URL プレビューや通知の送り先を使って代わりに接続させられる）は tuwunel ユーザーからの新しい接続をこの章と同じ場所のルールで拒否している（[`hermes-local-chat.md`](hermes-local-chat.md)）。

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

Hermes を後で専用ユーザーへ移すときは、`~/.hermes`（`.env` を含む）・`~/.config/garden-api.env`・systemd の設定を移し、上の `--uid-owner` を新しいユーザーに書き換えて `sudo ufw reload` する。

## 7. バックアップ

systemd のタイマーで毎日 3:15 に、DB を曜日ごとのファイル（7世代）に、uploads を `/var/backups/garden/uploads/` にコピーする（同じディスクの中だけ）。`Persistent=true` なので、3:15 にサーバーが止まっていた日は、次に起動した直後に1回実行する（2026-10-23 に cron から置き換え。cron は止まっていた日の分を実行せず、10/18 から5日分抜けていた）。

```bash
sudo mkdir -p /var/backups/garden && sudo chown garden:garden /var/backups/garden && sudo chmod 700 /var/backups/garden
sudo tee /usr/local/bin/garden-backup >/dev/null <<'EOF'
#!/bin/sh
# garden-app のバックアップ（garden-backup.service から garden ユーザーで実行）
set -eu
sqlite3 /opt/garden-app/instance/garden.db ".backup '/var/backups/garden/garden-$(date +%a).db'"
rsync -a --delete /opt/garden-app/app/static/uploads/ /var/backups/garden/uploads/
EOF
sudo chmod 755 /usr/local/bin/garden-backup
sudo tee /etc/systemd/system/garden-backup.service >/dev/null <<'EOF'
[Unit]
Description=garden-app backup (DB and uploads)

[Service]
Type=oneshot
User=garden
Group=garden
Environment=LC_ALL=C
Nice=10
IOSchedulingClass=idle
ExecStart=/usr/local/bin/garden-backup
EOF
sudo tee /etc/systemd/system/garden-backup.timer >/dev/null <<'EOF'
[Unit]
Description=Daily garden-app backup

[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl start garden-backup.service      # 1回目を手で実行して確かめる
sudo systemctl enable --now garden-backup.timer
sudo touch /var/lib/systemd/timers/stamp-garden-backup.timer && sudo systemctl daemon-reload && sudo systemctl restart garden-backup.timer
```

- **最後の `touch` を省かない**。`Persistent=true` は前回の実行時刻（`/var/lib/systemd/timers/stamp-garden-backup.timer`）と比べて追いつくか決める。手で `start` した分は記録されず、記録が無いと「起動後の 3:15」を次の予定にするため、3:15 前に止める使い方では一度も実行されない。`systemctl list-timers garden-backup.timer` の LAST が `-` でなければよい
- 確認: `systemctl list-timers garden-backup.timer`（LAST・NEXT）、`journalctl -u garden-backup.service`（`Finished` が出れば成功）、`sudo ls -l --time-style=long-iso /var/backups/garden/`。失敗しても通知はない
- サーバーをたまにしか起動しないと、曜日によっては古いファイルが残る（7世代＝直近7日分とは限らない）

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

**サーバーで動作を確かめてから PR をマージする**（2026-10-26 から）。マージした後に本番で不具合が見つかると、そのたびに直す PR が要るため。PR のブランチで本番を動かして確かめ、問題があれば同じ PR にコミットを足し、確認が済んでからマージする。開発者も利用者も1人なので、確認中に本番が PR のブランチで動いていても困る人はいない（複数人で使うようになったら、確認中はほかの人のアクセスを止める仕組みを考える）。

1. PR を作る（マージしない）
2. バックアップを取り（下の別名の DB）、PR のブランチに切り替えて再起動する:

   ```bash
   sudo -u garden -H bash -c 'cd /opt/garden-app && git fetch origin && git switch <ブランチ名> && ~/.local/bin/uv sync'
   sudo systemctl restart garden-app
   ```

   初めて切り替えるブランチでも、`git switch <ブランチ名>` は `origin/<ブランチ名>` を追う手元のブランチを作る。
3. 本番で動作を確かめる。直すときは同じ PR にコミットを足して push し、サーバーでは `git pull` → `uv sync` → 再起動（2 のコマンドの `git switch` を `git pull` にしたもの）
4. 確認が済んだら GitHub で PR をマージする（マージコミットの方式。Squash にすると、サーバーで確かめたコミットと main のコミットが別物になる）
5. サーバーを main に戻す:

   ```bash
   sudo -u garden -H bash -c 'cd /opt/garden-app && git switch main && git pull && ~/.local/bin/uv sync'
   sudo systemctl restart garden-app
   ```

   中身は 3 で確かめたものと同じ。`git status` が `On branch main` で、`git log -1` がマージコミットになっていることを確かめる。手元のブランチは `git branch -d <ブランチ名>` で消してよい

**取りやめるとき**（確認で大きな問題が出て、PR を閉じる・作り直すとき）: 5 と同じく main に戻して再起動する。PR にマイグレーションがあり、データを書き換える・消す種類のときは、2 で取ったバックアップの DB に戻す（テーブル・列を足すだけなら、残っても害はない）。戻すときはアプリを止めてから `cp -p` で置き換える。

起動時にマイグレーションが自動で走るので、切り替える前に必ずバックアップを取る（下の別名の DB。uploads も取り直すなら `sudo systemctl start garden-backup.service` だが、DB は曜日のファイルを上書きする）。

- 手で取るバックアップは、曜日ごとのファイルを上書きしないよう別名にする: `sudo -u garden sqlite3 /opt/garden-app/instance/garden.db ".backup '/var/backups/garden/garden-before-update-$(date +%Y%m%d-%H%M).db'"`
- 再起動の直後（1秒ほど）は接続できない。`curl` で確かめるときは少し待つ（`journalctl -u garden-app` の `Serving on` が出ていれば起動済み）
- 停止のたびに `status=143` / `Failed with result 'exit-code'` が記録されるが、SIGTERM で終わったという意味で、異常ではない

## 10. ログイン（パスキー）の入口: avahi・Caddy・443番

**2026-10-28 に追加**。閲覧は今までどおり `http://<サーバーのIP>:5000`（誰にとっても閲覧専用）、登録・編集・削除は `https://<サーバーのホスト名>.local/` でパスキーを使ってログインした自分だけ、という2つの入口にする。アプリ側の仕組みはルート `CLAUDE.md` の「ログイン（パスキー）」、設計は [`../superpowers/specs/2026-10-28-owner-login-passkey-design.md`](../superpowers/specs/2026-10-28-owner-login-passkey-design.md)。

```
家族の端末 ──HTTP──▶ <サーバーのIP>:5000 ───────────▶ waitress（Web アプリ）  閲覧専用
自分の端末 ──HTTPS─▶ <サーバーのホスト名>.local:443 ─▶ Caddy ─▶ 127.0.0.1:5000  パスキーでログイン → 編集
Hermes ──────────────────────────────────────────▶ 127.0.0.1:5001（API、今までどおり）
Hermes ──✕──▶ 5000 番・Caddy の 443 番（ufw のルール）
```

守っていること（崩さない）:

- **Hermes を 443 番にも届かせない**（10.3）。443 番は Web 画面の入口そのもの
- **sudo をパスワード無しにしない**（10.4）。非常口のコマンド（10.7）は `sudo` で `garden` として実行する。Hermes はログイン用のユーザーのユーザー systemd で動いているので、`NOPASSWD` を足す、sudo の記憶を端末ごとから変えると、Hermes が登録用 URL を作れてしまう
- 名前は mDNS（`.local`）で、外部の名前サービス・自分のドメインの DNS・Let's Encrypt には頼らない

### 10.1 avahi（導入済み。やり直すときの記録）

サーバーの名前（`<サーバーのホスト名>.local`）を LAN に流す。サーバーのホスト名がそのまま `.local` の名前になる。

```bash
sudo -v
sudo apt install -y avahi-daemon
sudo cp --update=none /etc/avahi/avahi-daemon.conf /etc/avahi/avahi-daemon.conf.orig
sudo sed -i \
  -e 's/^#\?disable-user-service-publishing=.*/disable-user-service-publishing=yes/' \
  -e 's/^#\?use-ipv6=.*/use-ipv6=no/' \
  -e 's/^#\?publish-aaaa-on-ipv4=.*/publish-aaaa-on-ipv4=no/' \
  /etc/avahi/avahi-daemon.conf
sudo ufw allow from <LANの範囲> to any port 5353 proto udp comment 'mDNS (avahi)'
sudo systemctl restart avahi-daemon
grep -E '^(disable-user-service-publishing|use-ipv6|publish-aaaa-on-ipv4)=' /etc/avahi/avahi-daemon.conf
```

成功時の出力:

```
use-ipv6=no
disable-user-service-publishing=yes
publish-aaaa-on-ipv4=no
```

- `disable-user-service-publishing=yes`: 一般ユーザー（Hermes の実行ユーザー）が LAN に名前を流すのを禁止する
- `use-ipv6=no`・`publish-aaaa-on-ipv4=no`: ufw は IPv4 の LAN だけ許可しているため
- PC・iPhone・iPad から `<サーバーのホスト名>.local` が引けることを確かめる（PC なら `ping <サーバーのホスト名>.local`）。**iPhone・iPad は「セキュリティ Wi-Fi」の SSID で `.local` を引けない**（サーバーの mDNS の答えが届かない）。2026-10-28 からどちらもふだんの接続先を 5G の SSID にした。閲覧は IP の HTTP で今までどおりできる

### 10.2 Caddy のサイトと ufw の 443 番

Caddy は Matrix 用に入れてある（[`hermes-local-chat.md`](hermes-local-chat.md)）。`/etc/caddy/Caddyfile` の末尾にサイトを足す（`admin off` などの先頭の設定と Matrix のサイトはそのまま）。Web アプリへは `127.0.0.1:5000` に転送する（アプリのポートは増やさない）:

```bash
sudo -v
sudo cp -p /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-owner-login
sudo tee -a /etc/caddy/Caddyfile >/dev/null <<'EOF'

https://<サーバーのホスト名>.local {
	tls internal
	reverse_proxy 127.0.0.1:5000
}
EOF
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile \
  && sudo systemctl restart caddy \
  && sudo ufw allow from <LANの範囲> to any port 443 proto tcp comment 'Web app HTTPS (Caddy)' \
  && sudo ss -ltn 'sport = :443'
```

成功時の出力: `Valid configuration`（`caddy validate`）に続けて、`*:443`（または `[::]:443`）が `LISTEN` の行。設定の反映は `reload` ではなく `restart`（`admin off` のため）。

- 証明書は Caddy の `tls internal`（Matrix と同じ自前の発行元）。初回の接続で発行されるので、最初の1回は数秒かかることがある
- サイトはホストの名前（SNI）で選ばれる。先頭の `default_sni <サーバーのIP>` は Matrix のスマホ用で、このサイトには影響しない

### 10.3 Hermes から 443 番を遮断する（`-o lo` 必須）

手順 6 の 5000 番のルールと同じ場所（`-o lo -j ACCEPT` の直前）に、Hermes の実行ユーザー（`hermes`）から 443 番への接続を拒否するルールを TCP と UDP の2本足す。手順 6 と同じく、Hermes はログイン用のユーザーのユーザー systemd サービスで動いているので、下の `hermes` はそのユーザー名に読み替える。

> **UDP も止める**。Caddy は既定で HTTP/3（QUIC、UDP の 443 番）でも待ち受ける（[`hermes-local-chat.md`](hermes-local-chat.md)）。ループバックの UDP は `-o lo -j ACCEPT` で通るので、TCP だけを止めると Hermes は HTTP/3 の使えるクライアントで Web 画面に届いてしまう。

> **必ず `-o lo` を付ける**。手順 6 の 5000 番のルールは宛先を絞っていないが、443 番で同じ書き方をすると、Hermes のインターネットへの HTTPS（ChatGPT・OpenRouter・Web 検索）が全部止まる。`-o lo` を付ければ、自分のサーバー宛て（`127.0.0.1` も自分の LAN IP も `lo` を通る）だけが止まり、外への 443 番は通る。Matrix の 8448 番は止めない（Hermes は Matrix に `127.0.0.1:8008` で直接つないでいる）

```bash
sudo -v
for f in /etc/ufw/before.rules /etc/ufw/before6.rules; do
  case "$f" in *before6*) chain=ufw6-before-output ;; *) chain=ufw-before-output ;; esac
  n=$(sudo grep -c -- "^-A $chain -o lo -j ACCEPT\$" "$f"); echo "$f lo=$n"
  [ "$n" = 1 ] || { echo "中止: $f"; break; }
  sudo test -e "$f.bak-owner-login" || sudo cp -p "$f" "$f.bak-owner-login"
  for proto in tcp udp; do
    sudo grep -q -- "^-A $chain -o lo -p $proto --dport 443 -m owner --uid-owner hermes " "$f" && { echo "足し済み: $f $proto"; continue; }
    case "$proto" in tcp) reject=' --reject-with tcp-reset' ;; *) reject='' ;; esac
    sudo sed -i "/^-A $chain -o lo -j ACCEPT\$/i # Hermes(hermes) は自分のサーバーの 443 番（Web 画面の HTTPS の入口。udp は HTTP/3）に接続できない。-o lo で自ホスト宛てだけを止める（外への HTTPS は通す）。lo の ACCEPT より前に置くこと\n-A $chain -o lo -p $proto --dport 443 -m owner --uid-owner hermes -j REJECT$reject" "$f"
  done
done
sudo ufw reload
sudo grep -n -E 'uid-owner|-o lo -j ACCEPT' /etc/ufw/before.rules /etc/ufw/before6.rules
sudo iptables -S ufw-before-output | grep -E 'uid-owner|-o lo'
sudo ip6tables -S ufw6-before-output | grep -E 'uid-owner|-o lo'
```

（TCP のルールだけを先に足していた場合も、もう一度実行すれば UDP のルールだけが足される。バックアップは最初の1回だけ取る）

成功時の出力: 各ファイルが `lo=1`。`grep` では各ファイルで `--uid-owner hermes` の3本（5000 番、443 番の tcp、443 番の udp）の行が、`-o lo -j ACCEPT` の行より小さい行番号に並ぶ。`iptables -S` と `ip6tables -S` では、次の順に並ぶ（`--uid-owner` の後ろはユーザー名ではなく番号（`<UID>`）。IPv6 は `ufw6-before-output` と `icmp6-port-unreachable`。[`hermes-local-chat.md`](hermes-local-chat.md) の tuwunel の `NEW` を拒否する行も一緒に出る）:

```
-A ufw-before-output -p tcp -m tcp --dport 5000 -m owner --uid-owner <UID> -j REJECT --reject-with tcp-reset
-A ufw-before-output -o lo -p tcp -m tcp --dport 443 -m owner --uid-owner <UID> -j REJECT --reject-with tcp-reset
-A ufw-before-output -o lo -p udp -m udp --dport 443 -m owner --uid-owner <UID> -j REJECT --reject-with icmp-port-unreachable
-A ufw-before-output -o lo -j ACCEPT
```

UDP（HTTP/3）のルールは、サーバーに HTTP/3 の使えるクライアントが無い（Ubuntu の `curl` は HTTP/3 に非対応）ので接続しての確認はできない。上の一覧に `-o lo -p udp ... --dport 443` の行が `-o lo -j ACCEPT` より上にあることを確認とする。

確認（Hermes の実行ユーザーで。`.local` の名前は自分のサーバーでは引けないことがあるので、`--resolve` で LAN の IP に固定する）:

```bash
sudo -u hermes curl -sS -m 5 -k https://127.0.0.1/ || true
sudo -u hermes curl -sS -m 5 --resolve <サーバーのホスト名>.local:443:<サーバーのIP> https://<サーバーのホスト名>.local/ || true
sudo -u hermes curl -sS -m 5 -o /dev/null -w '%{http_code}\n' -I https://example.com
sudo -u hermes curl -sS -m 5 -H "Authorization: Bearer $T" http://127.0.0.1:5001/api/v1/health
```

成功時の出力: 1・2行目は `curl: (7) Failed to connect to ... port 443 ... Connection refused`（拒否）。3行目は `200`（外への HTTPS は通る。`301`・`302` でも可。**止まっていたら `-o lo` の付け忘れ**）。4行目は `{"ok": true, ...}`（API は今までどおり）。

### 10.4 sudo の確認（読み取りだけ）

非常口を自分だけのものにしている前提（パスワード無しで sudo できない）を確かめる。何も変更しない:

```bash
sudo -v
sudo -l
sudo grep -rnE 'NOPASSWD|timestamp_type|timestamp_timeout' /etc/sudoers /etc/sudoers.d/ || echo "該当なし"
ls -l /etc/sudoers.d/
setsid -w sudo -n true; echo "exit=$?"
```

成功時の出力:

- `sudo -l` の権限の行に `NOPASSWD` が無い（`(ALL : ALL) ALL` など）
- `grep` は `該当なし`（`NOPASSWD` も、sudo の記憶を端末ごとから変える `timestamp_type` も無い。Ubuntu の既定は端末（tty）ごと）。`/etc/sudoers.d/` にファイルがあれば中身を読んで、同じ意味の設定が無いことを確かめる
- 最後は `sudo: a password is required` と `exit=1`（端末の無いプロセスは、自分が SSH で sudo した直後の記憶を使い回せない。Hermes のプロセスと同じ条件）

`NOPASSWD` や `timestamp_type=global` が見つかったら、先へ進まずに外す。

### 10.5 `.env`（`/opt/garden-app/.env`）

`SECRET_KEY` が固定の値で入っていることを確かめ（値は画面に出さない）、無ければ作る。ログイン用の値を足し、`WEB_BASE_URL` を HTTPS に変える:

```bash
sudo -v
sudo cp -p /opt/garden-app/.env /opt/garden-app/.env.bak-owner-login
[ "$(sudo grep -c '^SECRET_KEY=.\+' /opt/garden-app/.env)" = 1 ] || echo "SECRET_KEY=$(openssl rand -hex 32)" | sudo -u garden tee -a /opt/garden-app/.env >/dev/null
sudo sed -i '/^WEB_BASE_URL=/d' /opt/garden-app/.env
sudo -u garden tee -a /opt/garden-app/.env >/dev/null <<'EOF'
WEB_BASE_URL=https://<サーバーのホスト名>.local
PASSKEY_RP_ID=<サーバーのホスト名>.local
PASSKEY_ORIGIN=https://<サーバーのホスト名>.local
OWNER_BASE_URL=https://<サーバーのホスト名>.local
EOF
sudo grep -c '^SECRET_KEY=.\+' /opt/garden-app/.env
sudo grep -E '^(WEB_BASE_URL|PASSKEY_RP_ID|PASSKEY_ORIGIN|OWNER_BASE_URL)=' /opt/garden-app/.env
sudo ls -l /opt/garden-app/.env
sudo -u garden -H bash -c 'cd /opt/garden-app && ~/.local/bin/uv sync' && sudo systemctl restart garden-app
```

成功時の出力: `grep -c` が `1`、続く `grep` が上の4行、`ls -l` が `-rw------- 1 garden garden`。`SESSION_COOKIE_SECURE` は本番の既定が有効なので書かない（HTTP だけで使うときだけ `0`）。再起動の直後は1秒ほど接続できない。

- `.env.bak-owner-login` には `SECRET_KEY`・トークンが入っている。確認が済んだら `sudo rm` する
- `WEB_BASE_URL` が HTTPS になるので、API の応答の `web_url` や Hermes が Matrix の返事に付けるリンクが HTTPS の入口になり、ログイン済みならそのまま編集できる。iPhone・iPad がセキュリティ Wi-Fi のときはリンクが開けない（5G の SSID にする）

### 10.6 PC に Caddy の発行元の証明書を入れる

iPhone・iPad は Matrix のときに発行元の証明書を入れてあるので、同じ証明書で足りる。PC（Windows）には、サーバーから `root.crt` を取り出して「現在のユーザーの信頼されたルート」に入れる。**入れる前に、サーバーと PC で SHA-256 の指紋が同じことを確かめる**（違うものを信頼させない）。

サーバー（発行元は `/var/lib/caddy/.local/share/caddy/pki/authorities/local/`）:

```bash
sudo -v
sudo openssl x509 -in /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt -noout -fingerprint -sha256
sudo cp /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/root.crt && sudo chown "$USER": ~/root.crt
```

PC に `root.crt` を持ってくる（`scp <user>@<サーバーのIP>:root.crt .`）。PC の PowerShell で:

```powershell
certutil -dump .\root.crt | Select-String -Pattern 'sha256'                         # サーバーの指紋と同じか（コロンの有無・大文字小文字は無視）
Import-Certificate -FilePath .\root.crt -CertStoreLocation Cert:\CurrentUser\Root    # 同じときだけ。確認のダイアログが出たら「はい」
```

成功時の出力: 指紋が一致し、`Import-Certificate` が `Thumbprint`・`Subject`（Caddy の発行元の名前）の行を返す。Chrome・Edge を開き直し、`https://<サーバーのホスト名>.local/` を開いて警告が出なければよい。使い終わった `~/root.crt` はサーバーから消す。信頼を外すときは `Cert:\CurrentUser\Root` から該当の Thumbprint を `Remove-Item` する。

### 10.7 パスキーを登録する（非常口と端末の追加）

最初の1つ目は、サーバーで次のコマンドを実行して**登録用の URL**（1回限り・15分）を出す。ここがパスキーの非常口でもある（全部の端末をなくしたときも同じ）:

```bash
sudo -v
sudo -u garden -H bash -c 'cd /opt/garden-app && ~/.local/bin/uv run flask --app app passkey-register-link'
```

成功時の出力: `https://<サーバーのホスト名>.local/auth/register/<トークン>` の形の URL と、有効期限の案内。URL は他人に見せない（使うか期限が切れれば無効）。`--base-url` で URL の先頭を変えられる（既定は `OWNER_BASE_URL`）。

1. **PC**: 上の URL をブラウザで開き、Windows Hello（顔認証）で登録する。そのままログイン済みになる
2. **iPhone**: Safari で `https://<サーバーのホスト名>.local/` を開き、ログインしてから設定画面（`/settings/`）の「この端末のパスキーを追加」で Face ID で登録する（ログイン中の人だけが追加できる。最初の1つ目と同じく、先に PC で登録しておく）
3. **iPad**: iPhone で登録したパスキーは iCloud キーチェーンで同期されるので、登録せずにログインできる（2026-10-28 の試作で確認）。iPhone・iPad ともセキュリティ Wi-Fi では `.local` を引けないので 5G の SSID につなぐ
4. 設定画面の「パスキー」の欄で、名前の変更・削除ができる。端末をなくしたときは、その端末のパスキーを消せばその端末のログインはすぐ切れる。全部の端末をなくしたときは、このコマンドで登録し直したあと古いパスキーを全部消す

### 10.8 動作確認

ログイン用のユーザーは Hermes の実行ユーザーと同じなので（手順 6）、サーバーでそのまま `curl` すると 5000 番・443 番は遮断のルールで拒否される。`sudo`（root で実行する。遮断のルールは `hermes` のユーザーにだけ当たる）を付けて確かめる:

```bash
sudo -v
sudo curl -sS -m 5 -o /dev/null -w '%{http_code}\n' http://<サーバーのIP>:5000/                                   # → 200（家族の閲覧は今までどおり）
sudo curl -sS -m 5 -k -o /dev/null -w '%{http_code}\n' --resolve <サーバーのホスト名>.local:443:127.0.0.1 https://<サーバーのホスト名>.local/   # → 200
sudo curl -sS -m 5 -o /dev/null -w '%{http_code} %{redirect_url}\n' http://<サーバーのIP>:5000/crops/new           # → 302 と /auth/login への URL（ログインしていない人は編集画面に入れない）
sudo curl -sS -m 5 -o /dev/null -w '%{http_code}\n' -X POST http://<サーバーのIP>:5000/crops/1/delete             # → 302 か 401 か 403（拒否される。データは変わらない）
```

成功時の出力: 各行の `#` の後ろのとおり（1行目 `200`、2行目 `200`、3行目 `302 http://.../auth/login?next=...`、4行目 `302`・`401`・`403` のどれか）。

PC からなら遮断のルールに当たらないので、PowerShell の `curl.exe` で同じことを確かめられる（10.6 で証明書を入れた後なら `-k` はいらない。`.local` を引けない端末でも `--resolve` で IP に固定できる）:

```powershell
curl.exe -sS -m 5 -o NUL -w '%{http_code}\n' http://<サーバーのIP>:5000/                                                                      # → 200
curl.exe -sS -m 5 -o NUL -w '%{http_code}\n' --resolve <サーバーのホスト名>.local:443:<サーバーのIP> https://<サーバーのホスト名>.local/   # → 200
```

さらに、ログイン済みの PC などで次を確かめる:

- `https://<サーバーのホスト名>.local/` でパスキーでログインでき、登録・編集・削除ができる。ログアウトするとボタンが消える
- `http://<サーバーのIP>:5000/` では、ログイン中でも編集のボタンが出ない（HTTP にはログインの Cookie が届かない）。ナビの「ログイン」を押すと HTTPS の URL に移る
- 家族の端末（証明書を入れていない）で `http://<サーバーのIP>:5000/` の閲覧が今までどおりできる
- 10.3 の確認（Hermes から 443 番に届かない、外への HTTPS と API は通る）

### 10.9 Hermes の記憶に古い URL が残っていないか

Hermes が以前の返事で覚えた `http://<サーバーのIP>:5000` のリンクを、これからも返すことがある（その URL は閲覧専用）。残っているか調べ、あれば Hermes に「編集は `https://<サーバーのホスト名>.local/`、`http://<サーバーのIP>:5000` は閲覧専用」と伝えて直させる:

```bash
grep -rIn '<サーバーのIP>:5000' ~/.hermes 2>/dev/null | head
```

成功時の出力: 何も出ない（あっても、閲覧用の説明として意図して書いた行だけ）。

### 取りやめるとき

`Caddyfile.bak-owner-login`・`.env.bak-owner-login`・`before.rules.bak-owner-login`・`before6.rules.bak-owner-login` で戻し、443 番の許可を消して反映する:

```bash
sudo -v
sudo cp -p /etc/caddy/Caddyfile.bak-owner-login /etc/caddy/Caddyfile \
  && sudo cp -p /opt/garden-app/.env.bak-owner-login /opt/garden-app/.env \
  && sudo cp -p /etc/ufw/before.rules.bak-owner-login /etc/ufw/before.rules \
  && sudo cp -p /etc/ufw/before6.rules.bak-owner-login /etc/ufw/before6.rules \
  && sudo ufw delete allow from <LANの範囲> to any port 443 proto tcp \
  && sudo ufw reload \
  && sudo systemctl restart caddy garden-app
sudo iptables -S ufw-before-output | grep -c 'dport 443'
sudo ip6tables -S ufw6-before-output | grep -c 'dport 443'
```

成功時の出力: `ufw delete` が `Rule deleted`、`ufw reload` が `Firewall reloaded`、最後の2行がどちらも `0`（Hermes の 443 番のルールが消えた）。`0` でなければ `before.rules`／`before6.rules` に 443 番の行が残っているので、`sudo grep -n 'dport 443' /etc/ufw/before.rules /etc/ufw/before6.rules` で探して消し、`sudo ufw reload` する。

- `.env.bak-owner-login` を確認後に消していた（10.5）ときは、2行目の代わりに `.env` から `PASSKEY_RP_ID`・`PASSKEY_ORIGIN`・`OWNER_BASE_URL` の行を消し、`WEB_BASE_URL` を `http://<サーバーのIP>:5000` に戻す（`SECRET_KEY` は残してよい）。途中の行が失敗すると `&&` で後ろは実行されないので、直してから残りを実行する

アプリを手順 9 の要領で以前のブランチに戻すと、編集の入口はまた認証なしになる（`passkeys` 表は残っても害はない）。
