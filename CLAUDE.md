# CLAUDE.md - 家庭菜園管理アプリ AI アシスタントガイド

このドキュメントは、このコードベースで作業するAIアシスタント（Claudeなど）のための包括的なガイドです。アーキテクチャ、規約、ワークフロー、ベストプラクティスについて説明します。

## プロジェクト概要

**名称:** 家庭菜園管理アプリ
**タイプ:** Flask ベースの Web アプリケーション
**言語:** Python 3.12、日本語UI
**データベース:** SQLite
**目的:** ビジュアルキャンバスレイアウト、日記エントリ、作物と場所の関係を使用した家庭菜園の栽培管理

### 主な機能
- **作物管理:** 作物の種類、品種、特徴のCRUD操作
- **場所管理:** 畑やプランターの場所のCRUD、画像サポート付き
- **キャンバスエディター:** Fabric.jsを使用したビジュアル菜園レイアウトデザイナー（作物、図形、テキストのドラッグ&ドロップ）
- **栽培記録:** 作物と場所をリンクし、ステータス追跡（栽培中/収穫済み/削除済み）
- **日記システム:** 複数エンティティ間の関係と画像添付を持つ栽培日記
- **画像サポート:** 作物、場所、日記エントリの画像アップロード・管理（最大16MB）
- **検索とフィルター:** エンティティ全体でのキーワード検索、日記の日付範囲フィルタリング
- **ダッシュボード:** 統計情報と最近のアクティビティ概要

---

## クイックリファレンス

### プロジェクト構造
```
garden-app/
├── app/                      # メインアプリケーションパッケージ
│   ├── __init__.py          # Flaskファクトリパターン
│   ├── config.py            # 環境ベース設定
│   ├── database.py          # SQLite接続管理
│   ├── schema.sql           # 初期データベーススキーマ
│   ├── models/              # データモデル（静的メソッドパターン）
│   │   ├── crop.py
│   │   ├── location.py
│   │   ├── location_crop.py # 多対多関係
│   │   └── diary.py
│   ├── routes/              # Flask ブループリント
│   │   ├── crop_routes.py
│   │   ├── location_routes.py
│   │   └── diary_routes.py
│   ├── utils/               # ユーティリティ
│   │   ├── upload.py        # 画像アップロードヘルパー
│   │   └── migration.py     # マイグレーションユーティリティ
│   ├── migrations/          # データベースマイグレーション（増分SQL）
│   ├── templates/           # Jinja2 テンプレート
│   │   ├── base.html        # ナビバー付きベースレイアウト
│   │   ├── index.html       # ダッシュボード
│   │   ├── crops/           # 作物テンプレート
│   │   ├── locations/       # 場所テンプレート（+ canvas.html）
│   │   └── diary/           # 日記テンプレート
│   └── static/              # 静的アセット
│       ├── css/             # Bootstrap カスタマイズ
│       ├── js/              # キャンバスエディター、ユーティリティ
│       └── uploads/         # ユーザー画像（crops/, locations/, diary/）
├── instance/                # Flask インスタンスフォルダ（garden.db）
├── run.py                   # アプリケーション起動スクリプト
├── test_data.py             # テストデータ投入スクリプト
└── pyproject.toml           # プロジェクトメタデータ（uvパッケージマネージャー）
```

### 主要コマンド
```bash
# セットアップ
uv sync                           # 依存関係をインストール

# データベース
uv run python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app)"

# 実行
uv run python run.py              # 開発サーバー起動（localhost:5000）

# テストデータ
uv run python test_data.py        # サンプルデータを投入
```

---

## アーキテクチャパターン

### 1. Flask アプリケーションファクトリパターン

**ファイル:** `app/__init__.py`

```python
def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # ブループリントを登録
    from app.routes import crop_routes, location_routes, diary_routes
    app.register_blueprint(crop_routes.bp)

    # データベースクリーンアップ
    app.teardown_appcontext(close_db)

    return app
```

**要点:**
- 環境ベースの設定選択（development/production/testing）
- モジュラールートのためのブループリント登録
- teardownによるデータベース接続のクリーンアップ

### 2. 静的メソッドモデルパターン

**ORM不使用 - 静的メソッドによる直接SQL**

```python
class Crop:
    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute('SELECT * FROM crops ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def create(data):
        db = get_db()
        db.execute('''INSERT INTO crops (...) VALUES (?, ?, ...)''',
                   (data['name'], data['crop_type'], ...))
        db.commit()
        return db.execute('SELECT last_insert_rowid()').fetchone()[0]
```

**共通メソッド:**
- `get_all()` - 全レコード取得
- `get_by_id(id)` - 単一レコード取得
- `create(data)` - INSERT、IDを返す
- `update(id, data)` - レコード更新
- `delete(id)` - レコード削除
- `count()` - 総レコード数
- `search(keyword)` - LIKE クエリ

**データベースアクセス:**
- 接続には`get_db()`を使用（Flask g コンテキスト）
- Rowファクトリは辞書ライクなオブジェクトを返す: `row['field_name']`
- 変更後は必ず`db.commit()`を実行

### 3. RESTful ルートパターン

**構造:**
```python
bp = Blueprint('crops', __name__, url_prefix='/crops')

@bp.route('/')              # GET /crops/
def list():
    keyword = request.args.get('keyword', '')
    crops = Crop.search(keyword) if keyword else Crop.get_all()
    return render_template('crops/list.html', crops=crops)

@bp.route('/new')           # GET /crops/new
def new():
    return render_template('crops/form.html', crop=None)

@bp.route('/create', methods=['POST'])  # POST /crops/create
def create():
    data = dict(request.form)
    # 画像アップロード処理
    if 'image' in request.files:
        data['image_path'] = save_image(request.files['image'], 'crops')
    Crop.create(data)
    flash('作物を登録しました', 'success')
    return redirect(url_for('crops.list'))

@bp.route('/<int:id>')      # GET /crops/123
def detail(id):
    crop = Crop.get_by_id(id)
    return render_template('crops/detail.html', crop=crop)

@bp.route('/<int:id>/edit') # GET /crops/123/edit
def edit(id):
    crop = Crop.get_by_id(id)
    return render_template('crops/form.html', crop=crop)

@bp.route('/<int:id>/update', methods=['POST'])  # POST /crops/123/update
def update(id):
    crop = Crop.get_by_id(id)
    data = dict(request.form)

    # 画像更新処理
    if 'image' in request.files and request.files['image'].filename:
        if crop['image_path']:
            delete_image(crop['image_path'])
        data['image_path'] = save_image(request.files['image'], 'crops')
    elif 'delete_image' in request.form and crop['image_path']:
        delete_image(crop['image_path'])
        data['image_path'] = None

    Crop.update(id, data)
    flash('作物を更新しました', 'success')
    return redirect(url_for('crops.detail', id=id))

@bp.route('/<int:id>/delete', methods=['POST'])  # POST /crops/123/delete
def delete(id):
    crop = Crop.get_by_id(id)
    if crop['image_path']:
        delete_image(crop['image_path'])
    Crop.delete(id)
    flash('作物を削除しました', 'success')
    return redirect(url_for('crops.list'))
```

**URL規約:**
- リソース名は複数形: `/crops`, `/locations`, `/diary`
- ネストされたアクション: `/<id>/edit`, `/<id>/update`, `/<id>/delete`
- ネストされたリソース: `/locations/<id>/crops/<crop_id>/position`

### 4. テンプレート継承パターン

**ベーステンプレート:** `app/templates/base.html`
- Bootstrap 5.3.0 + Bootstrap Icons
- ナビゲーションリンク付きナビバー
- フラッシュメッセージ表示システム
- ブロック構造: `title`, `content`, `extra_css`, `extra_js`

**子テンプレート:**
```html
{% extends "base.html" %}

{% block title %}作物一覧{% endblock %}

{% block content %}
<div class="container mt-4">
    <h1>作物一覧</h1>
    <!-- コンテンツ -->
</div>
{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/custom.css') }}">
{% endblock %}
```

**フォームパターン（作成/編集で再利用）:**
```html
{% if crop %}
    <form action="{{ url_for('crops.update', id=crop.id) }}" method="post">
{% else %}
    <form action="{{ url_for('crops.create') }}" method="post">
{% endif %}
    <input name="name" value="{{ crop.name if crop else '' }}" required>
    <button type="submit">{{ '更新' if crop else '登録' }}</button>
</form>
```

---

## データベーススキーマリファレンス

### 主要テーブル

**crops** - 作物タイプ定義
```sql
id INTEGER PRIMARY KEY
name TEXT NOT NULL              -- 作物名（例: "トマト"）
crop_type TEXT                  -- 種類（例: "野菜", "果物"）
variety TEXT                    -- 品種（例: "ミニトマト"）
characteristics TEXT            -- 特徴
planting_season TEXT            -- 植え付け時期
harvest_season TEXT             -- 収穫時期
notes TEXT                      -- メモ
image_path TEXT                 -- 画像パス（migration 003）
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**locations** - 菜園の場所
```sql
id INTEGER PRIMARY KEY
name TEXT NOT NULL              -- 場所名（例: "南側の畑"）
location_type TEXT              -- 種類（例: "畑", "プランター"）
area_size REAL                  -- 面積（㎡）
sun_exposure TEXT               -- 日当たり
notes TEXT
image_path TEXT                 -- 画像パス（migration 003）
canvas_data TEXT                -- キャンバスJSON（migration 001）
created_at TIMESTAMP
updated_at TIMESTAMP
```

**location_crops** - 栽培記録（多対多）
```sql
id INTEGER PRIMARY KEY
location_id INTEGER FK          -- 場所
crop_id INTEGER FK              -- 作物
planted_date DATE               -- 植え付け日
quantity INTEGER                -- 数量
status TEXT CHECK IN ('active', 'harvested', 'removed')  -- 状態
notes TEXT
position_x DECIMAL              -- キャンバス位置X（migration 001）
position_y DECIMAL              -- キャンバス位置Y（migration 001）
created_at TIMESTAMP
updated_at TIMESTAMP
```

**diary_entries** - 栽培日記（migration 002）
```sql
id INTEGER PRIMARY KEY
title TEXT NOT NULL
content TEXT
entry_date DATE NOT NULL
weather TEXT                    -- 天気
status TEXT DEFAULT 'published'
image_path TEXT                 -- 画像パス（migration 003）
created_at TIMESTAMP
updated_at TIMESTAMP
```

**diary_relations** - 日記の多対多関係（migration 002）
```sql
id INTEGER PRIMARY KEY
diary_id INTEGER FK             -- 日記エントリ
relation_type TEXT CHECK IN ('crop', 'location', 'location_crop')
crop_id INTEGER FK              -- 任意: 関連する作物
location_id INTEGER FK          -- 任意: 関連する場所
location_crop_id INTEGER FK     -- 任意: 関連する栽培記録
created_at TIMESTAMP
```

### インデックス（パフォーマンス最適化）
```sql
-- 栽培記録
CREATE INDEX idx_location_crops_location ON location_crops(location_id);
CREATE INDEX idx_location_crops_crop ON location_crops(crop_id);
CREATE INDEX idx_location_crops_status ON location_crops(status);

-- 日記
CREATE INDEX idx_diary_relations_diary ON diary_relations(diary_id);
CREATE INDEX idx_diary_entries_date ON diary_entries(entry_date);
CREATE INDEX idx_diary_relations_crop ON diary_relations(crop_id);
CREATE INDEX idx_diary_relations_location ON diary_relations(location_id);
```

---

## 開発ワークフロー

### 新機能の追加

**1. データベース変更（必要な場合）**

マイグレーションファイルを作成: `app/migrations/004_feature_name.sql`

```sql
-- べき等性のため、常にIF NOT EXISTSを使用
ALTER TABLE crops ADD COLUMN new_field TEXT IF NOT EXISTS;

CREATE TABLE IF NOT EXISTS new_table (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_new_table_name ON new_table(name);
```

**マイグレーションの自動実行:**
- マイグレーションはアプリ起動時にアルファベット順に実行される
- エラーはログに記録されるがアプリはクラッシュしない（"already exists"はスキップ）
- 手動実行は不要

**2. モデル更新**

既存モデルにメソッドを追加するか、新しいモデルを作成:

```python
# app/models/crop.py
class Crop:
    @staticmethod
    def get_by_season(season):
        db = get_db()
        rows = db.execute(
            'SELECT * FROM crops WHERE planting_season LIKE ? ORDER BY name',
            (f'%{season}%',)
        ).fetchall()
        return [dict(row) for row in rows]
```

**3. ルート実装**

適切なブループリントにルートを追加:

```python
# app/routes/crop_routes.py
@bp.route('/season/<season>')
def by_season(season):
    crops = Crop.get_by_season(season)
    return render_template('crops/list.html', crops=crops, title=f'{season}の作物')
```

**4. テンプレート更新**

テンプレートを作成または修正:

```html
<!-- app/templates/crops/list.html -->
{% extends "base.html" %}
{% block content %}
<div class="container mt-4">
    <h1>{{ title if title else '作物一覧' }}</h1>
    {% for crop in crops %}
        <div class="card">
            <h5>{{ crop.name }}</h5>
        </div>
    {% endfor %}
</div>
{% endblock %}
```

**5. テスト**

```bash
# アプリを再起動（マイグレーションが自動実行される）
uv run python run.py

# ブラウザでテスト
# 必要に応じてテストデータを追加
uv run python test_data.py
```

### 画像アップロードワークフロー

**統合パターン:**

```python
from app.utils.upload import save_image, delete_image, allowed_file

# ルートのcreate/update内
data = dict(request.form)

# 新規アップロード処理
if 'image' in request.files and request.files['image'].filename:
    file = request.files['image']
    if allowed_file(file.filename):
        image_path = save_image(file, 'crops')  # 戻り値: 'crops/uuid.jpg'
        data['image_path'] = image_path
    else:
        flash('許可されていないファイル形式です', 'error')
        return redirect(...)

# 削除処理（更新時）
if 'delete_image' in request.form and entity['image_path']:
    delete_image(entity['image_path'])
    data['image_path'] = None

# 削除処理（エンティティ削除時）
if entity['image_path']:
    delete_image(entity['image_path'])
```

**テンプレートパターン:**

```html
<!-- アップロードフォーム -->
<form method="post" enctype="multipart/form-data">
    <input type="file" name="image" accept="image/png,image/jpeg,image/gif,image/webp">
    {% if entity and entity.image_path %}
        <label>
            <input type="checkbox" name="delete_image"> 画像を削除
        </label>
    {% endif %}
</form>

<!-- 画像表示 -->
{% if entity.image_path %}
<img src="{{ url_for('static', filename='uploads/' + entity.image_path) }}"
     class="img-fluid" alt="{{ entity.name }}">
{% endif %}
```

**重要なファイル:**
- `app/utils/upload.py` - ヘルパー関数
- `app/static/uploads/{crops,locations,diary}/` - 保存フォルダ
- Config: `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH`, `ALLOWED_EXTENSIONS`

### キャンバスエディター統合

**キャンバスデータフロー:**
1. ユーザーが`locations/canvas.html`でキャンバスを編集
2. 自動保存（3秒デバウンス）→ POST `/locations/<id>/canvas/save`
3. `Location.save_canvas_data()`がJSONを保存し、location_cropの位置を更新
4. ドラッグによる位置更新 → POST `/locations/<id>/crops/<lc_id>/position`

**キャンバスJSON構造:**
```json
{
  "version": "1.0",
  "objects": [
    {
      "type": "group",
      "left": 120,
      "top": 80,
      "cropId": 1,
      "locationCropId": 5,
      "cropName": "ミニトマト",
      "plantedDate": "2024-05-15"
    },
    {
      "type": "rect",
      "left": 50,
      "top": 50,
      "width": 200,
      "height": 150,
      "fill": "rgba(76, 175, 80, 0.3)"
    }
  ]
}
```

**キャンバス機能の追加:**

```javascript
// app/static/js/canvas-editor.js

class CanvasEditor {
    addCustomTool() {
        // 1. ツールバーにツールボタンを追加
        const toolBtn = document.createElement('button');
        toolBtn.id = 'customTool';
        toolBtn.innerHTML = '<i class="bi-icon"></i>';
        document.querySelector('.tool-palette').appendChild(toolBtn);

        // 2. キーボードショートカットを登録
        this.addKeyboardShortcut('X', 'customTool');

        // 3. ツールロジックを実装
        this.canvas.on('mouse:down', (e) => {
            if (this.activeTool !== 'customTool') return;
            // ツール実装
        });
    }
}
```

**作物サイドバーパターン:**
```html
<!-- canvas.html -->
<div class="crop-sidebar">
    {% for lc in location_crops %}
    <div class="crop-item" draggable="true"
         data-crop-id="{{ lc.crop_id }}"
         data-location-crop-id="{{ lc.id }}"
         data-crop-name="{{ lc.crop_name }}"
         data-planted-date="{{ lc.planted_date }}">
        {{ lc.crop_name }}
    </div>
    {% endfor %}
</div>
```

---

## コード規約

### Pythonスタイル
- **命名:**
  - クラス: `PascalCase`（Crop, Location, DiaryEntry）
  - 関数/変数: `snake_case`
  - 定数: `UPPER_SNAKE_CASE`
- **インポート:** stdlib → サードパーティ → ローカルの順にグループ化
- **Docstring:** 不要（コードは自己文書化）
- **型ヒント:** 使用しない（Flaskコンテキスト）

### SQL規約
- **テーブル:** 小文字複数形（crops, locations, diary_entries）
- **カラム:** 小文字スネークケース（crop_type, planted_date, image_path）
- **外部キー:** 単数形のエンティティ名 + `_id`（crop_id, location_id）
- **タイムスタンプ:** 常に`created_at`, `updated_at`を含める（TIMESTAMP DEFAULT CURRENT_TIMESTAMP）
- **ステータスフィールド:** テキスト列挙型（'active', 'harvested', 'removed'）

### テンプレート規約
- **ファイル:** 小文字、エンティティ別に整理（crops/list.html, locations/detail.html）
- **共有フォーム:** `form.html`を条件ロジックで作成/編集に再利用
- **CSSクラス:** Bootstrap ユーティリティ + カスタムケバブケース（.crop-sidebar, .canvas-editor）
- **フラッシュカテゴリ:** 'success', 'error', 'warning', 'info'（Bootstrap alertクラス）

### JavaScript規約
- **命名:** camelCase（変数、関数）、PascalCase（クラス）
- **構成:** 複雑な機能にはクラス（CanvasEditor）、シンプルなタスクにはユーティリティ関数
- **イベント委譲:** 動的コンテンツには委譲リスナーを優先
- **AJAX:** ネイティブのfetch()を使用

### URLルーティング規約
- **リソース:** 複数形の名前（`/crops`, `/locations`, `/diary`）
- **アクション:** 動詞ベースのサフィックス（`/create`, `/update`, `/delete`, `/plant`, `/harvest`）
- **ID:** 整数パラメータ（`/<int:id>`, `/<int:crop_id>`）
- **ネスト:** 論理的な階層（`/locations/<id>/crops/<crop_id>/position`）

---

## よくあるタスク

### 新しいエンティティタイプの追加

**1. データベーススキーマ**（`app/schema.sql`またはマイグレーション）
```sql
CREATE TABLE IF NOT EXISTS new_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_new_entities_name ON new_entities(name);
```

**2. モデル**（`app/models/new_entity.py`）
```python
from app.database import get_db

class NewEntity:
    @staticmethod
    def get_all():
        db = get_db()
        return [dict(row) for row in db.execute('SELECT * FROM new_entities').fetchall()]

    @staticmethod
    def get_by_id(entity_id):
        db = get_db()
        row = db.execute('SELECT * FROM new_entities WHERE id = ?', (entity_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        db = get_db()
        db.execute(
            'INSERT INTO new_entities (name, description, image_path) VALUES (?, ?, ?)',
            (data.get('name'), data.get('description'), data.get('image_path'))
        )
        db.commit()
        return db.execute('SELECT last_insert_rowid()').fetchone()[0]

    @staticmethod
    def update(entity_id, data):
        db = get_db()
        db.execute(
            'UPDATE new_entities SET name = ?, description = ?, image_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (data.get('name'), data.get('description'), data.get('image_path'), entity_id)
        )
        db.commit()

    @staticmethod
    def delete(entity_id):
        db = get_db()
        db.execute('DELETE FROM new_entities WHERE id = ?', (entity_id,))
        db.commit()
```

**3. ルート**（`app/routes/new_entity_routes.py`）
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.new_entity import NewEntity
from app.utils.upload import save_image, delete_image

bp = Blueprint('new_entities', __name__, url_prefix='/new-entities')

@bp.route('/')
def list():
    entities = NewEntity.get_all()
    return render_template('new_entities/list.html', entities=entities)

@bp.route('/new')
def new():
    return render_template('new_entities/form.html', entity=None)

@bp.route('/create', methods=['POST'])
def create():
    data = dict(request.form)
    if 'image' in request.files and request.files['image'].filename:
        data['image_path'] = save_image(request.files['image'], 'new_entities')
    NewEntity.create(data)
    flash('登録しました', 'success')
    return redirect(url_for('new_entities.list'))

@bp.route('/<int:id>')
def detail(id):
    entity = NewEntity.get_by_id(id)
    return render_template('new_entities/detail.html', entity=entity)

@bp.route('/<int:id>/edit')
def edit(id):
    entity = NewEntity.get_by_id(id)
    return render_template('new_entities/form.html', entity=entity)

@bp.route('/<int:id>/update', methods=['POST'])
def update(id):
    entity = NewEntity.get_by_id(id)
    data = dict(request.form)

    if 'image' in request.files and request.files['image'].filename:
        if entity['image_path']:
            delete_image(entity['image_path'])
        data['image_path'] = save_image(request.files['image'], 'new_entities')
    elif 'delete_image' in request.form and entity['image_path']:
        delete_image(entity['image_path'])
        data['image_path'] = None

    NewEntity.update(id, data)
    flash('更新しました', 'success')
    return redirect(url_for('new_entities.detail', id=id))

@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    entity = NewEntity.get_by_id(id)
    if entity['image_path']:
        delete_image(entity['image_path'])
    NewEntity.delete(id)
    flash('削除しました', 'success')
    return redirect(url_for('new_entities.list'))
```

**4. ブループリント登録**（`app/__init__.py`）
```python
from app.routes import new_entity_routes
app.register_blueprint(new_entity_routes.bp)
```

**5. テンプレート作成**（`app/templates/new_entities/`）
- `list.html` - エンティティ一覧
- `detail.html` - 単一エンティティビュー
- `form.html` - 作成/編集フォーム

**6. アップロードディレクトリ作成**
```bash
mkdir -p app/static/uploads/new_entities
touch app/static/uploads/new_entities/.gitkeep
```

### 検索/フィルター機能の追加

```python
# モデルメソッド
@staticmethod
def search(keyword=None, date_from=None, date_to=None):
    db = get_db()
    query = 'SELECT * FROM table_name WHERE 1=1'
    params = []

    if keyword:
        query += ' AND (field1 LIKE ? OR field2 LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    if date_from:
        query += ' AND date_field >= ?'
        params.append(date_from)

    if date_to:
        query += ' AND date_field <= ?'
        params.append(date_to)

    query += ' ORDER BY created_at DESC'
    rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]

# ルートでの使用
@bp.route('/')
def list():
    keyword = request.args.get('keyword', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    entities = Model.search(keyword, date_from, date_to)
    return render_template('list.html', entities=entities,
                          keyword=keyword, date_from=date_from, date_to=date_to)
```

### 多対多関係の追加

**例: 日記エントリと作物/場所のリンク**

```python
# モデルメソッド（DiaryEntry）
@staticmethod
def get_relations(diary_id):
    db = get_db()
    rows = db.execute('''
        SELECT dr.*, c.name as crop_name, l.name as location_name
        FROM diary_relations dr
        LEFT JOIN crops c ON dr.crop_id = c.id
        LEFT JOIN locations l ON dr.location_id = l.id
        WHERE dr.diary_id = ?
    ''', (diary_id,)).fetchall()
    return [dict(row) for row in rows]

@staticmethod
def save_relations(diary_id, relations):
    db = get_db()
    # 既存の関係をクリア
    db.execute('DELETE FROM diary_relations WHERE diary_id = ?', (diary_id,))

    # 新しい関係を挿入
    for rel in relations:
        db.execute('''
            INSERT INTO diary_relations (diary_id, relation_type, crop_id, location_id, location_crop_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (diary_id, rel['type'], rel.get('crop_id'), rel.get('location_id'), rel.get('location_crop_id')))

    db.commit()

# ルートでの使用
@bp.route('/create', methods=['POST'])
def create():
    data = dict(request.form)
    diary_id = DiaryEntry.create(data)

    # 関係を処理
    relations = []
    if 'crop_ids' in request.form:
        for crop_id in request.form.getlist('crop_ids'):
            relations.append({'type': 'crop', 'crop_id': crop_id})

    DiaryEntry.save_relations(diary_id, relations)
    return redirect(url_for('diary.detail', id=diary_id))
```

---

## トラブルシューティング

### データベースの問題

**データベースが初期化されない:**
```bash
# 手動初期化
uv run python -c "from app import create_app; from app.database import init_db; app = create_app(); init_db(app)"
```

**マイグレーションエラー:**
- マイグレーションファイルのSQL構文を確認
- マイグレーションが`IF NOT EXISTS`を使用してべき等であることを確認
- マイグレーション番号のシーケンスを確認（001, 002, 003...）
- アプリ起動時のコンソールログを確認

**データベースロック:**
```bash
# SQLiteは複数プロセスがアクセスするとロックされる
# 他のPythonプロセスを終了するか再起動
pkill -f "python run.py"
```

### 画像アップロードの問題

**画像が保存されない:**
- ディレクトリが存在するか確認: `app/static/uploads/{folder}/`
- ファイルパーミッションを確認
- `MAX_CONTENT_LENGTH`設定を確認（デフォルト16MB）
- `upload.py`の許可拡張子を確認

**画像が表示されない:**
- パス形式を確認: `folder/filename.ext`（先頭にスラッシュなし）
- テンプレートで使用: `url_for('static', filename='uploads/' + path)`
- ファイルがファイルシステムに存在するか確認

### キャンバスの問題

**キャンバスが保存されない:**
- ブラウザコンソールでJavaScriptエラーを確認
- エンドポイントを確認: POST `/locations/<id>/canvas/save`
- JSON形式の妥当性を確認
- location_idがデータベースに存在することを確認

**作物の位置が更新されない:**
- `position_x`と`position_y`カラムが存在することを確認（migration 001）
- エンドポイントを確認: POST `/locations/<id>/crops/<lc_id>/position`
- location_crop_idが有効であることを確認

---

## AIアシスタントのベストプラクティス

### 変更を行う際

1. **修正前に読む:** 変更前に必ずReadツールを使用して既存ファイルを確認
2. **既存パターンに従う:** 既存コードのスタイルと構造に合わせる
3. **規約を維持:** 確立された命名パターンとファイル構成を使用
4. **変更後にテスト:** タスクを完了と見なす前に変更が動作することを確認
5. **シンプルに保つ:** 過度に設計しない。現在の複雑さレベルに合わせる

### データベース変更

1. **常にマイグレーションを作成:** 新機能のために`schema.sql`を直接変更しない
2. **IF NOT EXISTSを使用:** マイグレーションをべき等にする
3. **連番を付ける:** 3桁のプレフィックスを使用（001, 002, 003...）
4. **インデックスを追加:** 外部キーと頻繁にクエリされるフィールドに
5. **モデルメソッドを更新:** 新しいフィールド/テーブルに対応するPythonメソッドを追加

### コード構成

1. **ファイルごとに1機能:** ルート/モデルを単一エンティティに集中させる
2. **テンプレートを再利用:** 別ファイルの代わりにフォームで条件ロジックを使用
3. **ユーティリティを集中化:** 共有コードは`app/utils/`に配置
4. **ブループリントパターンに従う:** すべてのルートをブループリント経由で登録
5. **重複を避ける:** 共通パターンをヘルパー関数に抽出

### UI/UX考慮事項

1. **Bootstrapを優先:** カスタムCSSを書く前にBootstrapユーティリティを使用
2. **フラッシュメッセージ:** アクションに対して常にユーザーフィードバックを提供
3. **確認ダイアログ:** 削除にはmain.jsの`confirmDelete()`を使用
4. **レスポンシブデザイン:** 複数の画面サイズでテスト
5. **アクセシビリティ:** 画像にaltテキスト、入力にラベルを含める

### セキュリティ考慮事項

1. **ファイルアップロードを検証:** `allowed_file()`で拡張子をチェック
2. **入力をサニタイズ:** パラメータ化クエリを使用（`?`プレースホルダーで既に実施済み）
3. **権限をチェック:** 削除/更新前にエンティティが存在することを確認
4. **エラーを優雅に処理:** ファイル操作にtry/exceptを使用
5. **内部情報を公開しない:** ユーザーに適切なエラーメッセージを返す

---

## 付録: 完全なモデルAPIリファレンス

### Cropモデル（`app/models/crop.py`）

```python
Crop.get_all() → List[Dict]
Crop.get_by_id(crop_id: int) → Dict | None
Crop.create(data: Dict) → int  # 挿入されたIDを返す
Crop.update(crop_id: int, data: Dict) → None
Crop.delete(crop_id: int) → None
Crop.count() → int
Crop.search(keyword: str) → List[Dict]
```

### Locationモデル（`app/models/location.py`）

```python
Location.get_all() → List[Dict]
Location.get_by_id(location_id: int) → Dict | None
Location.create(data: Dict) → int
Location.update(location_id: int, data: Dict) → None
Location.delete(location_id: int) → None
Location.count() → int
Location.search(keyword: str) → List[Dict]
Location.get_canvas_data(location_id: int) → str | None  # JSON文字列
Location.save_canvas_data(location_id: int, canvas_dict: Dict) → None
```

### LocationCropモデル（`app/models/location_crop.py`）

```python
LocationCrop.get_by_location(location_id: int, status: str = 'active') → List[Dict]
LocationCrop.get_by_crop(crop_id: int, status: str = 'active') → List[Dict]
LocationCrop.get_by_id(location_crop_id: int) → Dict | None
LocationCrop.plant(data: Dict) → int  # 栽培記録を作成
LocationCrop.harvest(location_crop_id: int) → None  # statusを'harvested'に設定
LocationCrop.remove(location_crop_id: int) → None  # statusを'removed'に設定
LocationCrop.count_active() → int
LocationCrop.get_all_active() → List[Dict]  # 詳細を含むすべての栽培中の記録
LocationCrop.update_position(location_crop_id: int, x: float, y: float) → None
LocationCrop.get_crops_with_position(location_id: int) → List[Dict]
LocationCrop.clear_positions_except(location_id: int, location_crop_ids: List[int]) → None
```

### DiaryEntryモデル（`app/models/diary.py`）

```python
DiaryEntry.get_all(limit: int = None, offset: int = 0) → List[Dict]
DiaryEntry.get_by_id(diary_id: int) → Dict | None
DiaryEntry.create(data: Dict) → int
DiaryEntry.update(diary_id: int, data: Dict) → None
DiaryEntry.delete(diary_id: int) → None
DiaryEntry.count() → int
DiaryEntry.search(keyword: str = None, date_from: str = None, date_to: str = None) → List[Dict]
DiaryEntry.get_recent(limit: int = 5) → List[Dict]
DiaryEntry.get_relations(diary_id: int) → List[Dict]
DiaryEntry.save_relations(diary_id: int, relations: List[Dict]) → None
DiaryEntry.get_by_crop(crop_id: int) → List[Dict]
DiaryEntry.get_by_location(location_id: int) → List[Dict]
```

---

## 追加リソース

### 設定リファレンス（`app/config.py`）

```python
class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    DATABASE = os.path.join(Config.BASE_DIR, 'instance', 'garden.db')
    SECRET_KEY = 'dev-secret-key-change-in-production'
    UPLOAD_FOLDER = os.path.join(Config.BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
```

### キャンバスエディターのキーボードショートカット

- `S` - 選択ツール
- `R` - 矩形ツール
- `C` - 円ツール
- `L` - 線ツール
- `T` - テキストツール
- `D` - 選択したオブジェクトを削除
- `Ctrl+Z` / `Cmd+Z` - 元に戻す
- `Ctrl+Shift+Z` / `Cmd+Shift+Z` - やり直す
- `Delete` / `Backspace` - 選択を削除

### Fabric.js統合ポイント

**CanvasEditorの主要メソッド:**
```javascript
constructor(canvasElementId, locationId)  // キャンバスを初期化
loadCanvas()                              // サーバーからキャンバスデータを読み込み
saveCanvas()                              // デバウンスされた自動保存（3秒）
addCropToCanvas(cropData)                 // キャンバスに作物アイコンを追加
updateCropPosition(locationCropId, x, y)  // サーバーに位置を同期
addToHistory()                            // 元に戻す/やり直し用に状態を保存
undo() / redo()                           // 履歴ナビゲーション
enableDrawingMode(tool)                   // 描画ツールをアクティブ化
```

---

## クイック決定ツリー

**既存エンティティにフィールドを追加する必要がある？**
→ マイグレーションを作成、モデルメソッドを更新、フォームテンプレートを更新

**新しいページを追加する必要がある？**
→ ルート関数を追加、base.htmlを継承するテンプレートを作成

**エンティティ間の関係を追跡する必要がある？**
→ ジャンクションテーブル（diary_relationsのような）を作成、get/saveのモデルメソッドを追加

**画像アップロードを追加する必要がある？**
→ ルートで`save_image()`を使用、フォームに`enctype="multipart/form-data"`を追加

**検索を追加する必要がある？**
→ LIKEクエリを使用したsearchメソッドをモデルに追加、リストテンプレートに検索フォームを追加

**キャンバス機能のリクエスト？**
→ canvas-editor.jsを修正、locations/canvas.htmlでテスト

**APIエンドポイントが必要？**
→ JSONレスポンスルートを追加、JavaScriptからfetch()でテスト

このドキュメントは、コードベースが進化するにつれて、新しいパターンと規約を反映するように更新する必要があります。
