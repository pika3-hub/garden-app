# モデル開発ガイド

## データベーススキーマ

### テーブル一覧

| テーブル | 説明 | 主キー |
|---------|------|--------|
| crops | 作物マスタ | id |
| varieties | 品種マスタ（作物:品種 = 1:多） | id |
| locations | 場所マスタ | id |
| plantings | 植え付け記録（作物×品種×場所） | id |
| diary_entries | 日記 | id |
| harvests | 収穫記録 | id |
| diary_relations | 日記×関連エンティティ（多対多、relation_type で区別） | id |
| tasks | タスク | id |
| task_relations | タスク×関連エンティティ（多対多） | id |
| planting_records | 栽培観察記録（植え付けに紐づく） | id |

### ビュー

| ビュー | 説明 |
|--------|------|
| crop_variety_view | 作物×品種の結合ビュー（品種なし行も含む UNION ALL）。display 用の `crop_name`, `variety`, `icon_path`, `image_color` 等を提供 |

### 主要テーブル詳細

#### crops
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| name | TEXT | 作物名（必須） |
| crop_type | VARCHAR(50) | 種類（必須） |
| notes | TEXT | メモ（Markdown形式） |
| icon_path | TEXT | 作物アイコンパス（`crop_icons/` 内） |
| image_color | TEXT | イメージカラー（HEX、デフォルト `#4CAF50`） |
| image_path | TEXT | 画像パス |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

#### varieties
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| crop_id | INTEGER | 親作物ID（FK → crops、ON DELETE CASCADE） |
| name | TEXT | 品種名（必須） |
| notes | TEXT | メモ（Markdown形式） |
| icon_path | TEXT | アイコンパス（nullable、未設定なら親作物から継承） |
| image_color | TEXT | イメージカラー（nullable、未設定なら親作物から継承） |
| image_path | VARCHAR(255) | 画像パス（nullable、未設定なら親作物から継承） |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

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
| location_id | INTEGER | 場所ID（FK、必須） |
| crop_id | INTEGER | 作物ID（FK → crops、ON DELETE CASCADE、**nullable**） |
| variety_id | INTEGER | 品種ID（FK → varieties、ON DELETE CASCADE、**nullable**） |
| planted_date | DATE | 植え付け日 |
| end_date | DATE | 栽培終了日（harvested 時に自動セット、任意） |
| status | TEXT | 状態（active/harvested/removed） |
| position_x | DECIMAL | キャンバスX座標 |
| position_y | DECIMAL | キャンバスY座標 |
| canvas_snapshot | TEXT | 栽培終了時の見取り図スナップショット（version 2.0 JSON） |
| created_at | DATETIME | 作成日時 |

**制約（重要）**: `CHECK ((crop_id IS NOT NULL AND variety_id IS NULL) OR (crop_id IS NULL AND variety_id IS NOT NULL))`
- 作物として植えた場合: `crop_id=X, variety_id=NULL`
- 品種として植えた場合: `crop_id=NULL, variety_id=Y`（作物情報は品種の親を辿って解決）
- 両方同時セット・両方NULL は禁止
- `Planting.plant()` / `update_all()` は `_normalize_crop_variety()` で自動正規化（variety_id 指定時は crop_id を NULL に強制）

**品種削除時の挙動**: `trg_promote_variety_plantings_before_delete` トリガーにより、品種単独削除時は植え付けが「親作物の植え付け（品種なし）」に昇格する（`crop_id = OLD.crop_id, variety_id = NULL` への付け替え）。

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
| relation_type | VARCHAR(20) | 関連タイプ（crop/variety/location/location_crop） |
| crop_id | INTEGER | 作物ID（FK、任意） |
| variety_id | INTEGER | 品種ID（FK → varieties、ON DELETE CASCADE、任意） |
| location_id | INTEGER | 場所ID（FK、任意） |
| location_crop_id | INTEGER | 栽培記録ID（FK、任意） |
| created_at | DATETIME | 作成日時 |

#### diary_relations
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| diary_id | INTEGER | 日記ID（FK） |
| relation_type | VARCHAR(20) | 関連タイプ（crop/variety/location/location_crop/harvest） |
| crop_id | INTEGER | 作物ID（FK、任意） |
| variety_id | INTEGER | 品種ID（FK → varieties、ON DELETE CASCADE、任意） |
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

#### photo_pool
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| image_path | VARCHAR(255) | 画像相対パス（例 `photo_pool/uuid.jpg`） |
| original_filename | VARCHAR(255) | 元ファイル名（参考） |
| file_size | INTEGER | バイト数 |
| notes | TEXT | ユーザーメモ |
| taken_at | TIMESTAMP | EXIFから抽出した撮影日時 |
| created_at | TIMESTAMP | 登録日時 |
| updated_at | TIMESTAMP | 更新日時 |

#### photo_pool_usages
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| photo_pool_id | INTEGER | 写真プールID（FK → photo_pool、ON DELETE CASCADE） |
| entity_type | VARCHAR(20) | 使用先種別（crop/location/diary/harvest/planting_record/supplement） |
| entity_id | INTEGER | 使用先エンティティID |
| copied_image_path | VARCHAR(255) | コピー先の相対パス（追跡用） |
| created_at | TIMESTAMP | 使用日時 |

#### supplements
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER | 主キー |
| entity_type | VARCHAR(20) | エンティティ種別（crop/variety/location/diary/task/harvest） |
| entity_id | INTEGER | 親エンティティのID |
| supplement_type | VARCHAR(20) | 補足種別（text/image/url/youtube） |
| title | VARCHAR(200) | 表示ラベル（任意） |
| content | TEXT | ペイロード（text:本文, image:画像パス, url:完全URL, youtube:動画ID or 動画ID:秒数） |
| sort_order | INTEGER | 表示順（将来用、現在は登録順） |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

## crop_variety_view（VIEW）の使い方

plantings は排他形式 `(crop_id=X, variety_id=NULL)` または `(crop_id=NULL, variety_id=Y)` で保存されているため、VIEW 側も品種行では `crop_id=NULL`、作物行では `variety_id=NULL` を返す。JOIN は **両側 IFNULL 化** が必須:

```sql
JOIN crop_variety_view cv
  ON IFNULL(cv.crop_id, -1) = IFNULL(lc.crop_id, -1)
  AND IFNULL(cv.variety_id, -1) = IFNULL(lc.variety_id, -1)
```

- ビューは「品種行（`crop_id=NULL`, `variety_id=Y`）」と「作物行（`crop_id=X`, `variety_id=NULL`）」を UNION ALL で返す
- `cv.effective_crop_id` は常に作物ID（品種行なら親作物ID、作物行なら自身）— 「作物Xの植え付け一覧（品種経由含む）」は `WHERE cv.effective_crop_id = ?` で書く
- `cv.icon_path`, `cv.image_color`, `cv.image_path`, `cv.notes` は `COALESCE(v.*, c.*)` で品種→作物の継承を表現
- `cv.*` は使わない（SQLite Row 重複カラム名対策） — 必要カラムを明示する

`diary_relations.crop_id` や `task_relations.crop_id` は作物レベル参照なので、ビューではなく crops テーブルを直接 JOIN し、`variety` は `NULL as variety` として明示する。

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
