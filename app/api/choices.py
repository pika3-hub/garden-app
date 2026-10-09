"""選択肢の一覧（/meta と検証で共用）"""
import os

from app.database import get_db

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')

PLANTING_STATUSES = ['active', 'harvested', 'removed']
TASK_STATUSES = ['pending', 'in_progress', 'completed']
SUN_EXPOSURES = ['全日', '半日', '日陰']                       # locations/form.html と同じ
WEATHERS = ['晴れ', '曇り', '雨', '雪', '晴れ時々曇り', '曇り時々雨']  # diary/form.html と同じ

# 日記・料理・タスクで使える関連のキー（各テーブルの列に合わせる）
DIARY_RELATION_KEYS = ('crop_ids', 'variety_ids', 'location_ids', 'planting_ids', 'harvest_ids')
COOKING_RELATION_KEYS = ('crop_ids', 'variety_ids', 'planting_ids', 'harvest_ids')
TASK_RELATION_KEYS = ('crop_ids', 'variety_ids', 'location_ids', 'planting_ids')


def crop_icons():
    """作物アイコンのファイル名一覧（crop_routes._get_crop_icon_list と同じ）"""
    path = os.path.join(_STATIC_DIR, 'images', 'crop_icons')
    return sorted(os.listdir(path)) if os.path.isdir(path) else []


def bg_images():
    """見取り図背景画像のファイル名一覧（Location.get_bg_images と同じ条件）"""
    path = os.path.join(_STATIC_DIR, 'images', 'location_bg_images')
    if not os.path.isdir(path):
        return []
    return sorted(f for f in os.listdir(path)
                  if os.path.splitext(f)[1].lower() in {'.png', '.jpg', '.jpeg', '.webp'})


def distinct_values(table, column):
    """既存データに入っている値の一覧（自由入力の項目の候補）"""
    rows = get_db().execute(
        f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
    ).fetchall()
    return [r[0] for r in rows]
