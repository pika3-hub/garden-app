# モデル開発ガイド

## データベーススキーマ

### テーブル一覧

| テーブル | 説明 | 主キー |
|---------|------|--------|
| crops | 作物マスタ | id |
| locations | 場所マスタ | id |
| plantings | 植え付け記録（作物×場所） | id |
| diary_entries | 日記 | id |
| harvests | 収穫記録 | id |
| diary_relations | 日記×関連エンティティ（多対多、relation_type で区別） | id |
| tasks | タスク | id |
| task_relations | タスク×関連エンティティ（多対多） | id |
| planting_records | 栽培観察記録（植え付けに紐づく） | id |

### 主要テーブル詳細

#### crops
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| name | TEXT | 作物名（必須） |
| variety | TEXT | 品種 |
| crop_type | VARCHAR(50) | 種類（必須） |
| planting_season | VARCHAR(50) | 植え付け時期 |
| harvest_season | VARCHAR(50) | 収穫時期 |
| characteristics | TEXT | 特徴 |
| notes | TEXT | メモ |
| icon_path | TEXT | 作物アイコンパス（`crop_icons/` 内） |
| image_color | TEXT | イメージカラー（HEX） |
| image_path | TEXT | 画像パス |
| created_at | DATETIME | 作成日時 |

#### locations
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| name | VARCHAR(100) | 場所名（必須） |
| location_type | VARCHAR(50) | 場所の種類（必須） |
| area_size | DECIMAL(10,2) | 面積（㎡） |
| sun_exposure | VARCHAR(50) | 日当たり |
| notes | TEXT | メモ |
| image_path | VARCHAR(255) | 画像パス |
| canvas_data | TEXT | 見取り図データ（version 2.0 JSON形式、旧Fabric.js形式は無視） |
| bg_image | TEXT | 見取り図の背景画像ファイル名（`location_bg_images/` 内のファイル名） |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

#### plantings
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| location_id | INTEGER | 場所ID（FK） |
| crop_id | INTEGER | 作物ID（FK） |
| planted_date | DATE | 植え付け日 |
| end_date | DATE | 栽培終了日（harvested 時に自動セット、任意） |
| status | TEXT | 状態（active/harvested/removed） |
| position_x | DECIMAL | キャンバスX座標 |
| position_y | DECIMAL | キャンバスY座標 |
| canvas_snapshot | TEXT | 栽培終了時の見取り図スナップショット（version 2.0 JSON） |
| created_at | DATETIME | 作成日時 |

#### diary_entries
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| entry_date | DATE | 記録日 |
| title | TEXT | タイトル（必須） |
| content | TEXT | 本文 |
| weather | TEXT | 天気 |
| image_path | TEXT | 画像パス |
| created_at | DATETIME | 作成日時 |

#### harvests
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| location_crop_id | INTEGER | 栽培記録ID（FK） |
| harvest_date | DATE | 収穫日 |
| quantity | REAL | 収穫量 |
| unit | TEXT | 単位 |
| notes | TEXT | メモ |
| image_path | TEXT | 画像パス |
| created_at | DATETIME | 作成日時 |

#### tasks
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| title | VARCHAR(200) | タイトル（必須） |
| description | TEXT | 説明 |
| due_date | DATE | 期限日 |
| status | VARCHAR(20) | ステータス（pending/in_progress/completed） |
| created_at | DATETIME | 作成日時 |
| updated_at | DATETIME | 更新日時 |

#### task_relations
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| task_id | INTEGER | タスクID（FK） |
| relation_type | VARCHAR(20) | 関連タイプ（crop/location/location_crop） |
| crop_id | INTEGER | 作物ID（FK、任意） |
| location_id | INTEGER | 場所ID（FK、任意） |
| location_crop_id | INTEGER | 栽培記録ID（FK、任意） |
| created_at | DATETIME | 作成日時 |

#### diary_relations
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| diary_id | INTEGER | 日記ID（FK） |
| relation_type | VARCHAR(20) | 関連タイプ（crop/location/location_crop/harvest） |
| crop_id | INTEGER | 作物ID（FK、任意） |
| location_id | INTEGER | 場所ID（FK、任意） |
| location_crop_id | INTEGER | 植え付けID（FK、任意） |
| harvest_id | INTEGER | 収穫ID（FK、任意） |
| created_at | TIMESTAMP | 作成日時 |

#### planting_records
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| location_crop_id | INTEGER | 植え付けID（FK → plantings） |
| recorded_at | DATE | 記録日（必須） |
| notes | TEXT | メモ |
| image_path | VARCHAR(255) | 画像パス |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

## SQLite Row の重複カラム名に関する注意（重要）

SQLiteの `Row` オブジェクトを dict として扱う場合、**同名カラムは最初に出現した値が優先される**（最後ではない）。これは `SELECT dr.*, lc.id as id` のようなクエリで、`dr.*` に含まれる `id`（リレーションテーブルのID）が `lc.id as id`（エンティティのID）を上書きする原因になる。

```python
# Bad — dr.* の id がリレーションテーブルの id になり、lc.id が無視される
'''SELECT dr.*, lc.id as id, c.name as crop_name ...
   FROM diary_relations dr
   JOIN plantings lc ON dr.location_crop_id = lc.id ...'''

# Good — dr.* を使わず、必要なカラムだけ明示的に列挙する
'''SELECT lc.id as id, c.name as crop_name, c.variety, ...
   FROM diary_relations dr
   JOIN plantings lc ON dr.location_crop_id = lc.id ...'''
```

**ルール**: リレーションテーブル（`diary_relations`, `task_relations`）を JOIN するクエリでは、`dr.*` や `tr.*` を使わず、必要なカラムを明示的に SELECT すること。特に `id` と `location_id` は衝突しやすい。

**追加ルール**: `get_relations()` 等のリレーション取得クエリでは、結合先エンティティの主キーを **リレーションテーブルのFKカラム名と同じエイリアス** で返すこと。ルート側で `r['location_crop_id']`, `r['crop_id']` 等のFK名でアクセスするため、エイリアスが一致しないと `KeyError` になる。

```python
# Bad — lc.id as id だけでは r['location_crop_id'] でアクセスできない
'''SELECT lc.id as id, c.name as crop_name ...
   FROM diary_relations dr
   JOIN plantings lc ON dr.location_crop_id = lc.id ...'''

# Good — FK名と同じエイリアスを含める
'''SELECT lc.id as id, lc.id as location_crop_id, c.name as crop_name ...
   FROM diary_relations dr
   JOIN plantings lc ON dr.location_crop_id = lc.id ...'''
```

## 日付カラムの注意点

SQLiteは動的型付けのため、日付の保存形式が一定でない場合がある。
クエリで日付を比較・取得する際は `DATE()` 関数で形式を統一すること。

```python
# Good
DATE(entry_date) as date
WHERE DATE(planted_date) BETWEEN ? AND ?

# Bad（形式不一致の可能性）
entry_date as date
WHERE planted_date BETWEEN ? AND ?
```

## モデルのコーディングパターン

```python
from app.database import get_db

class Example:
    @staticmethod
    def get_all():
        db = get_db()
        return db.execute('SELECT * FROM examples ORDER BY id').fetchall()

    @staticmethod
    def get_by_id(example_id):
        db = get_db()
        return db.execute('SELECT * FROM examples WHERE id = ?', (example_id,)).fetchone()

    @staticmethod
    def create(name, description=None):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO examples (name, description) VALUES (?, ?)',
            (name, description)
        )
        db.commit()
        return cursor.lastrowid
```
