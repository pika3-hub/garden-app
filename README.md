# 家庭菜園管理アプリ

家庭菜園での作物栽培を管理するWebアプリケーション。

個人の PC で動かし、その PC と自宅 LAN 内のスマホからブラウザで使うことを想定しています。見るだけなら誰でもできますが、登録・編集・削除はパスキー（Windows Hello・Face ID など）でログインした自分だけができます。インターネットへの公開や複数人での編集は想定していません（「ログインと編集」を参照）。

## 機能

- **作物・品種**: 作物（トマトなど）と品種（桃太郎など）を登録。品種のアイコン・色・画像は未設定なら作物から引き継ぐ
- **場所・見取り図**: 畑やプランターを登録し、作物アイコンを並べて配置図を作成。過去の配置も日付をさかのぼって確認できる
- **植え付け・栽培記録**: どこに何を植えたかと、その後の観察記録（メモ・写真）を残す。複数の植え付けへまとめて登録も可能
- **収穫記録**: 収穫日・収穫量・写真を記録。植え付けからの日数を自動表示。まとめて登録も可能
- **料理記録**: 収穫した野菜を使った料理を記録
- **日記・タスク**: 栽培日記と作業タスクを記録し、作物・場所・植え付けなどと関連付け
- **カレンダー**: 月ごとに植え付け・収穫・日記・タスクなどを表示
- **ダッシュボード**: 件数の集計、最近の記録、写真のスライド表示
- **写真**: 各データへの写真添付、写真のスライドショー表示。スマホで撮った写真を「写真プール」にまとめてアップロードし、後から各記録に割り当てられる。複数枚を選んで1枚ずつ続けて登録する「振り分け」画面（AI がメモなどを下書き）と、写真ごとの使用先へのリンクもある
- **補足情報**: 詳細画面にメモ・画像・外部リンク・YouTube 動画を追加
- **メモの Markdown 表示**: 各メモ欄は Markdown（見出し・箇条書き・太字・表・リンクなど）で書くと、詳細画面で整形して表示される
- **Hermes との会話の履歴**: AI エージェント（Hermes）とチャットでした会話を一覧・詳細で読み返せる。各データの詳細画面にも、そのデータが出てきた会話を表示
- **Hermes のアドバイス**: Hermes に相談した内容と答えをアドバイスとして残し、植え付け・品種・作物の詳細画面や一覧（`/advices/`）で振り返れる
- **外部API**: AI エージェントなどから、写真付きでデータを登録・更新し、登録済みの写真を取得できる JSON API（トークン認証、削除なし）
- **AIメモ下書き**: 作物・品種のメモを Claude（AI）が下書き。設定画面で登録した地域・栽培環境に合わせた内容になり、Web 検索も併用できる

## 技術スタック

- **バックエンド**: Python 3.12 / Flask 3.1 / SQLite / waitress（本番用サーバー）
- **フロントエンド**: Jinja2 テンプレート / Bootstrap 5.3・Bootstrap Icons（CDN）/ バニラ JS
- **画像処理**: Pillow（サムネイル生成）、pillow-heif（iPhone の HEIC を JPEG に変換）
- **Markdown**: markdown-it-py（メモ欄の表示）
- **AI**: Anthropic Python SDK（Claude API）
- **開発**: uv（パッケージ管理）/ pytest

## セットアップ

### 1. 依存関係のインストール

```bash
uv sync
```

### 2. データベース初期化

```bash
uv run python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app)"
```

### 3. AI機能の設定（任意）

メモの AI 下書きを使う場合は、Anthropic Console（console.anthropic.com）で API キーを発行し、プロジェクト直下に `.env` を作成します。

```
ANTHROPIC_API_KEY=発行したキー
# 任意: claude-opus-5-5（既定・品質重視）/ claude-sonnet-5-5（コスト・速度重視）/ claude-haiku-5-5（最安・最速）
ANTHROPIC_MODEL=claude-opus-5-5
```

起動後、ナビバーの「設定」で地域・栽培環境を登録してください。API の利用料は 1 件あたり1円未満〜約40円です（モデルと Web 検索の有無による）。

### 4. 起動

```bash
uv run python server.py   # 普段使い（waitress）
uv run python run.py      # 開発時（デバッグモード）
```

ブラウザで http://localhost:5000 にアクセスしてください。

### 5. スマホから使う（任意）

既定ではこの PC からのみアクセスできます。同じ自宅 LAN 内のスマホから使う場合は `.env` に次の 1 行を追加し、スマホのブラウザで `http://<PCのIPアドレス>:5000` を開きます。

```
HOST=0.0.0.0
```

- 閲覧は同じ LAN 内の誰でもできます。登録・編集・削除と AI 機能（課金に関わる操作）はログインした人だけです（「ログインと編集」を参照）。信頼できる自宅 LAN でのみ使い、Anthropic Console で月の使用上限を設定しておくと安心です
- `run.py` はデバッグモードで動くため、`HOST=0.0.0.0` のまま開発サーバーを起動すると、LAN 内からエラー画面のデバッガ経由で PC 上のコードを実行できてしまいます。スマホから使うときは `server.py` で起動してください

### 6. ログインと編集

- 見るだけなら、ログインなしで全部の画面を見られます。登録・編集・削除・写真のアップロード・AI 下書き・見取り図の保存などは、パスキー（パスワードは使いません）でログインした人だけができます。ログインしていない人にはそれらのボタンは表示されず、直接送信してもサーバーが拒否します
- 自分のパソコンで試すときは `http://localhost:5000`（`127.0.0.1` ではなく `localhost`）を開き、右上の「ログイン」から進みます。最初の1つ目のパスキーは、次のコマンドが表示する URL（15 分・1 回だけ有効）をブラウザで開いて登録します。以降のパスキーは設定画面の「この端末のパスキーを追加」で足せます

  ```
  uv run flask --app app passkey-register-link
  ```

- 設定は `.env` に書きます（開発では何も書かなくても動きます）: `PASSKEY_RP_ID`（既定 `localhost`）、`PASSKEY_ORIGIN`（既定 `http://localhost:5000`）、`OWNER_BASE_URL`（ログインの入口の URL。既定は `PASSKEY_ORIGIN`）、`SESSION_COOKIE_SECURE`（本番の既定は有効。HTTP だけで使うなら `0`）、`SECRET_KEY`（固定の値を入れておかないと、再起動のたびにログインが外れます）
- サーバーで HTTPS の入口を作る手順は `docs/api/migration-to-ubuntu.md`（手順 10）

### 7. 外部API（任意）

AI エージェント（Hermes Agent など）からデータを登録・更新する JSON API を、Web 画面とは別のポートで起動できます。`.env` に 32 文字以上のトークンを設定して `server.py` で起動します（`run.py` では起動しません）。

```
API_TOKEN=<uv run python -c "import secrets;print(secrets.token_urlsafe(32))" の出力>
API_HOST=0.0.0.0        # 別の PC のエージェントから使う場合
API_PORT=5001
WEB_BASE_URL=http://<PCのIPアドレス>:5000
```

仕様は [docs/api/README.md](docs/api/README.md)、ファイアウォールの設定は [docs/api/firewall-windows.md](docs/api/firewall-windows.md)、エージェント用スキルの下書きは [docs/api/hermes-skill/SKILL.md](docs/api/hermes-skill/SKILL.md) を参照してください。

## プロジェクト構造

```
garden-app/
├── app/
│   ├── __init__.py          # アプリ生成（ファクトリ）・ダッシュボード
│   ├── config.py            # 設定
│   ├── database.py          # SQLite 接続管理
│   ├── schema.sql           # 初期スキーマ
│   ├── api/                 # 外部API（/api/v1/*）
│   ├── models/              # データモデル（機能ごとに {feature}.py）
│   ├── routes/              # Blueprint（機能ごとに {feature}_routes.py）
│   ├── utils/               # アップロード・サムネイル・マイグレーション・OGP取得・AIメモ・Markdown表示等
│   ├── migrations/          # 増分マイグレーション SQL（連番）
│   ├── templates/           # Jinja2 テンプレート（機能ごとのフォルダ + 共通部品 _*.html）
│   └── static/
│       ├── css/
│       ├── js/
│       ├── images/          # UI画像・作物アイコン（crop_icons/）・見取り図背景（location_bg_images/）
│       └── uploads/         # アップロード画像（機能ごとのフォルダ）
├── docs/                    # 開発者向けドキュメント（外部APIは docs/api/）
├── instance/                # データベース（garden.db）
├── tests/                   # テスト（uv run pytest）
├── run.py                   # 開発サーバー起動
├── server.py                # 本番サーバー起動（waitress。Web ＋ 外部API）
├── test_data.py             # テストデータ投入
└── pyproject.toml
```
