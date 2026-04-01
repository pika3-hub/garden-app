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

        query += ''' ORDER BY CASE status
                        WHEN 'in_progress' THEN 1
                        WHEN 'pending' THEN 2
                        WHEN 'completed' THEN 3
                     END,
                     CASE WHEN status != 'completed' THEN due_date END ASC NULLS LAST,
                     CASE WHEN status = 'completed' THEN due_date END DESC NULLS LAST'''

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

        query += ''' ORDER BY CASE status
                        WHEN 'in_progress' THEN 1
                        WHEN 'pending' THEN 2
                        WHEN 'completed' THEN 3
                     END,
                     CASE WHEN status != 'completed' THEN due_date END ASC NULLS LAST,
                     CASE WHEN status = 'completed' THEN due_date END DESC NULLS LAST'''

        tasks = db.execute(query, params).fetchall()
        return [dict(task) for task in tasks]

    @staticmethod
    def get_pending(limit=5):
        """未完了タスクを取得（ダッシュボード用）"""
        db = get_db()
        tasks = db.execute(
            '''SELECT * FROM tasks
               WHERE status != 'completed'
               ORDER BY CASE status
                           WHEN 'in_progress' THEN 1
                           WHEN 'pending' THEN 2
                           WHEN 'completed' THEN 3
                        END, due_date ASC NULLS LAST
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
            '''SELECT tr.*, c.name as crop_name, c.crop_type, c.variety,
                      c.icon_path, c.image_color
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
            '''SELECT lc.id as id, lc.id as location_crop_id, c.name as crop_name, c.variety,
                      c.icon_path, c.image_color, l.name as location_name,
                      lc.location_id, lc.planted_date, lc.status,
                      (SELECT pr.image_path FROM planting_records pr
                       WHERE pr.location_crop_id = lc.id AND pr.image_path IS NOT NULL AND pr.image_path != ''
                       ORDER BY pr.recorded_at DESC, pr.created_at DESC LIMIT 1) as latest_record_image
               FROM task_relations tr
               JOIN plantings lc ON tr.location_crop_id = lc.id
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
    def get_adjacent(task_id):
        """現在のタスクの前後を取得（一覧の表示順に基づく）"""
        db = get_db()
        tasks = db.execute(
            '''SELECT id, title FROM tasks
               ORDER BY CASE status
                           WHEN 'in_progress' THEN 1
                           WHEN 'pending' THEN 2
                           WHEN 'completed' THEN 3
                        END,
                        CASE WHEN status != 'completed' THEN due_date END ASC NULLS LAST,
                        CASE WHEN status = 'completed' THEN due_date END DESC NULLS LAST'''
        ).fetchall()

        task_list = [dict(t) for t in tasks]
        current_index = None
        for i, t in enumerate(task_list):
            if t['id'] == task_id:
                current_index = i
                break

        if current_index is None:
            return None, None

        prev_task = task_list[current_index - 1] if current_index > 0 else None
        next_task = task_list[current_index + 1] if current_index < len(task_list) - 1 else None

        return prev_task, next_task

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

    @staticmethod
    def get_upcoming_task_counts(relation_type, entity_ids):
        """エンティティごとの期限間近タスク数を一括取得（一覧画面用）"""
        if not entity_ids:
            return {}
        db = get_db()
        col_map = {
            'crop': 'crop_id',
            'location': 'location_id',
            'location_crop': 'location_crop_id'
        }
        col = col_map.get(relation_type)
        if not col:
            return {}
        placeholders = ','.join('?' * len(entity_ids))
        rows = db.execute(f'''
            SELECT tr.{col} as entity_id, COUNT(DISTINCT t.id) as task_count
            FROM task_relations tr
            JOIN tasks t ON tr.task_id = t.id
            WHERE tr.relation_type = ?
              AND tr.{col} IN ({placeholders})
              AND t.status != 'completed'
              AND t.due_date IS NOT NULL
              AND DATE(t.due_date) <= DATE('now', '+9 hours', '+7 days')
            GROUP BY tr.{col}
        ''', [relation_type] + list(entity_ids)).fetchall()
        return {row['entity_id']: row['task_count'] for row in rows}

    @staticmethod
    def get_incomplete_tasks_for_entity(relation_type, entity_id):
        """エンティティに関連する未完了タスクを取得（詳細画面用）"""
        db = get_db()
        col_map = {
            'crop': 'crop_id',
            'location': 'location_id',
            'location_crop': 'location_crop_id'
        }
        col = col_map.get(relation_type)
        if not col:
            return []
        rows = db.execute(f'''
            SELECT DISTINCT t.id, t.title, t.due_date, t.status
            FROM tasks t
            JOIN task_relations tr ON t.id = tr.task_id
            WHERE tr.relation_type = ?
              AND tr.{col} = ?
              AND t.status != 'completed'
            ORDER BY CASE t.status
                        WHEN 'in_progress' THEN 1
                        WHEN 'pending' THEN 2
                     END,
                     CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,
                     t.due_date ASC
        ''', (relation_type, entity_id)).fetchall()
        return [dict(r) for r in rows]
