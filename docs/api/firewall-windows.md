# Windows ファイアウォールの設定（Ubuntu へ移設するまでの暫定）

目的:

- エージェント PC（192.168.11.24）からは **API（5001）だけ**に届く
- スマホなど LAN 内の他の端末からは **Web 画面（5000）だけ**に届く
- エージェント PC から Web 画面（認証なし。削除もできる）には届かない

```
スマホ ──LAN──▶ :5000 Web 画面        ← LocalSubnet を許可、192.168.11.24 はブロック
Hermes(.24) ──▶ :5001 API（Bearer 必須） ← 192.168.11.24 だけ許可
```

以下は**管理者として開いた PowerShell** で実行する。

## 1. ネットワークプロファイルの確認

```powershell
Get-NetConnectionProfile
```

`NetworkCategory` が `Private` であること（`Public` だと下のルールが効かない）。違う場合は Windows の設定 → ネットワーク → プロパティで「プライベート」に変える。

このPC（192.168.11.10）とエージェント PC（192.168.11.24）の IP はルーター（192.168.11.1）の DHCP で「手動割当」にして固定してある。IP が変わると下のルールの `-RemoteAddress` と `.env` の `WEB_BASE_URL` がずれる（特に .24 が変わると Web 画面の遮断が効かなくなる）ので、ルーターを交換・初期化したときは割り当てし直す。

## 2. python.exe のプログラム単位の許可ルールを確認・無効化

初めてサーバーを起動したときのダイアログで「許可」を押していると、python.exe に対する**全ポート許可**のルールができている。これがあると、下のポート単位のルールに関係なく 5001 が LAN 全体に開いてしまう。

```powershell
Get-NetFirewallApplicationFilter | Where-Object { $_.Program -like '*python*' } |
  Get-NetFirewallRule | Select-Object DisplayName, Enabled, Direction, Action, Profile
```

`Direction = Inbound` かつ `Action = Allow` のルールがあれば、名前を確認してから無効化する:

```powershell
Disable-NetFirewallRule -DisplayName '<上で表示された名前>'
```

（`uv` の仮想環境の python.exe と、システムの python.exe の両方が出ることがある。両方確認する）

## 3. ポート単位のルールを追加

```powershell
New-NetFirewallRule -DisplayName "Garden API (Hermes only)" -Direction Inbound -Protocol TCP -LocalPort 5001 -RemoteAddress 192.168.11.24 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Garden Web (LAN)"        -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress LocalSubnet   -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Garden Web block Hermes" -Direction Inbound -Protocol TCP -LocalPort 5000 -RemoteAddress 192.168.11.24 -Action Block
```

ブロックのルールは許可のルールより優先されるので、192.168.11.24 から 5000 には届かない。

## 4. `.env` を設定してサーバーを再起動

```
HOST=0.0.0.0
API_HOST=0.0.0.0
API_PORT=5001
API_TOKEN=<uv run python -c "import secrets;print(secrets.token_urlsafe(32))" の出力>
WEB_BASE_URL=http://<このPCのIPアドレス>:5000
```

```powershell
uv run python server.py
```

## 5. 確認

| 実行元 | 操作 | 期待 |
|---|---|---|
| Ubuntu (.24) | `curl -sS -H "Authorization: Bearer $T" http://<PC>:5001/api/v1/health` | `{"ok": true, ...}` |
| Ubuntu (.24) | `curl -sS -m 5 http://<PC>:5000/` | タイムアウト（ブロック） |
| Ubuntu (.24) | `curl -sS http://<PC>:5001/` | JSON の 401（Web 画面は出ない） |
| スマホ | ブラウザで `http://<PC>:5000/` | 画面が開く |
| スマホ | ブラウザで `http://<PC>:5001/api/v1/health` | 開けない |

## 元に戻す

```powershell
Remove-NetFirewallRule -DisplayName "Garden API (Hermes only)"
Remove-NetFirewallRule -DisplayName "Garden Web (LAN)"
Remove-NetFirewallRule -DisplayName "Garden Web block Hermes"
```

手順 2 で無効化したルールは `Enable-NetFirewallRule -DisplayName '<名前>'` で戻せる。
