# モデル開発ガイド

## データベーススキーマ

### テーブル一覧

| テーブル | 説明 | 主キー |
|---------|------|--------|
| crops | 作物マスタ | id |
| locations | 場所マスタ | id |
| location_crops | 栽培記録（作物×場所） | id |
| diary_entries | 日記 | id |
| harvests | 収穫記録 | id |
| diary_crops | 日記×作物（多対多） | diary_id, crop_id |
| diary_locations | 日記×場所（多対多） | diary_id, location_id |
| diary_location_crops | 日記×栽培記録（多対多） | diary_id, location_crop_id |
| diary_harvests | 日記×収穫（多対多） | diary_id, harvest_id |

### 主要テーブル詳細

#### crops
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| name | TEXT | 作物名（必須） |
| variety | TEXT | 品種 |
| characteristics | TEXT | 特徴 |
| image_path | TEXT | 画像パス |
| created_at | DATETIME | 作成日時 |

#### locations
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| name | TEXT | 場所名（必須） |
| description | TEXT | 説明 |
| image_path | TEXT | 画像パス |
| canvas_data | TEXT | キャンバスJSON |
| created_at | DATETIME | 作成日時 |

#### location_crops
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| location_id | INTEGER | 場所ID（FK） |
| crop_id | INTEGER | 作物ID（FK） |
| planted_date | DATE | 植え付け日 |
| status | TEXT | 状態（growing/harvested/removed） |
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
