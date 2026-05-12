# DBを使った検証作業の安全ガイドライン

`instance/garden.db` はユーザーの**実データ**である。検証用クエリで誤って既存データを破壊するインシデントが過去に発生したため、以下のルールを厳守すること。

## 過去の事象

マイグレーション 016（plantings の crop_id/variety_id 排他化）の動作検証中に、テストデータの挿入後に `DELETE FROM crops`、`DELETE FROM varieties`、`DELETE FROM locations` を `WHERE` 句なしで実行した結果、ユーザーの crops 44件・varieties 55件・locations 9件が全削除された。`backup-pre-016` から復旧できたが、復旧作業に時間がかかり、ユーザーへの影響も大きかった。

## ルール

### 1. 検証前に必ずバックアップを取る

DDL や行を変更するDMLを書く場合は、実行前にバックアップを作成する：

```bash
cp instance/garden.db instance/garden.db.before-<change-name>
```

バックアップ無しに `DROP TABLE` / `ALTER TABLE` / 大量 `DELETE`/`UPDATE` を実行しない。

### 2. 本番DBで実データに触れる検証は避ける

- 一過性の検証はコピーDBに対して実行する：
  ```bash
  cp instance/garden.db /tmp/test.db
  # その後 /tmp/test.db に接続して検証
  ```
- またはトランザクション ROLLBACK を使って永続化を防ぐ：
  ```python
  conn.execute('BEGIN')
  # ... 検証クエリ ...
  conn.rollback()  # 必ず ROLLBACK
  ```

### 3. `DELETE` / `UPDATE` には必ず `WHERE` 句を付ける

- テストデータのクリーンアップでも `WHERE id IN (?, ?, ...)` で対象を限定する
- `WHERE` 句なしの `DELETE`/`UPDATE` を書きそうになったら、必ず一度立ち止まる
- サブエージェント等にSQL検証を委譲する場合も同様の制約を必ず指示する

### 4. テーブル再作成パターン（`plantings_new` 方式）はトリガー削除を先に行う

- 対象テーブルを参照するトリガーや VIEW がある場合、テーブルを `DROP` する前に `DROP TRIGGER` / `DROP VIEW` を実行
- 参照解決失敗で migration が中断すると、`plantings_new` のような中間テーブルが残った中途半端な状態になる
- 中断時の DB は冪等性が保証されない場合があるため、再実行前に手動回復または `before-<change-name>` バックアップから戻す

### 5. `init_db()` はマイグレーション失敗を warning として握り潰す

`app/database.py` の `run_migrations()` は例外を warning として print するだけで止まらない：

- 出力に `Migration warning:` が出たら必ず内容を確認する
- 失敗が続いた状態でアプリを起動すると、見えない不整合（中間テーブル残存・トリガー消失など）が蓄積する

## 推奨される検証フロー（マイグレーション編集時）

```bash
# 1. 必ずバックアップ
cp instance/garden.db instance/garden.db.before-NNN

# 2. アプリ初期化でマイグレーション適用
uv run python -c "from app import create_app; create_app()"
# → "Migration applied: NNN_xxx.sql" / "Migration warning" を確認

# 3. スキーマ確認
sqlite3 instance/garden.db ".schema plantings"
sqlite3 instance/garden.db ".schema crop_variety_view"

# 4. データ整合性チェック（重要：必ず PRAGMA foreign_key_check）
sqlite3 instance/garden.db "PRAGMA foreign_key_check"

# 5. アプリ動作確認（uv run python run.py 起動 → ブラウザまたは curl）
```

データの作成・更新・削除を伴う動作確認はブラウザ上で行う。SQLの一括 DML で「テストデータ挿入 → 検証 → 削除」のパターンは原則禁止。
