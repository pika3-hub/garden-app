from app.database import get_db
from app.utils.timezone import get_jst_now


class Task:
    """タスクモデル"""

    # ステータス定義
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'

    STATUS_LABELS = {
        STATUS_PENDING: '未着手',
        STATUS_IN_PROGRESS: '進行中',
        STATUS_COMPLETED: '完了'
    }

    STATUS_BADGES = {
        STATUS_PENDING: 'bg-secondary',
        STATUS_IN_PROGRESS: 'bg-primary',
        STATUS_COMPLETED: 'bg-success'
    }

    @staticmethod
    def get_all(limit=None, offset=None, include_completed=True):
        """全タスクを取得（ページネーション対応）"""
        db = get_db()
        query = 'SELECT * FROM tasks'
        params = []

        if not include_completed:
            query += " WHERE status != 'completed'"

        query += ' ORDER BY due_date ASC NULLS LAST, created_at DESC'

        if limit:
            query += ' LIMIT ?'
            params.append(limit)
            if offset:
                query += ' OFFSET ?'
                params.append(offset)

        tasks = db.execute(query, params).fetchall()
        return [dict(task) for task in tasks]

    @staticmethod
    def get_by_id(task_id):
        """IDでタスクを取得"""
        db = get_db()
        task = db.execute(
            'SELECT * FROM tasks WHERE id = ?',
            (task_id,)
        ).fetchone()
        return dict(task) if task else None

    @staticmethod
    def create(data):
        """タスクを作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO tasks (title, description, due_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (data['title'], data.get('description'), data.get('due_date'),
             data.get('status', Task.STATUS_PENDING), now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(task_id, data):
        """タスクを更新"""
        db = get_db()
        db.execute(
            '''UPDATE tasks SET title = ?, description = ?, due_date = ?,
               status = ?, updated_at = ?
               WHERE id = ?''',
            (data['title'], data.get('description'), data.get('due_date'),
             data.get('status', Task.STATUS_PENDING), get_jst_now(), task_id)
        )
        db.commit()

    @staticmethod
    def delete(task_id):
        """タスクを削除"""
        db = get_db()
        db.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        db.commit()

    @staticmethod
    def count(status=None):
        """タスクの総数を取得"""
        db = get_db()
        if status:
            result = db.execute(
                'SELECT COUNT(*) as count FROM tasks WHERE status = ?',
                (status,)
            ).fetchone()
        else:
            result = db.execute('SELECT COUNT(*) as count FROM tasks').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def search(keyword=None, status=None, date_from=None, date_to=None):
        """タスクを検索"""
        db = get_db()
        query = '''SELECT * FROM tasks WHERE 1=1'''
        params = []

        if keyword:
            query += ' AND (title LIKE ? OR description LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        if status:
            query += ' AND status = ?'
            params.append(status)

        if date_from:
            query += ' AND due_date >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND due_date <= ?'
            params.append(date_to)

        query += ' ORDER BY due_date ASC NULLS LAST, created_at DESC'

        tasks = db.execute(query, params).fetchall()
        return [dict(task) for task in tasks]

    @staticmethod
    def get_pending(limit=5):
        """未完了タスクを取得（ダッシュボード用）"""
        db = get_db()
        tasks = db.execute(
            '''SELECT * FROM tasks
               WHERE status != 'completed'
               ORDER BY due_date ASC NULLS LAST, created_at DESC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(task) for task in tasks]

    @staticmethod
    def get_relations(task_id):
        """タスクに関連するデータを取得"""
        db = get_db()

        # 関連する作物を取得
        crops = db.execute(
            '''SELECT tr.*, c.name as crop_name, c.crop_type, c.variety
               FROM task_relations tr
               JOIN crops c ON tr.crop_id = c.id
               WHERE tr.task_id = ? AND tr.relation_type = 'crop' ''',
            (task_id,)
        ).fetchall()

        # 関連する場所を取得
        locations = db.execute(
            '''SELECT tr.*, l.name as location_name, l.location_type
               FROM task_relations tr
               JOIN locations l ON tr.location_id = l.id
               WHERE tr.task_id = ? AND tr.relation_type = 'location' ''',
            (task_id,)
        ).fetchall()

        # 関連する植え付け場所を取得
        location_crops = db.execute(
            '''SELECT tr.*, c.name as crop_name, l.name as location_name,
                      lc.planted_date, lc.status
               FROM task_relations tr
               JOIN location_crops lc ON tr.location_crop_id = lc.id
               JOIN crops c ON lc.crop_id = c.id
               JOIN locations l ON lc.location_id = l.id
               WHERE tr.task_id = ? AND tr.relation_type = 'location_crop' ''',
            (task_id,)
        ).fetchall()

        return {
            'crops': [dict(c) for c in crops],
            'locations': [dict(l) for l in locations],
            'location_crops': [dict(lc) for lc in location_crops]
        }

    @staticmethod
    def save_relations(task_id, relations):
        """タスクの関連を保存"""
        db = get_db()

        # 既存の関連を削除
        db.execute('DELETE FROM task_relations WHERE task_id = ?', (task_id,))

        # 作物の関連を保存
        for crop_id in relations.get('crop_ids', []):
            db.execute(
                '''INSERT INTO task_relations (task_id, relation_type, crop_id)
                   VALUES (?, 'crop', ?)''',
                (task_id, crop_id)
            )

        # 場所の関連を保存
        for location_id in relations.get('location_ids', []):
            db.execute(
                '''INSERT INTO task_relations (task_id, relation_type, location_id)
                   VALUES (?, 'location', ?)''',
                (task_id, location_id)
            )

        # 植え付け場所の関連を保存
        for location_crop_id in relations.get('location_crop_ids', []):
            db.execute(
                '''INSERT INTO task_relations (task_id, relation_type, location_crop_id)
                   VALUES (?, 'location_crop', ?)''',
                (task_id, location_crop_id)
            )

        db.commit()

    @staticmethod
    def update_status(task_id, status):
        """ステータスのみを更新"""
        db = get_db()
        db.execute(
            '''UPDATE tasks SET status = ?, updated_at = ?
               WHERE id = ?''',
            (status, get_jst_now(), task_id)
        )
        db.commit()

    @staticmethod
    def get_status_label(status):
        """ステータスの日本語ラベルを取得"""
        return Task.STATUS_LABELS.get(status, status)

    @staticmethod
    def get_status_badge(status):
        """ステータスのバッジクラスを取得"""
        return Task.STATUS_BADGES.get(status, 'bg-secondary')
