import sqlite3
import os
import shutil
import sys

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.config import Config


def run_migration(migration_file):
    """マイグレーションSQLを実行"""
    db_path = Config.DATABASE

    # データベースファイルの存在確認
    if not os.path.exists(db_path):
        print(f"エラー: データベースファイルが見つかりません: {db_path}")
        return False

    # バックアップ作成
    backup_path = f"{db_path}.backup"
    shutil.copy2(db_path, backup_path)
    print(f"データベースをバックアップしました: {backup_path}")

    # マイグレーション実行
    conn = sqlite3.connect(db_path)
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
        print(f"マイグレーション完了: {migration_file}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"マイグレーションエラー: {e}")
        # バックアップからリストア
        shutil.copy2(backup_path, db_path)
        print(f"バックアップから復元しました")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    migration_file = 'app/migrations/001_add_canvas_support.sql'
    if run_migration(migration_file):
        print("\n[OK] マイグレーションが正常に完了しました")
    else:
        print("\n[ERROR] マイグレーションに失敗しました")
