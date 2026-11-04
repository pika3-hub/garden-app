import hashlib
import json
import os
from flask import current_app
from app.database import get_db
from app.utils.timezone import get_jst_now
from app.utils.search_text import fold
from app.utils.canvas_areas import TOP_DIRECTIONS

# 背景を選んでいない場所の見取り図の背景（一覧の先頭）
DEFAULT_BG_IMAGE = 'soil.webp'


def _top_direction(data):
    """見取り図の上の方角。北・東・南・西以外（空を含む）は NULL にする"""
    value = data.get('canvas_top_direction')
    return value if value in TOP_DIRECTIONS else None


def order_bg_images(names):
    """背景画像の一覧の並び: 既定の背景を先頭、残りは名前順"""
    rest = sorted(n for n in names if n != DEFAULT_BG_IMAGE)
    return [DEFAULT_BG_IMAGE] + rest if DEFAULT_BG_IMAGE in names else rest


class CanvasConflictError(Exception):
    """見取り図を読んでから書くまでに、ほかの保存が何度も入って書けなかった"""


class Location:
    """場所モデル"""

    @staticmethod
    def get_all():
        """全場所を取得"""
        db = get_db()
        locations = db.execute(
            'SELECT * FROM locations ORDER BY created_at DESC'
        ).fetchall()
        return [dict(location) for location in locations]

    @staticmethod
    def get_by_id(location_id):
        """IDで場所を取得"""
        db = get_db()
        location = db.execute(
            'SELECT * FROM locations WHERE id = ?',
            (location_id,)
        ).fetchone()
        return dict(location) if location else None

    @staticmethod
    def create(data):
        """場所を作成"""
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO locations (name, location_type, area_size, sun_exposure, notes, image_path, bg_image,
                                      canvas_top_direction, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['name'], data['location_type'], data.get('area_size'),
             data.get('sun_exposure'), data.get('notes'), data.get('image_path'),
             data.get('bg_image') or DEFAULT_BG_IMAGE, _top_direction(data), now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(location_id, data):
        """場所を更新"""
        db = get_db()
        db.execute(
            '''UPDATE locations SET name = ?, location_type = ?, area_size = ?,
               sun_exposure = ?, notes = ?, image_path = ?, bg_image = ?,
               canvas_top_direction = ?, updated_at = ?
               WHERE id = ?''',
            (data['name'], data['location_type'], data.get('area_size'),
             data.get('sun_exposure'), data.get('notes'), data.get('image_path'),
             data.get('bg_image') or DEFAULT_BG_IMAGE, _top_direction(data), get_jst_now(), location_id)
        )
        db.commit()

    @staticmethod
    def delete(location_id):
        """場所を削除"""
        db = get_db()
        db.execute('DELETE FROM locations WHERE id = ?', (location_id,))
        db.commit()

    @staticmethod
    def count():
        """場所の総数を取得"""
        db = get_db()
        result = db.execute('SELECT COUNT(*) as count FROM locations').fetchone()
        return result['count'] if result else 0

    @staticmethod
    def get_adjacent(location_id):
        """現在の場所の前後の場所を取得（created_at DESC順）"""
        db = get_db()
        current = db.execute(
            'SELECT id, created_at FROM locations WHERE id = ?', (location_id,)
        ).fetchone()
        if not current:
            return None, None

        params = {'created_at': current['created_at'], 'id': current['id']}

        prev_loc = db.execute(
            '''SELECT id, name FROM locations
               WHERE (created_at < :created_at)
                  OR (created_at = :created_at AND id < :id)
               ORDER BY created_at DESC, id DESC LIMIT 1''',
            params
        ).fetchone()

        next_loc = db.execute(
            '''SELECT id, name FROM locations
               WHERE (created_at > :created_at)
                  OR (created_at = :created_at AND id > :id)
               ORDER BY created_at ASC, id ASC LIMIT 1''',
            params
        ).fetchone()

        return (dict(prev_loc) if prev_loc else None,
                dict(next_loc) if next_loc else None)

    @staticmethod
    def search(keyword):
        """場所を検索"""
        db = get_db()
        locations = db.execute(
            '''SELECT * FROM locations
               WHERE search_fold(name) LIKE ? OR search_fold(location_type) LIKE ?
               ORDER BY created_at DESC''',
            (f'%{fold(keyword)}%',) * 2
        ).fetchall()
        return [dict(location) for location in locations]

    @staticmethod
    def get_bg_images():
        """static/images/location_bg_images/ から背景画像ファイル名リストを返す"""
        bg_dir = os.path.join(current_app.static_folder, 'images', 'location_bg_images')
        if not os.path.isdir(bg_dir):
            return []
        allowed_ext = {'.png', '.jpg', '.jpeg', '.webp'}
        return order_bg_images([f for f in os.listdir(bg_dir)
                                if os.path.splitext(f)[1].lower() in allowed_ext])

    @staticmethod
    def get_canvas_data(location_id):
        """キャンバスデータをJSON形式で取得"""
        return Location.parse_canvas(Location.canvas_text(location_id))

    @staticmethod
    def canvas_text(location_id):
        """保存されている canvas_data の文字列そのもの（NULL・場所なしは空文字）"""
        row = get_db().execute(
            'SELECT canvas_data FROM locations WHERE id = ?', (location_id,)
        ).fetchone()
        return (row['canvas_data'] if row else None) or ''

    @staticmethod
    def parse_canvas(canvas_text):
        """canvas_data の文字列を dict などにする。空・壊れているときは None"""
        if not canvas_text:
            return None
        try:
            return json.loads(canvas_text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def revision_of(canvas_text):
        """保存されている canvas_data の文字列（NULL は空文字）のリビジョン（SHA-256 の先頭16文字）"""
        return hashlib.sha256((canvas_text or '').encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def canvas_revision(location_id):
        """今の canvas_data のリビジョン。エディターが開いたあとの変化を見つけるのに使う"""
        return Location.revision_of(Location.canvas_text(location_id))

    @staticmethod
    def remove_from_canvas(location_id, location_crop_id):
        """見取り図から指定の植え付けを削除"""
        canvas_data = Location.get_canvas_data(location_id)
        if not canvas_data or 'placements' not in canvas_data:
            return
        canvas_data['placements'] = [
            p for p in canvas_data['placements']
            if p.get('locationCropId') != location_crop_id
        ]
        db = get_db()
        db.execute(
            'UPDATE locations SET canvas_data = ?, updated_at = ? WHERE id = ?',
            (json.dumps(canvas_data, ensure_ascii=False), get_jst_now(), location_id)
        )
        db.commit()

    @staticmethod
    def save_canvas_data(location_id, canvas_dict, *, expected_text):
        """キャンバスデータをJSON形式で保存し、保存した文字列のリビジョンを返す

        保存されている文字列が expected_text（読んだときの canvas_text）のままのときだけ書く。
        読んでから書くまでにほかの保存（エディター・API）が入っていたら何もせず None を返す
        """
        from app.models.planting import Planting

        db = get_db()
        canvas_json = json.dumps(canvas_dict, ensure_ascii=False)
        updated = db.execute(
            '''UPDATE locations SET canvas_data = ?, updated_at = ?
               WHERE id = ? AND IFNULL(canvas_data, '') = ?''',
            (canvas_json, get_jst_now(), location_id, expected_text)
        ).rowcount
        db.commit()
        if updated == 0:
            return None

        # キャンバス上に存在する作物のIDを抽出
        location_crop_ids = set()
        if canvas_dict and 'placements' in canvas_dict:
            # 新フォーマット (version 2.0)
            for p in canvas_dict['placements']:
                if p.get('locationCropId'):
                    location_crop_ids.add(int(p['locationCropId']))
        elif canvas_dict and 'objects' in canvas_dict:
            # 旧フォーマット (Fabric.js)
            for obj in canvas_dict['objects']:
                if obj.get('locationCropId'):
                    location_crop_ids.add(int(obj['locationCropId']))

        # キャンバス上にない作物の位置情報をクリア
        Planting.clear_positions_except(location_id, location_crop_ids)

        return Location.revision_of(canvas_json)
