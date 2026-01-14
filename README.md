# 家庭菜園管理アプリ

家庭菜園での作物栽培を管理するWebアプリケーション。

## 機能

- **作物管理**: トマト、なすなどの作物情報を登録・管理
- **場所管理**: 畑、プランターなどの栽培場所を管理
- **作物紐付け**: どの場所でどの作物を育てているかを記録

## 技術スタック

- Python 3.12
- Flask 3.1
- SQLite
- Bootstrap 5
- uv (パッケージ管理)

## セットアップ

### 1. 依存関係のインストール

```bash
uv sync
```

### 2. データベース初期化

```bash
uv run python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app)"
```

### 3. 開発サーバー起動

```bash
uv run python run.py
```

ブラウザで http://localhost:5000 にアクセスしてください。

## プロジェクト構造

```
garden-manager/
├── app/                  # アプリケーションパッケージ
│   ├── models/          # データモデル
│   ├── routes/          # ルーティング
│   ├── templates/       # HTMLテンプレート
│   └── static/          # 静的ファイル(CSS, JS)
├── instance/            # インスタンス固有ファイル(DB等)
├── run.py              # アプリケーション起動スクリプト
└── pyproject.toml      # プロジェクト設定
```

## 開発状況

- [x] プロジェクト基盤構築
- [x] データベース設計
- [x] 作物管理機能（CRUD完全実装）
- [x] 場所管理機能（CRUD + 作物紐付け）
- [x] ダッシュボード（統計情報表示）

## 今後の予定

- 見取り図のキャンバス描画機能
- 管理日記機能
- 日記画像添付機能
