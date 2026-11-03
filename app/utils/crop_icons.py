"""作物アイコンの一覧（作物・品種・写真の振り分けの画面と API の選択肢で共用）

ファイル名は「大分類_中身.png」（例: fruitveg_tomato.png）。大分類は最初の `_` より前。
CATEGORIES に無い大分類（`_` の無い名前を含む）は最後の「その他」にまとめる。
"""
import os

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'crop_icons')
ICON_EXTS = {'.png', '.webp'}

# （大分類, 見出し）を選ぶ画面に並べる順で
CATEGORIES = [
    ('fruitveg', '実の野菜'),
    ('bean', '豆'),
    ('leaf', '葉の野菜'),
    ('stem', '茎・花の野菜'),
    ('onion', 'ねぎ類'),
    ('root', '根の野菜'),
    ('tuber', 'いも'),
    ('herb', 'ハーブ'),
    ('mushroom', 'きのこ'),
    ('fruit', '果物'),
]
OTHER_LABEL = 'その他'

_ORDER = {prefix: i for i, (prefix, _) in enumerate(CATEGORIES)}


def _category_index(filename):
    prefix = filename.split('_', 1)[0] if '_' in filename else ''
    return _ORDER.get(prefix, len(CATEGORIES))


def _sort_key(filename):
    return (_category_index(filename), filename)


def list_crop_icons():
    """アイコンのファイル名を「大分類の順 → 名前順」で返す"""
    if not os.path.isdir(ICON_DIR):
        return []
    files = [f for f in os.listdir(ICON_DIR)
             if os.path.isfile(os.path.join(ICON_DIR, f)) and os.path.splitext(f)[1].lower() in ICON_EXTS]
    return sorted(files, key=_sort_key)


def group_crop_icons(icons=None):
    """[(見出し, [ファイル名, ...]), ...] を返す（空の大分類は出さない）"""
    if icons is None:
        icons = list_crop_icons()
    labels = [label for _, label in CATEGORIES] + [OTHER_LABEL]
    groups = {}
    for icon in sorted(icons, key=_sort_key):
        groups.setdefault(_category_index(icon), []).append(icon)
    return [(labels[i], files) for i, files in sorted(groups.items())]
