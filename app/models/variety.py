from app.database import get_db
from app.utils.timezone import get_jst_now


class Variety:
    """品種モデル（作物:品種 = 1:多）"""

    @staticmethod
    def get_all():
        """全品種を取得（親作物情報付き、作物名→created_at順）"""
        db = get_db()
        rows = db.execute(
            '''SELECT v.*, c.name AS crop_name, c.crop_type,
                      c.icon_path AS crop_icon_path, c.image_color AS crop_image_color,
                      c.image_path AS crop_image_path
               FROM varieties v
               JOIN crops c ON v.crop_id = c.id
               ORDER BY c.name, v.created_at DESC, v.id DESC'''
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(variety_id):
        """IDで品種を取得（親作物情報付き）"""
        db = get_db()
        row = db.execute(
            '''SELECT v.*, c.name AS crop_name, c.crop_type,
                      c.icon_path AS crop_icon_path, c.image_color AS crop_image_color,
                      c.image_path AS crop_image_path, c.notes AS crop_notes
               FROM varieties v
               JOIN crops c ON v.crop_id = c.id
               WHERE v.id = ?''',
            (variety_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_crop(crop_id):
        """作物に紐づく品種一覧を取得"""
        db = get_db()
        rows = db.execute(
            '''SELECT * FROM varieties WHERE crop_id = ?
               ORDER BY created_at DESC, id DESC''',
            (crop_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def create(data):
        """品種を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO varieties
               (crop_id, name, notes, icon_path, image_color, image_path,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['crop_id'], data['name'], data.get('notes'),
             data.get('icon_path') or None,
             data.get('image_color') or None,
             data.get('image_path'), now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(variety_id, data):
        """品種を更新"""
        db = get_db()
        db.execute(
            '''UPDATE varieties
               SET crop_id = ?, name = ?, notes = ?,
                   icon_path = ?, image_color = ?, image_path = ?, updated_at = ?
               WHERE id = ?''',
            (data['crop_id'], data['name'], data.get('notes'),
             data.get('icon_path') or None,
             data.get('image_color') or None,
             data.get('image_path'), get_jst_now(), variety_id)
        )
        db.commit()

    @staticmethod
    def delete(variety_id):
        """品種を削除（関連 plantings.variety_id は FK で SET NULL される）"""
        db = get_db()
        db.execute('DELETE FROM varieties WHERE id = ?', (variety_id,))
        db.commit()

    @staticmethod
    def count():
        """品種の総数を取得"""
        db = get_db()
        row = db.execute('SELECT COUNT(*) as count FROM varieties').fetchone()
        return row['count'] if row else 0

    @staticmethod
    def get_adjacent(variety_id):
        """全品種リスト順（親作物名→created_at）で前後の品種を取得"""
        db = get_db()
        all_rows = db.execute(
            '''SELECT v.id, v.name AS variety_name, c.name AS crop_name
               FROM varieties v
               JOIN crops c ON v.crop_id = c.id
               ORDER BY c.name, v.created_at DESC, v.id DESC'''
        ).fetchall()
        prev_v = next_v = None
        for i, r in enumerate(all_rows):
            if r['id'] == variety_id:
                if i > 0:
                    prev_v = dict(all_rows[i - 1])
                if i + 1 < len(all_rows):
                    next_v = dict(all_rows[i + 1])
                break
        return prev_v, next_v

    @staticmethod
    def search(keyword):
        """品種を検索（品種名・親作物名でLIKE）"""
        db = get_db()
        rows = db.execute(
            '''SELECT v.*, c.name AS crop_name, c.crop_type,
                      c.icon_path AS crop_icon_path, c.image_color AS crop_image_color
               FROM varieties v
               JOIN crops c ON v.crop_id = c.id
               WHERE v.name LIKE ? OR c.name LIKE ?
               ORDER BY c.name, v.created_at DESC''',
            (f'%{keyword}%', f'%{keyword}%')
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_effective_display(variety):
        """品種のアイコン/カラー/画像を親から継承した実効値で返す（dictを受け取り、同じdictに上書き）"""
        if variety is None:
            return None
        if not variety.get('icon_path'):
            variety['icon_path'] = variety.get('crop_icon_path')
        if not variety.get('image_color'):
            variety['image_color'] = variety.get('crop_image_color') or '#4CAF50'
        if not variety.get('image_path'):
            variety['image_path'] = variety.get('crop_image_path')
        return variety
