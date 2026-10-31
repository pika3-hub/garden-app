# LAN 内のチャット（Matrix＋Element X）で Hermes に依頼する

スマホから Hermes への依頼を、Telegram 社のサーバーを通さず自宅の LAN の中だけで済ませるための構成と手順。**2026-10-18 に構築済み**。2026-10-23 からはこれだけを使っている（Telegram は停止。[`hermes-telegram.md`](../../../garden-app-private/docs/api/hermes-telegram.md)）。2026-10-24 から、ふだんは**暗号化（E2EE）ありの部屋**を使う（下の「E2EE（暗号化ありの部屋）」）。設計の経緯は [`../superpowers/specs/2026-10-18-hermes-matrix-design.md`](../../../garden-app-private/docs/superpowers/specs/2026-10-18-hermes-matrix-design.md)、構築時の計画は [`../superpowers/plans/2026-10-18-hermes-matrix.md`](../../../garden-app-private/docs/superpowers/plans/2026-10-18-hermes-matrix.md)。

固有値は記号で書く（`<サーバーのIP>`・`<LANの範囲>`・`<user>` = Hermes の実行ユーザー）。実際の値はリポジトリ外の `local-env.md`。

## 構成

```
iPhone / iPad（Element X）
   │  https://<サーバーのIP>:8448   ← LAN からだけ（ufw）
   ▼
Caddy（HTTPS を受けて転送。証明書は Caddy の内部の発行元）
   │  http://127.0.0.1:8008
   ▼
Tuwunel（Matrix サーバー）  ←──  Hermes の gateway（Bot @hermes。127.0.0.1:8008 に直接つなぐ）
                                    │
                                    ▼
                               garden-app の API（127.0.0.1:5001）
```

| 部品 | 場所・設定 | メモ |
|---|---|---|
| Tuwunel | apt（`https://apt.f.dog`）、`tuwunel.service`、ユーザー `tuwunel`、設定 `/etc/tuwunel/tuwunel.toml`（root:tuwunel 640）、DB `/var/lib/tuwunel` | 待ち受け 127.0.0.1:8008 だけ。サーバー名 `garden.home.arpa`（変更不可）。フェデレーションなし、新規登録は閉じている |
| Caddy | apt（cloudsmith の公式リポジトリ）、`caddy.service`、`/etc/caddy/Caddyfile`、発行元 `/var/lib/caddy/.local/share/caddy/pki/authorities/local/` | `*:8448`（Matrix）と `*:443`（Web アプリのサイト `https://<サーバーのホスト名>.local`、2026-10-28 追加。`tls internal`、`127.0.0.1:5000` へ転送）で待ち受ける（TCP と HTTP/3 の UDP）。LAN 以外を止めているのは ufw。**管理用 API を止めている**（下記） |
| ufw | `8448/tcp ALLOW IN <LANの範囲>` | 8008 は開けない。既存の 22・5000 と `<user>` → 5000 の遮断はそのまま（2026-10-28 から `<user>` → 自ホストの 443 番（TCP・UDP）も遮断）。**tuwunel ユーザーからの新しい接続をすべて拒否**（下記） |
| アカウント | `@<user>:garden.home.arpa`（管理者）、`@hermes:garden.home.arpa`（Bot） | 先に登録したほうが管理者になる |
| Hermes | `~/.hermes/.env` の `MATRIX_*`、部品は `hermes pm install --extra matrix` | Telegram の設定は 2026-10-23 に外した。E2EE の鍵は `~/.hermes/platforms/matrix/store/crypto.db` |
| 部屋 | 「Hermes（暗号化）」（ふだん使い、E2EE あり）、「Hermes」（予備、E2EE なし） | どちらも @hermes との DM。DM は `MATRIX_ALLOWED_ROOMS` の対象外（下記） |
| スマホ | Element X（App Store では「Element X - Secure Chat & Call」、開発元 Vector Creations Limited） | 発行元の証明書を入れて信頼させる。**通知はオフ**（下記） |

### 守っていること

- **Caddy の管理用 API を止める（`admin off`）**。既定の `localhost:2019` はサーバー内のどのユーザーからも設定を書き換えられ、Hermes の実行ユーザーが「5000番へ転送する」設定を足すと、ufw の `<user>` → 5000 の遮断（[`migration-to-ubuntu.md`](migration-to-ubuntu.md) の 6章）をすり抜けられる。代わりに設定の反映は `systemctl reload` ではなく `restart`
- **Caddy に Web アプリのサイトが増えた**（2026-10-28）。`https://<サーバーのホスト名>.local`（`.local` は avahi の名前）を `127.0.0.1:5000` へ転送する、パスキーでログインして編集する入口。Matrix のサイトとは別で、`admin off` も `default_sni <サーバーのIP>`（Matrix のスマホ用）もそのまま。Caddy を経由すると Hermes が Web 画面に届く道になるので、`before.rules`／`before6.rules` で Hermes の実行ユーザーから自ホスト宛ての 443 番を TCP と UDP（Caddy は HTTP/3 を UDP の 443 番で受けるので、TCP だけでは HTTP/3 で届いてしまう）の両方で拒否している（`-o lo` 付き。付けないと外への HTTPS が全部止まる）。Matrix の 8448 番は止めない。手順は [`migration-to-ubuntu.md`](migration-to-ubuntu.md) の 10章
- Tuwunel は他の Matrix サーバーに鍵を問い合わせない（`trusted_servers = []`。既定は matrix.org）
- 設定ファイルは `<user>` から読めない（登録用トークンを一時的に書くため）
- **Tuwunel は自分から接続しない（ufw）**。Hermes は Tuwunel のトークンを持つので、URL プレビュー（`preview_url`）や通知の送り先（pusher）を使えば、tuwunel ユーザーに代わりに `127.0.0.1:5000` へ接続させられるおそれがある（`<user>` → 5000 の遮断は tuwunel には効かない）。フェデレーションをしない Tuwunel には外への接続がいらないので、`before.rules`／`before6.rules` で tuwunel の `NEW` の接続を拒否している（スマホ・Hermes・Caddy からの接続への返事は止まらない）
- **スマホの通知は使わない**。Element X で通知を許可すると、Tuwunel に通知の送り先 `https://matrix.org/_matrix/push/v1/notify`（Element 社の通知サーバー）が登録され、メッセージのたびに部屋 ID・イベント ID・未読数が LAN の外に送られる（本文は送られない `event_id_only` 形式）。上の ufw のルールで送れないが、iPhone・iPad の 設定 → 通知 → Element X はオフにし、登録された送り先は消しておく（構築手順 5）

## 使い方

- 「Hermes（暗号化）」の部屋で文面・写真を送る。暗号化ありの部屋が返事をしなくなったら「Hermes」（暗号なし）の部屋で依頼でき、その間に下の「E2EE の鍵が壊れたとき」で直す
- 写真（カメラロール）として送れば Element X が **JPEG に変換・縮小して送る**（例 1536×2048）ので、HEIC で断られない。「ファイル」として送ると HEIC のまま届き、受け取りで断られる見込み（Telegram と同じ。[`hermes-skill/SKILL.md`](hermes-skill/SKILL.md) の HEIC の注意）
- `/new` を送ると確認が出る。Matrix にはボタンが無いので、**`!approve`（今回だけ）・`!always`（以後確認しない）・`!cancel`** を文字で返す
- セッションは**毎朝4時以降の最初の依頼と、6時間あいた後の依頼で自動で新しくなる**（2026-10-24 から。下の「会話の自動リセット」）。SKILL.md をサーバーに送った後は、自動を待たずに `/new` する。自己改善（SKILL.md の書き換えは承認制。`/skills pending` で確認）の扱いは [`hermes-telegram.md`](../../../garden-app-private/docs/api/hermes-telegram.md) の「Hermes の自己改善」（Telegram 時代の記録だが Matrix でも同じ）
- ホームチャンネル（定期実行の結果や gateway の終了通知の送り先）は設定していない（Telegram の `/sethome` は停止とともに無効。定期実行のジョブも無い）。必要になったら Hermes の部屋で `/sethome` を送る
- 一覧にある「garden.home.arpa Admin」は Tuwunel の管理用の部屋。書いた文が管理コマンドとして扱われるので、普段は開かない
- サーバーを起動すれば Tuwunel・Caddy・gateway は自動で立ち上がる

## 確認とログ

```bash
systemctl is-active tuwunel caddy garden-app; systemctl --user is-active hermes-gateway
grep -h 'matrix connected' ~/.hermes/logs/gateway.log | tail -1
```

- **gateway のログは `~/.hermes/logs/gateway.log` を見る**。`journalctl --user -u hermes-gateway` には WARNING 以上しか出ず、Matrix の接続や受け取った画像（`Cached user image at ...`）の行が見えない
- **暗号の失敗は `~/.hermes/logs/errors.log` にだけ出る**（暗号ライブラリ mautrix のログ。`gateway.log` には出ない）。暗号化ありの部屋で返事が無いときは `grep 'Failed to decrypt' ~/.hermes/logs/errors.log | tail -3`
- Tuwunel は `sudo journalctl -u tuwunel`、Caddy は `sudo journalctl -u caddy`

## 構築手順

サーバーで `<user>` として実行する。sudo の前に `sudo -v`。

### 1. Tuwunel

```bash
sudo curl -fsSL -o /usr/share/keyrings/tuwunel-archive-keyring.gpg https://apt.f.dog/tuwunel-archive-keyring.gpg
sudo tee /etc/apt/sources.list.d/tuwunel.sources >/dev/null <<'EOF'
Types: deb
URIs: https://apt.f.dog
Suites: stable
Components: main
Signed-By: /usr/share/keyrings/tuwunel-archive-keyring.gpg
EOF
sudo apt update && sudo apt install tuwunel
```

apt.f.dog は一時的に毎秒数 KB まで遅くなることがある（2026-10-18 に発生、しばらくして戻った）。急ぐときは GitHub のリリースの `.deb` を取ってきて、`apt-cache show tuwunel=<版>` の `SHA256` と `sha256sum` が一致することを確かめてから `sudo apt install ./<ファイル>.deb` で入れる。

設定（元の設定例は `tuwunel.toml.orig` に残す）:

```bash
sudo cp --update=none /etc/tuwunel/tuwunel.toml /etc/tuwunel/tuwunel.toml.orig
sudo tee /etc/tuwunel/tuwunel.toml >/dev/null <<'EOF'
[global]
server_name = "garden.home.arpa"
database_path = "/var/lib/tuwunel"
address = ["127.0.0.1"]
port = 8008
allow_federation = false
trusted_servers = []
allow_outgoing_presence = false
allow_registration = false
new_user_displayname_suffix = ""
EOF
sudo chown root:tuwunel /etc/tuwunel/tuwunel.toml && sudo chmod 640 /etc/tuwunel/tuwunel.toml
sudo systemctl enable --now tuwunel.service
curl -s http://127.0.0.1:8008/_matrix/client/versions | head -c 100; echo                 # JSON
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8008/_matrix/federation/v1/version  # 403
```

### 2. Caddy と ufw

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
sudo cp --update=none /etc/caddy/Caddyfile /etc/caddy/Caddyfile.orig
sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
{
	# 管理用 API を止める（設定の反映は systemctl restart caddy）
	admin off
	# IP で接続するスマホは SNI を送らない
	default_sni <サーバーのIP>
	auto_https disable_redirects
	skip_install_trust
}

https://<サーバーのIP>:8448 {
	tls internal
	reverse_proxy 127.0.0.1:8008
}
EOF
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl restart caddy
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:2019/config/   # 000（管理用 API が無い）
sudo ufw allow from <LANの範囲> to any port 8448 proto tcp comment 'Matrix (Caddy)'
```

Tuwunel から外へ（`127.0.0.1:5000` を含む）の新しい接続を拒否する。既存の `<user>` → 5000 のルールと同じく、`lo` の ACCEPT より**前**に置く（後ろでは効かない）:

```bash
for f in /etc/ufw/before.rules /etc/ufw/before6.rules; do
  case "$f" in *before6*) chain=ufw6-before-output ;; *) chain=ufw-before-output ;; esac
  n=$(sudo grep -c -- "^-A $chain -o lo -j ACCEPT\$" "$f"); echo "$f lo=$n"
  [ "$n" = 1 ] || { echo "中止: $f"; break; }
  sudo cp -p "$f" "$f.bak-matrix"
  sudo sed -i "/^-A $chain -o lo -j ACCEPT\$/i # Tuwunel(tuwunel) は自分から接続しない（フェデレーション・プッシュ通知・URL プレビュー・5000 番への抜け道を塞ぐ）。lo の ACCEPT より前に置くこと\n-A $chain -m owner --uid-owner tuwunel -m conntrack --ctstate NEW -j REJECT" "$f"
done
sudo ufw reload
sudo iptables -S ufw-before-output | head -4      # tuwunel のルールが -o lo の ACCEPT より上
sudo -u tuwunel curl -s -m 5 -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/ || true   # 000
sudo -u tuwunel curl -s -m 5 -o /dev/null -w '%{http_code}\n' https://matrix.org/ || true      # 000
curl -sk -o /dev/null -w '%{http_code}\n' https://<サーバーのIP>:8448/_matrix/client/versions  # 200
```

HTTP/3（UDP 8448）の待ち受けも始まるが、ufw は TCP だけ許可しているので、スマホは自動で TCP に切り替わる。

### 3. アカウント

補助スクリプト [`tools/matrix_helper.py`](../../tools/matrix_helper.py)（Python 標準ライブラリのみ。パスワードは画面に出さずに聞き、トークンは標準出力の `MATRIX_ACCESS_TOKEN=...` の1行だけに出す）をサーバーの `~/matrix_helper.py` に置く（メイン PC から `scp`）。

```bash
TOKEN="$(openssl rand -hex 24)"
sudo sed -i 's/^allow_registration = false$/allow_registration = true\nregistration_token = "'"$TOKEN"'"/' /etc/tuwunel/tuwunel.toml
sudo systemctl restart tuwunel.service
echo "登録用トークン: $TOKEN"          # 入力に使う。チャットや文書に貼らない
# 自分の登録が成功したときだけ Hermes を登録する（先に登録したほうが管理者になる）
python3 ~/matrix_helper.py register <user> && python3 ~/matrix_helper.py register hermes
# すぐ閉じる
sudo sed -i -e 's/^allow_registration = true$/allow_registration = false/' -e '/^registration_token = /d' /etc/tuwunel/tuwunel.toml
sudo systemctl restart tuwunel.service; unset TOKEN
```

管理者になったユーザーは `sudo journalctl -u tuwunel | grep 'admin privileges as the first user'` で分かる。順番を間違えたら、Tuwunel を止めて `/var/lib/tuwunel` を別名に退避し、`sudo install -d -o tuwunel -g tuwunel -m 0740 /var/lib/tuwunel` で空にして登録し直す。

### 4. Hermes

Hermes は仮想環境ではなく自前の部品管理（`hermes pm`）を使う。Matrix の部品（`mautrix[encryption]`）は暗号化を使わなくても `python-olm` を含み、Python 3.14 用のビルド済みが無いのでソースからビルドされる。Hermes の Python は clang で作られているが、Hermes の注意書きによると libolm は今の clang・CMake 4 では失敗するため、gcc を使わせる:

```bash
sudo apt install -y build-essential
CC=gcc CXX=g++ LDSHARED="gcc -shared" LDCXXSHARED="g++ -shared" hermes pm install --extra matrix
hermes pm status | grep -E '"(outcome|exit_code)"'   # ok / 0
```

`hermes update` で `python-olm` のビルドし直しが要るときも、同じ環境変数を付ける。

接続情報（`~/.hermes/.env` は 600）:

```bash
cp -p ~/.hermes/.env ~/.hermes/.env.bak-before-matrix
# ログインに失敗したら残りの行を足さない（やり直すときは .env の MATRIX_ の行を消してから）
python3 ~/matrix_helper.py login hermes >> ~/.hermes/.env && cat >> ~/.hermes/.env <<'EOF'
MATRIX_HOMESERVER=http://127.0.0.1:8008
MATRIX_USER_ID=@hermes:garden.home.arpa
MATRIX_ALLOWED_USERS=@<user>:garden.home.arpa
MATRIX_E2EE_MODE=off
EOF
```

部屋（暗号化なしの1対1）を作り、許可する部屋に入れる。Tuwunel は room version 12 で部屋を作るので、部屋 ID にサーバー名が付かない（`!xxxx` だけ）:

```bash
(umask 077; python3 ~/matrix_helper.py login <user> > ~/.config/matrix-test-user.env)
ROOM="$(python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env create-dm @hermes:garden.home.arpa)"
[ -n "$ROOM" ] && echo "MATRIX_ALLOWED_ROOMS=$ROOM" >> ~/.hermes/.env
systemctl --user restart hermes-gateway.service
grep -h 'Matrix' ~/.hermes/logs/gateway.log | tail -5     # 招待を受けて join、matrix connected
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env send-text "$ROOM" "API の health を確認して"
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env messages "$ROOM" --limit 5
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env logout; rm -f ~/.config/matrix-test-user.env
ls ~/.config/matrix-test-user.env    # No such file or directory を確かめる
```

`matrix-test-user.env` は管理者（`@<user>`）のトークンで、同じユーザーで動く Hermes からも読める。途中で失敗しても、必ず消えたことを確かめる。

Element X で部屋を作ると既定で暗号化ありになる（後からオフにできない）ので、部屋はこのスクリプトで作る。暗号化ありの部屋も同じスクリプトで作る（「E2EE（暗号化ありの部屋）」。Element X で @hermes とのチャットを始めると、既存の DM が開くだけで新しい部屋はできない）。

### 5. スマホ

1. 発行元の証明書を取り出す: `sudo cp /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/garden-ca.crt && sudo chown "$USER": ~/garden-ca.crt`。`openssl x509 -in ~/garden-ca.crt -noout -fingerprint -sha256` の値を控える（秘密鍵ではないので配ってよい）
2. メールの添付か iCloud Drive で iPhone・iPad に届けて開く
3. 設定 → 一般 → VPN とデバイス管理 でインストール（詳細の SHA-256 が控えと同じか確かめる）→ 設定 → 一般 → 情報 → 証明書信頼設定 でオン
4. Safari で `https://<サーバーのIP>:8448/_matrix/client/versions` が警告なしで開けることを確かめる
5. Element X を入れ、**設定 → プライバシーとセキュリティ → ローカルネットワーク で Element X をオン**にする（オフのままだと「このホームサーバーに接続できませんでした」になる。Safari は開けるので気づきにくい）
6. 「手動で指定してサインイン」→ アカウント提供元に `https://<サーバーのIP>:8448` → `<user>` でログイン。復元キーの設定などはスキップ。**通知の許可を聞かれたら「許可しない」**（許可したら 設定 → 通知 → Element X でオフ）
7. 通知の送り先が登録されていないか確かめ、あれば消す（`{"pushers":[]}` になればよい）:

```bash
(umask 077; python3 ~/matrix_helper.py login <user> > ~/.config/m.env)
T="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' ~/.config/m.env)"
curl -s -H "Authorization: Bearer $T" http://127.0.0.1:8008/_matrix/client/v3/pushers   | python3 -c 'import json,sys; [print(json.dumps({"pushkey":p["pushkey"],"app_id":p["app_id"],"kind":None})) for p in json.load(sys.stdin)["pushers"]]'   | while read -r body; do curl -s -X POST -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "$body" http://127.0.0.1:8008/_matrix/client/v3/pushers/set; echo; done
curl -s -H "Authorization: Bearer $T" http://127.0.0.1:8008/_matrix/client/v3/pushers; echo
unset T
python3 ~/matrix_helper.py --token-file ~/.config/m.env logout; rm -f ~/.config/m.env; ls ~/.config/m.env
```

### 6. 後片付け

```bash
sudo tar -C /var/lib/caddy/.local/share/caddy -czf /root/caddy-pki-backup-$(date +%Y%m%d).tgz pki
sudo bash -c 'chmod 600 /root/caddy-pki-backup-*.tgz && ls -l /root/caddy-pki-backup-*.tgz'
rm ~/garden-ca.crt
```

`/root` の中の `*` は `<user>` のシェルでは展開できないので、`sudo bash -c '...'` の中に書く。

## E2EE（暗号化ありの部屋）

2026-10-24 に有効にした（Hermes v2026.9.24）。暗号化すると、文面と写真は Tuwunel の DB に暗号文で保存される（暗号なしの部屋は平文）。通信路は前から HTTPS。復号は Hermes がサーバーの中で行う。

- `MATRIX_E2EE_MODE=required`: 暗号の部品が無いと接続そのものを拒否する（`optional` は暗号なしに黙って戻るので使わない）。暗号なしの部屋もそのまま使える
- Bot の相互署名（cross-signing）: `MATRIX_RECOVERY_KEY`（Bot のアカウントの復元キー。ユーザーの Element の復元キーではない）で、起動のたびに Bot のデバイスに署名する（ログに `cross-signing verified via recovery key`）。Tuwunel は初回の相互署名の鍵の登録にパスワードの再入力を求めなかった
- 部品（`olm`・`asyncpg`・`aiosqlite`・mautrix の暗号）は構築手順 4 の `hermes pm install --extra matrix` で入っている
- 暗号化ありの部屋の写真も受け取れる（Hermes が復号して `Cached user image at ...`）
- iPhone の Element X で写真を送ると、自分のメッセージの写真がぼかし（読み込み中の表示）のまま残ることがある。押せば全画面で見え、部屋を開き直せば直る。iPad では最初から見える。サーバーにエラーは無く、Element X の表示の問題

### 有効にする手順

```bash
cd ~/.hermes && cp -p .env .env.bak-before-e2ee
# 1. required にし、Bot の復元キーを1度だけ書き出させる
grep -c '^MATRIX_E2EE_MODE=off$' .env && sed -i 's/^MATRIX_E2EE_MODE=off$/MATRIX_E2EE_MODE=required/' .env && echo "MATRIX_RECOVERY_KEY_OUTPUT_FILE=$HOME/.hermes/matrix-recovery-key.txt" >> .env
systemctl --user restart hermes-gateway.service && sleep 20 && grep -h 'Matrix' ~/.hermes/logs/gateway.log | tail -6
# → bootstrapped cross-signing ... written to ...、E2EE enabled
# 2. 復元キーを .env に移す（画面に出さない）
K="$(tr -d '\n' < matrix-recovery-key.txt)" && [ -n "$K" ] && printf 'MATRIX_RECOVERY_KEY="%s"\n' "$K" >> .env && unset K && sed -i '/^MATRIX_RECOVERY_KEY_OUTPUT_FILE=/d' .env
systemctl --user restart hermes-gateway.service && sleep 20 && grep -h 'cross-signing' ~/.hermes/logs/gateway.log | tail -1
# → cross-signing verified via recovery key を確かめてから
rm matrix-recovery-key.txt
chmod 700 ~/.hermes/platforms/matrix/store && chmod 600 ~/.hermes/platforms/matrix/store/crypto.db*
```

部屋は構築手順 4 と同じく自分のアカウントで一時的にログインして作る（`--encrypted`）。Hermes は DM の招待を受けると自分の DM の一覧に登録し、DM は `MATRIX_ALLOWED_ROOMS` の対象外なので、足さなくても応答する（`MATRIX_ALLOWED_USERS` は効く。DM でない部屋はメンションが必須）:

```bash
(umask 077; python3 ~/matrix_helper.py login <user> > ~/.config/matrix-test-user.env) && python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env create-dm --encrypted @hermes:garden.home.arpa
python3 ~/matrix_helper.py --token-file ~/.config/matrix-test-user.env logout; rm -f ~/.config/matrix-test-user.env; ls ~/.config/matrix-test-user.env
grep -h 'Matrix' ~/.hermes/logs/gateway.log | tail -3     # joined、recorded ... as DM room
```

暗号文で保存されているかは、Hermes のトークンで部屋のメッセージの種類を見て確かめた（すべて `m.room.encrypted`。返信先などの `m.relates_to` と取り消しは仕様で平文）。

### E2EE の鍵が壊れたとき

`crypto.db` を失う（消える・古いものに戻す）と、**暗号化ありの部屋だけが黙って返事をしなくなる**。2026-10-24 にわざと消して確かめた:

- 起動すると Hermes は新しい鍵を作り、Tuwunel は同じデバイスの鍵の差し替えを受け入れる。`gateway.log` は `server has stale keys ... attempting re-upload` の後 `E2EE enabled` で正常に見え、`required` でも止まらない
- Element X は Bot の古い鍵あてに部屋の鍵を送り続けるので、Hermes は復号できない。`gateway.log` には受け取った形跡すら無く、`errors.log` に `mau.client.crypto: Failed to decrypt ... no session with given ID ... found` が出る
- 暗号なしの部屋は使える

直し方（Bot のデバイスを作り直す。**@hermes のパスワードが要る**）。順番が大事で、新しくログインしてから `logout/all` すると新しいトークンも消える:

```bash
# 1. 止めて、今のトークンで Bot の全デバイスをログアウトする（パスワードの再入力は要らない）
systemctl --user stop hermes-gateway.service && cp -p ~/.hermes/.env ~/.hermes/.env.bak-before-new-token && T="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' ~/.hermes/.env | tr -d '"')" && curl -s -X POST -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8008/_matrix/client/v3/logout/all; echo; unset T
# → {}
# 2. 新しくログインして .env のトークンを差し替え、起動する
(umask 077; python3 ~/matrix_helper.py login hermes > ~/.config/m-hermes.env) && NEW="$(sed -n 's/^MATRIX_ACCESS_TOKEN=//p' ~/.config/m-hermes.env)" && [ -n "$NEW" ] && sed -i "s|^MATRIX_ACCESS_TOKEN=.*|MATRIX_ACCESS_TOKEN=$NEW|" ~/.hermes/.env && unset NEW && grep -c '^MATRIX_ACCESS_TOKEN=' ~/.hermes/.env; rm -f ~/.config/m-hermes.env; ls ~/.config/m-hermes.env
systemctl --user start hermes-gateway.service && sleep 25 && grep -h 'Matrix' ~/.hermes/logs/gateway.log | tail -6
# → access token belongs to a new device (... -> ...) — resetting local Olm account、cross-signing verified via recovery key、E2EE enabled
```

Element X 側の操作（`/discardsession` など）は要らなかった。壊れる前に送ったメッセージは Bot には読めないまま。1 の `logout/all` が失敗したとき（古いトークンが無効など）は、Tuwunel の管理用の部屋で古いデバイスを消すことになる（未確認）。

- **`crypto.db` はバックアップしない**。古いものに戻すと、上と同じ食い違いが起きる。壊れたら上の手順で作り直す
- **@hermes のパスワードを控えておく**（iPhone の「パスワード」アプリなど。Windows では iCloud for Windows の「iCloud パスワード」で同じものが見える）。忘れたら Tuwunel の管理用の部屋で再設定することになる（未確認）
- 復元キーは `.env` にしか無い。`.env` を失って復元キーも無くなると、Bot のデバイスに署名できず、Element X で「所有者に確認されていない」と出る（Hermes は相互署名の鍵がサーバーにあると作り直さない）

## 会話の自動リセット

Hermes のセッションは、放っておくと何日でも続く。毎回会話全体をモデルに送るので料金が増え、SKILL.md の更新も読み直されず、2026-10-22 には 10/18 から続いていた会話で Hermes が「今日」を 10/18 と思い込んだ（途中の `date +%F` で気づいて直した。サーバーの時計は正しかった）。

Hermes 本体の時間によるリセット（`config.yaml` の `session_reset`）は、v2026.9.11 のコミット `1d5d059`（stop time-triggered conversation rotation）で働かなくなった。今は `/new` と `/stop` でしか区切られない。そこで、公式のプラグイン一覧に community として載っている **`hermes-session-reset-policy`** を入れ、`session_reset` を働かせている（2026-10-24、Hermes v2026.9.24）。

- 仕組み: メッセージが届いたとき、前回のユーザーの依頼から `idle_minutes` たっているか、`at_hour` 時を過ぎているかを確かめ、そうなら `/new` と同じ処理で新しい会話にしてから、そのメッセージを処理する。タイマーは持たない。Hermes が作業している最中にはリセットしない。`/` で始まるコマンドは数えない
- **`!approve` の確認は出ない**（`/new` を手で送ったときだけ出る）。新しい会話になったことはモデルにも知らされない
- 中身: 一覧の版（`0.3.0 @ 0f2ea5ad`）を 2026-10-24 に読んだ。標準ライブラリだけで、外への通信・コマンドの実行は無く、使う権限はフック1つ（`pre_gateway_dispatch`）

```bash
hermes plugins search session-reset            # Pinned の版を確かめる（中身を読んだ版と同じか）
hermes plugins install hermes-session-reset-policy   # 「Enable now?」に y
hermes plugins doctor hermes-session-reset-policy    # OK ... 1 hook(s)
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-before-session-reset && cat >> ~/.hermes/config.yaml <<'EOF'

session_reset:
  mode: both          # idle と daily の両方
  idle_minutes: 360   # 6時間あいたら
  at_hour: 4          # 毎朝4時（サーバーの時刻）を過ぎたら
EOF
systemctl --user restart hermes-gateway.service
```

- 確かめ方: リセットされると `gateway.log` に `Invalidated run generation for agent:main:matrix:... (session_reset)` の行が出る（手で `/new` したときと同じ行）。プラグイン自身のログ（`session-reset-policy v0.3.0 armed` など）は `gateway.log` に出ない
- 試すときは `idle_minutes: 2` にして、2分以内なら前の依頼を覚えていること、3分あけると覚えていないことを確かめた
- やめる: `hermes plugins disable hermes-session-reset-policy` か、`session_reset` を `mode: none` にして gateway を再起動

## 会話の履歴

この部屋の会話をアプリで見られるようにする同期スクリプトの配置と運用は [`hermes-conversation-sync.md`](hermes-conversation-sync.md)。

## 更新

- Tuwunel・Caddy は apt の普段の更新に含まれる。Caddy の更新で reload に失敗した旨が出たら（`admin off` のため reload できない）`sudo systemctl restart caddy`
- Hermes を `hermes update` したら、`hermes pm status` が ok か、`gateway.log` に `matrix connected` が出るかを見る。あわせて `hermes plugins doctor hermes-session-reset-policy` が OK か、6時間以上あけた依頼で `(session_reset)` の行が出るかを見る（プラグインは Hermes の内部の関数を使っているので、本体の更新で動かなくなりうる。動かなくてもエラーにはならず、リセットされなくなるだけ）
- プラグインの更新は `hermes plugins check-updates` で分かる。更新する前に、新しい版の中身を読む
- `hermes update` の後は、`gateway.log` に `cross-signing verified via recovery key` と `E2EE enabled` が出るかを見て、暗号化ありの部屋で1度依頼する（返事が無ければ `errors.log` の `Failed to decrypt`）

## バックアップと戻し方

- Tuwunel の DB はバックアップしない（残すべき記録はアプリの DB に入る）。消えたら 3・4 と E2EE の手順をやり直す（相互署名の鍵も消えるので、`MATRIX_RECOVERY_KEY` を外して `MATRIX_RECOVERY_KEY_OUTPUT_FILE` から）
- E2EE をやめる: `.env` を `MATRIX_E2EE_MODE=off` にして gateway を再起動し、「Hermes」（暗号なし）の部屋を使う。暗号化ありの部屋は暗号なしに戻せない
- Caddy の発行元の鍵は `/root/caddy-pki-backup-YYYYMMDD.tgz`（root だけ）。無くなるとスマホに証明書を入れ直すことになる
- Telegram に戻す: Bot は削除済みなので作り直す（[`hermes-telegram.md`](../../../garden-app-private/docs/api/hermes-telegram.md) の冒頭）。`~/.hermes/.env.bak-before-matrix` などのバックアップの中の Telegram のトークンは使えない
- 全部やめる: `sudo systemctl disable --now tuwunel caddy`、`sudo ufw delete allow from <LANの範囲> to any port 8448 proto tcp`、`before.rules`／`before6.rules` の tuwunel の行を消して `sudo ufw reload`。`/var/lib/tuwunel` は purge でも消えないので手で消す

## 選ばなかった方法（2026-10-14 の調査）

- **Hermes の API サーバー＋Open WebUI**: チャットで送った写真をファイルに保存しない（`gateway/platforms/api_server.py` は画像を `image_url` のままモデルに渡すだけ）ので、写真をアプリに登録できない
- **SSH でターミナルの `hermes`**: スマホでの操作性が悪い
- **Matrix サーバーのソフト**: Synapse は重い（本格運用は PostgreSQL 推奨）。Continuwuity はボランティアの保守で `.deb` のビルドが落ちていた。Tuwunel（Conduit の後継、有給の開発者あり）を選んだ。Tuwunel で問題が出たら Synapse に切り替える（Caddy・ufw・証明書はそのまま使える）

## 参考

- [Matrix（Hermes Agent 公式）](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/matrix)
- [Tuwunel の Debian への導入](https://matrix-construct.github.io/tuwunel/deploying/debian.html)、[設定例](https://matrix-construct.github.io/tuwunel/configuration/examples.html)
- [Caddy の全体設定（admin・default_sni）](https://caddyserver.com/docs/caddyfile/options)
