import sqlite3
import os
from flask import g, current_app


def get_db():
    """データベース接続を取得"""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """データベース接続を閉じる"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """データベースを初期化"""
    with app.app_context():
        # instanceディレクトリが存在しない場合は作成
        os.makedirs(app.instance_path, exist_ok=True)

        db = get_db()
        with app.open_resource('schema.sql', mode='r', encoding='utf-8') as f:
            db.cursor().executescript(f.read())
        db.commit()

        # マイグレーションを実行
        run_migrations(app, db)

        print(f"Database initialized at: {app.config['DATABASE']}")

    # teardown関数を登録
    app.teardown_appcontext(close_db)


def run_migrations(app, db):
    """マイグレーションファイルを実行"""
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    if not os.path.exists(migrations_dir):
        return

    # マイグレーションファイルをソート順で取得
    migration_files = sorted([
        f for f in os.listdir(migrations_dir)
        if f.endswith('.sql')
    ])

    for filename in migration_files:
        filepath = os.path.join(migrations_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sql = f.read()
            db.cursor().executescript(sql)
            db.commit()
            print(f"Migration applied: {filename}")
        except Exception as e:
            # 既にテーブルが存在する場合などのエラーは無視
            if "already exists" not in str(e).lower():
                print(f"Migration warning for {filename}: {e}")


def query_db(query, args=(), one=False):
    """データベースクエリのヘルパー関数"""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv
