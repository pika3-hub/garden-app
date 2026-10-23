# LAN 内のチャット（Matrix＋Element X）で Hermes に依頼する

スマホから Hermes への依頼を、Telegram 社のサーバーを通さず自宅の LAN の中だけで済ませるための構成と手順。**2026-10-18 に構築済み**。2026-10-23 からはこれだけを使っている（Telegram は停止。[`hermes-telegram.md`](hermes-telegram.md)）。設計の経緯は [`../superpowers/specs/2026-10-18-hermes-matrix-design.md`](../superpowers/specs/2026-10-18-hermes-matrix-design.md)、構築時の計画は [`../superpowers/plans/2026-10-18-hermes-matrix.md`](../superpowers/plans/2026-10-18-hermes-matrix.md)。

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
| Caddy | apt（cloudsmith の公式リポジトリ）、`caddy.service`、`/etc/caddy/Caddyfile`、発行元 `/var/lib/caddy/.local/share/caddy/pki/authorities/local/` | `*:8448` で待ち受ける（TCP と HTTP/3 の UDP）。LAN 以外を止めているのは ufw。**管理用 API を止めている**（下記） |
| ufw | `8448/tcp ALLOW IN <LANの範囲>` | 8008 は開けない。既存の 22・5000 と `<user>` → 5000 の遮断はそのまま。**tuwunel ユーザーからの新しい接続をすべて拒否**（下記） |
| アカウント | `@<user>:garden.home.arpa`（管理者）、`@hermes:garden.home.arpa`（Bot） | 先に登録したほうが管理者になる |
| Hermes | `~/.hermes/.env` の `MATRIX_*`、部品は `hermes pm install --extra matrix` | Telegram の設定は 2026-10-23 に外した |
| スマホ | Element X（App Store では「Element X - Secure Chat & Call」、開発元 Vector Creations Limited） | 発行元の証明書を入れて信頼させる。**通知はオフ**（下記） |

### 守っていること

- **Caddy の管理用 API を止める（`admin off`）**。既定の `localhost:2019` はサーバー内のどのユーザーからも設定を書き換えられ、Hermes の実行ユーザーが「5000番へ転送する」設定を足すと、ufw の `<user>` → 5000 の遮断（[`migration-to-ubuntu.md`](migration-to-ubuntu.md) の 6章）をすり抜けられる。代わりに設定の反映は `systemctl reload` ではなく `restart`
- Tuwunel は他の Matrix サーバーに鍵を問い合わせない（`trusted_servers = []`。既定は matrix.org）
- 設定ファイルは `<user>` から読めない（登録用トークンを一時的に書くため）
- **Tuwunel は自分から接続しない（ufw）**。Hermes は Tuwunel のトークンを持つので、URL プレビュー（`preview_url`）や通知の送り先（pusher）を使えば、tuwunel ユーザーに代わりに `127.0.0.1:5000` へ接続させられるおそれがある（`<user>` → 5000 の遮断は tuwunel には効かない）。フェデレーションをしない Tuwunel には外への接続がいらないので、`before.rules`／`before6.rules` で tuwunel の `NEW` の接続を拒否している（スマホ・Hermes・Caddy からの接続への返事は止まらない）
- **スマホの通知は使わない**。Element X で通知を許可すると、Tuwunel に通知の送り先 `https://matrix.org/_matrix/push/v1/notify`（Element 社の通知サーバー）が登録され、メッセージのたびに部屋 ID・イベント ID・未読数が LAN の外に送られる（本文は送られない `event_id_only` 形式）。上の ufw のルールで送れないが、iPhone・iPad の 設定 → 通知 → Element X はオフにし、登録された送り先は消しておく（構築手順 5）

## 使い方

- Hermes の部屋で文面・写真を送る。写真（カメラロール）として送れば Element X が **JPEG に変換・縮小して送る**（例 1536×2048）ので、HEIC で断られない。「ファイル」として送ると HEIC のまま届き、受け取りで断られる見込み（Telegram と同じ。[`hermes-skill/SKILL.md`](hermes-skill/SKILL.md) の HEIC の注意）
- `/new` を送ると確認が出る。Matrix にはボタンが無いので、**`!approve`（今回だけ）・`!always`（以後確認しない）・`!cancel`** を文字で返す
- セッションは自動ではリセットされない。その日最初の依頼の前と、SKILL.md をサーバーに送った後は `/new` する（2026-10-22、10/18 から続いていた会話で Hermes が「今日」を 10/18 と思い込み、途中の `date +%F` で気づいて直した。サーバーの時計は正しかった）。理由と、自己改善（SKILL.md の書き換えは承認制。`/skills pending` で確認）の扱いは [`hermes-telegram.md`](hermes-telegram.md) の「使うときの注意」「Hermes の自己改善」（Telegram 時代の記録だが Matrix でも同じ）
- ホームチャンネル（定期実行の結果や gateway の終了通知の送り先）は設定していない（Telegram の `/sethome` は停止とともに無効。定期実行のジョブも無い）。必要になったら Hermes の部屋で `/sethome` を送る
- 一覧にある「garden.home.arpa Admin」は Tuwunel の管理用の部屋。書いた文が管理コマンドとして扱われるので、普段は開かない
- サーバーを起動すれば Tuwunel・Caddy・gateway は自動で立ち上がる

## 確認とログ

```bash
systemctl is-active tuwunel caddy garden-app; systemctl --user is-active hermes-gateway
grep -h 'matrix connected' ~/.hermes/logs/gateway.log | tail -1
```

- **gateway のログは `~/.hermes/logs/gateway.log` を見る**。`journalctl --user -u hermes-gateway` には WARNING 以上しか出ず、Matrix の接続や受け取った画像（`Cached user image at ...`）の行が見えない
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

Element X で部屋を作ると既定で暗号化ありになる（後からオフにできない）ので、部屋はこのスクリプトで作る。

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

## 更新

- Tuwunel・Caddy は apt の普段の更新に含まれる。Caddy の更新で reload に失敗した旨が出たら（`admin off` のため reload できない）`sudo systemctl restart caddy`
- Hermes を `hermes update` したら、`hermes pm status` が ok か、`gateway.log` に `matrix connected` が出るかを見る

## バックアップと戻し方

- Tuwunel の DB はバックアップしない（残すべき記録はアプリの DB に入る）。消えたら 3・4 をやり直す
- Caddy の発行元の鍵は `/root/caddy-pki-backup-YYYYMMDD.tgz`（root だけ）。無くなるとスマホに証明書を入れ直すことになる
- Telegram に戻す: Bot は削除済みなので作り直す（[`hermes-telegram.md`](hermes-telegram.md) の冒頭）。`~/.hermes/.env.bak-before-matrix` などのバックアップの中の Telegram のトークンは使えない
- 全部やめる: `sudo systemctl disable --now tuwunel caddy`、`sudo ufw delete allow from <LANの範囲> to any port 8448 proto tcp`、`before.rules`／`before6.rules` の tuwunel の行を消して `sudo ufw reload`。`/var/lib/tuwunel` は purge でも消えないので手で消す

## 選ばなかった方法（2026-10-14 の調査）

- **Hermes の API サーバー＋Open WebUI**: チャットで送った写真をファイルに保存しない（`gateway/platforms/api_server.py` は画像を `image_url` のままモデルに渡すだけ）ので、写真をアプリに登録できない
- **SSH でターミナルの `hermes`**: スマホでの操作性が悪い
- **Matrix サーバーのソフト**: Synapse は重い（本格運用は PostgreSQL 推奨）。Continuwuity はボランティアの保守で `.deb` のビルドが落ちていた。Tuwunel（Conduit の後継、有給の開発者あり）を選んだ。Tuwunel で問題が出たら Synapse に切り替える（Caddy・ufw・証明書はそのまま使える）

## 次の段階

- E2EE（暗号化ありの新しい部屋）を試す。`MATRIX_E2EE_MODE`、鍵の保管場所（crypto store）が壊れると Bot が黙って読めなくなる点に注意

## 参考

- [Matrix（Hermes Agent 公式）](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/matrix)
- [Tuwunel の Debian への導入](https://matrix-construct.github.io/tuwunel/deploying/debian.html)、[設定例](https://matrix-construct.github.io/tuwunel/configuration/examples.html)
- [Caddy の全体設定（admin・default_sni）](https://caddyserver.com/docs/caddyfile/options)
