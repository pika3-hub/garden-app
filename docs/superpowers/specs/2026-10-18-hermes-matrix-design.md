# Hermes の LAN 内チャット（Matrix＋Element X）設計書

- 作成日: 2026-10-18
- ステータス: レビュー待ち
- 調査と方針: [`docs/api/hermes-local-chat.md`](../../api/hermes-local-chat.md)（2026-10-14）

## 1. 背景と目的

スマホから Hermes への依頼（文面・写真）と Hermes の返信は、今は Telegram 社のサーバーを通っている。これを自宅の LAN の中だけで済む経路に置き換える。OpenRouter（Hermes のモデル）と Anthropic（AI メモ下書き）への接続はこれまでどおり使う。

### 要件（ユーザー確認済み）

- 今の Ubuntu サーバー（garden-app と Hermes がある機械）に Matrix サーバーを同居させ、スマホからは Element X で使う
- 他の Matrix サーバーとの連携（フェデレーション）はしない。接続は LAN の中からだけ受ける
- HTTPS を使う。第1段階では E2EE（エンドツーエンド暗号化）を使わない
- Telegram はしばらく並行して残す
- 技術的な懸念は早い段階で確かめる（スマホの設定より前に、サーバーの中だけで Hermes との相性を確かめる）

### 成功の基準

- iPhone の Element X から写真付きで「栽培記録を登録して」と頼むと、今の Telegram と同じようにアプリに写真付きで登録される
- iPad からも同じように使える

### 前提

- サーバーを止めている間は使えない（今の Telegram 経由の Hermes と同じ）
- 外出先からは使えない。プッシュ通知は使わない

### スコープ外

- E2EE（第2段階で別に試す）
- Web 画面（5000番）の HTTPS 化（Caddy で後から足せる形にだけしておく）
- Telegram の停止
- garden-app のコードの変更

## 2. 決めたこと

| 項目 | 決定 | 理由 |
|---|---|---|
| Matrix サーバー | **Tuwunel**（Conduit 系統の後継、Rust 製） | 2人（自分と Bot）だけなので軽さが効く。公式の `.deb` があり、保守がいちばん活発（2026-10 時点の最新は v1.9.4）。Hermes の公式文書には名前が無いので、相性は構築の早い段階で確かめる |
| 代わりの候補 | Synapse | 動かないと分かったときに切り替える。Hermes の公式文書に名前がある |
| HTTPS | **Caddy** を前に置き、Caddy の内部の発行元（`tls internal`）で証明書を作る | 証明書の作成・更新が自動。後で Web 画面の HTTPS 化にも使える |
| スマホからの接続先 | `https://<サーバーのIP>:8448` | ルーターに LAN 内の名前を登録する機能が無い。IP は DHCP の手動割当で固定済み。443 は Web 画面の HTTPS 化用に空けておく |
| Matrix のサーバー名 | `garden.home.arpa` | ID の末尾になり、後から変えられない。IP にすると IP が変わったとき作り直しになる。`home.arpa` は家庭内ネットワーク用に予約された名前。フェデレーションをしないので名前を引けなくてよい |
| スマホのアプリ | Element X | Element の現行アプリ。Tuwunel は Element X が使う同期方式（Sliding Sync）に対応している |

## 3. 構成

```
iPhone / iPad（Element X）
   │  https://<サーバーのIP>:8448   ← LAN（<LANの範囲>）からだけ。ufw で許可
   ▼
Caddy（HTTPS を受けて転送）
   │  http://127.0.0.1:8008
   ▼
Tuwunel（Matrix サーバー）  ←──  Hermes の gateway（Matrix の Bot。http://127.0.0.1:8008 に直接つなぐ）
                                    │ 今までどおり
                                    ▼
                               garden-app の API（127.0.0.1:5001）
```

### Tuwunel

- 公式の `.deb` で入れる。systemd のサービスとして、garden・`<user>` とは別の専用ユーザーで動かす
- 待ち受けは `127.0.0.1:8008` だけ（LAN から直接はつながらない）
- 設定: サーバー名 `garden.home.arpa`、フェデレーションをしない、新規登録は閉じる（アカウントを作るときだけ一時的に開ける）
- サーバーの起動時に自動で立ち上がる

### Caddy

- apt で入れる。`<サーバーのIP>:8448` で HTTPS を受け、`127.0.0.1:8008` へ転送する
- 証明書は Caddy の内部の発行元で作る。iPhone・iPad には、その発行元（ルート）の証明書を1回だけ入れて信頼させる
- サーバーの起動時に自動で立ち上がる

### ufw

- LAN（`<LANの範囲>`）から 8448/tcp だけを許可する。8008 は開けない
- 既存のルール（22・5000 の許可、`<user>` → 5000 の遮断）は変えない

### アカウント

| アカウント | 用途 | 作る順 |
|---|---|---|
| `@<user>:garden.home.arpa` | 自分。Element X でログインする | 1番目（先に作ったアカウントが管理者になる） |
| `@hermes:garden.home.arpa` | Hermes の Bot | 2番目 |

### Hermes

- gateway に Matrix 用の部品（`mautrix`）を入れる（入れ方は段階0で調べる）
- `~/.hermes/.env` に次を書く
  - `MATRIX_HOMESERVER=http://127.0.0.1:8008`（サーバーの中で完結するので、Caddy の証明書を Hermes に信頼させなくてよい）
  - `MATRIX_ACCESS_TOKEN`（Bot のトークン）
  - `MATRIX_ALLOWED_USERS=@<user>:garden.home.arpa`
  - `MATRIX_ALLOWED_ROOMS`（Hermes と話す部屋の ID）
  - `MATRIX_E2EE_MODE=off`
- 部屋は**暗号化をオフにして**作る（後からオフにはできない。Element X は既定で暗号化ありの部屋を作るので注意）

### 変えないもの

- `/opt/garden-app` と garden-app のコード
- Hermes の実行ユーザーが 5000番・`/opt/garden-app` に触れない遮断。Tuwunel・Caddy は別のユーザー・別の場所に置く

## 4. 構築の段階と確かめ方

各段階の確認が済んでから次へ進む。どの段階でも Telegram 経由の Hermes はそのまま使える。サーバーの操作はユーザーが1ステップずつ実行し、結果を貼って照合する。

| 段階 | やること | 確かめ方 |
|---|---|---|
| 0. 下調べ | Hermes の版と仮想環境の場所、`mautrix` の入れ方を調べる。ディスク・メモリの空きを見る | 入れ方が決まる。決まらなければ中止して設計を見直す |
| 1. Tuwunel | `.deb` で入れて設定し、起動する | サーバーの中で `curl http://127.0.0.1:8008/_matrix/client/versions` が応答する |
| 2. Caddy＋ufw | Caddy を入れて 8448 で受ける。ufw で LAN から 8448 を許可する | メイン PC から `curl -k https://<サーバーのIP>:8448/_matrix/client/versions` が応答する |
| 3. アカウント | 登録を一時的に開け、自分 → Hermes の順に作って閉じる。Hermes のトークンを取る | 3つ目の登録が断られる |
| 4. Hermes との相性（サーバーの中だけ） | Hermes に Matrix の設定をして gateway を再起動する。自分のアカウントで curl から暗号化なしの部屋を作り、Hermes を招待し、文字だけのメッセージ → テスト画像付きのメッセージを送る | Hermes が応答する（`health` の確認など）。gateway のログで、Matrix と Telegram の両方が接続中で、画像を受け取ってファイルに保存できている |
| 5. スマホ（iPhone） | 発行元の証明書を入れて信頼させ、Element X でログインする。段階4の部屋に入る | ログインでき、証明書の警告が出ない。部屋の一覧と、段階4のやりとりが見える |
| 6. iPhone から写真付きで試す | Element X から写真付きで栽培記録の登録を頼む | アプリに写真付きで登録される。gateway のログで、受け取った画像の形式（JPEG か HEIC か）を見る |
| 7. 仕上げ | セッションの区切り方（Telegram の `/new` に当たるもの）を確かめる。iPad にも証明書を入れてログインする。発行元の鍵をコピーする。文書を更新する | iPad からも使える |

### Tuwunel では動かないと分かりうる段階

| 段階 | 起きうること | 起きやすさ |
|---|---|---|
| 4 | Hermes の部品（`mautrix`）がログイン・同期に失敗する。画像（Matrix の認証付きメディア）を取れない | 低〜中 |
| 5 | Element X の同期（Sliding Sync）が動かない。部屋の一覧が出ない、読み込みが終わらない | いちばん怪しい（Tuwunel は v1.9.3 で Element X の不具合を直したばかり） |

先にログで原因を見る。設定で直るもの、Tuwunel の新しい版で直っているものはそれで対処する。直らなければ、**その段階で Synapse に切り替える**。

- やり直す: 段階1（Tuwunel を消して Synapse を入れる）、段階3、段階4の部屋作り
- そのまま使える: Caddy・ufw・iPhone の証明書（Synapse も `127.0.0.1:8008` で待ち受けさせる）

### つまずきそうな点

- 段階6で写真が HEIC のまま届き、gateway の形式チェックで断られる場合は、Element X の送信設定（画像の最適化など）を確かめる。それでもだめなら、Hermes の受け取り側で対処できるかを別に調べる
- Hermes の公式の Matrix のページに `/new` の記載が無い（`/resume` などはある）。段階7で確かめる

### 戻し方

- Hermes の `.env` から Matrix の行を消して gateway を再起動すれば、Telegram だけの状態に戻る
- Tuwunel・Caddy を止め、ufw の 8448 を閉じれば、他に影響は残らない

## 5. 運用

### バックアップ

- Tuwunel の DB はバックアップしない。残すべき記録はアプリの DB に入る。消えたら、アカウントと部屋を作り直す（段階3・4のやり直し）
- Caddy の発行元の鍵は、構築直後に1回だけ root しか読めない場所にコピーする（無くなると iPhone・iPad に証明書を入れ直すことになる）。場所と権限は構築時に決める
- 設定ファイル（Tuwunel の設定、Caddyfile、Hermes の `.env` の Matrix の行）は、内容を手順書に記号で書いて残す

### 更新

- Caddy は apt の普段の更新に含まれる
- Tuwunel は GitHub のリリースから新しい `.deb` を取ってきて入れる（手順は手順書に書く）。フェデレーションをせず LAN 内だけで使うので、急ぐ更新はほぼない

### 秘密の値

- Hermes のトークンは `~/.hermes/.env`（600）にだけ置く
- 自分のアカウントのパスワードはパスワード管理アプリに置く
- どちらも文書・worklog に書かない

## 6. 文書の更新（構築後）

- `docs/api/hermes-local-chat.md`: 調査メモから、構成と構築・更新の手順に書き換える（固有値は記号）
- `CLAUDE.md`: Hermes の説明に Matrix の経路を足す
- `docs/api/hermes-skill/SKILL.md`: 2026-10-18 時点で Telegram 前提の書き方は無い。段階6・7で Matrix 固有の注意が見つかったら足す
- `docs/wishlist.md`: 第1段階が済んだら、その行を E2EE の検証に書き換える
- `../garden-app-private/local-env.md`: 実際のポート・ユーザー・場所を足す
