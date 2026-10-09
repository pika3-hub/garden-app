"""API レスポンス用の値変換と URL 生成"""
from datetime import date, datetime
from decimal import Decimal

from flask import current_app

from app import _crop_display_name as display_name  # noqa: F401（作物名表記ルールを画面と共用）


def plain(value):
    """DB の値を JSON にできる形へ（日付は ISO 形式の文字列）"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def web_url(path):
    """既存 Web 画面の URL（スマホで開ける）"""
    return current_app.config['WEB_BASE_URL'].rstrip('/') + path


def image_url(image_path):
    return web_url('/static/uploads/' + image_path) if image_path else None


def planting_label(row):
    """植え付けの表示名。row は crop_name, variety, location_name, planted_date を持つ"""
    label = f'{display_name(row["crop_name"], row.get("variety"))} / {row["location_name"]}'
    if row.get('planted_date'):
        label += f'（{plain(row["planted_date"])} 植え付け）'
    return label
