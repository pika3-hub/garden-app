"""日記・料理・タスクの関連（多対多）の読み書き

PATCH の relations は「送られたキーだけ置き換え、送られなかったキーは維持」。
保存は各モデルの既存 save_relations()（全削除→再登録）を使う。
"""
from app.api.errors import detail
from app.api.serialize import display_name, plain, planting_label
from app.api.validation import (
    REF_CROP, REF_HARVEST, REF_LOCATION, REF_PLANTING, REF_VARIETY, check_ref_id,
)
from app.database import get_db
from app.models.planting import _CV_JOIN

# API のキー → (relation_type, 関連テーブルの列, 参照先, save_relations のキー, relation_items の type)
RELATION_SPECS = {
    'crop_ids': ('crop', 'crop_id', REF_CROP, 'crop_ids', 'crop'),
    'variety_ids': ('variety', 'variety_id', REF_VARIETY, 'variety_ids', 'variety'),
    'location_ids': ('location', 'location_id', REF_LOCATION, 'location_ids', 'location'),
    'planting_ids': ('location_crop', 'location_crop_id', REF_PLANTING, 'location_crop_ids', 'planting'),
    'harvest_ids': ('harvest', 'harvest_id', REF_HARVEST, 'harvest_ids', 'harvest'),
}


def read_relations(table, owner_column, owner_id, keys):
    db = get_db()
    result = {}
    for key in keys:
        rel_type, column = RELATION_SPECS[key][:2]
        rows = db.execute(
            f'''SELECT {column} FROM {table}
                WHERE {owner_column} = ? AND relation_type = ? AND {column} IS NOT NULL ORDER BY id''',
            (owner_id, rel_type)).fetchall()
        result[key] = [r[0] for r in rows]
    return result


def parse_relations(value, keys, errors):
    """payload['relations'] を検証し、送られたキーだけの {key: [id, ...]} を返す"""
    if not isinstance(value, dict):
        errors.append(detail('relations', f'オブジェクトで指定してください（使えるキー: {", ".join(keys)}）'))
        return {}
    parsed = {}
    for key, ids in value.items():
        field = f'relations.{key}'
        if key not in keys:
            errors.append(detail(field, f'未知のキーです。使えるキー: {", ".join(keys)}'))
            continue
        if not isinstance(ids, list):
            errors.append(detail(field, 'ID の配列で指定してください（例: [1, 2]、全解除は []）'))
            continue
        clean = []
        for i, raw in enumerate(ids):
            obj_id, reason = check_ref_id(RELATION_SPECS[key][2], raw)
            if reason:
                errors.append(detail(f'{field}[{i}]', reason, raw if isinstance(raw, (int, str)) else None))
            elif obj_id not in clean:
                clean.append(obj_id)
        parsed[key] = clean
    return parsed


def _amount(quantity, unit):
    if quantity is None:
        return ''
    try:
        number = f'{float(plain(quantity)):g}'
    except (TypeError, ValueError):
        number = str(quantity)
    return f' {number}{unit or ""}'


def _name(item_type, obj_id):
    db = get_db()
    if item_type == 'crop':
        r = db.execute('SELECT name FROM crops WHERE id = ?', (obj_id,)).fetchone()
        return r['name'] if r else None
    if item_type == 'variety':
        r = db.execute('SELECT v.name, c.name AS crop_name FROM varieties v JOIN crops c ON v.crop_id = c.id '
                       'WHERE v.id = ?', (obj_id,)).fetchone()
        return display_name(r['crop_name'], r['name']) if r else None
    if item_type == 'location':
        r = db.execute('SELECT name FROM locations WHERE id = ?', (obj_id,)).fetchone()
        return r['name'] if r else None
    if item_type == 'planting':
        r = db.execute(f'''SELECT lc.planted_date, cv.crop_name, cv.variety, l.name AS location_name
                           FROM plantings lc {_CV_JOIN} JOIN locations l ON lc.location_id = l.id
                           WHERE lc.id = ?''', (obj_id,)).fetchone()
        return planting_label(dict(r)) if r else None
    if item_type == 'harvest':
        r = db.execute(f'''SELECT h.harvest_date, h.quantity, h.unit, cv.crop_name, cv.variety
                           FROM harvests h JOIN plantings lc ON h.location_crop_id = lc.id {_CV_JOIN}
                           WHERE h.id = ?''', (obj_id,)).fetchone()
        if not r:
            return None
        return (f'{display_name(r["crop_name"], r["variety"])} {plain(r["harvest_date"])}'
                f'{_amount(r["quantity"], r["unit"])}')
    raise ValueError(item_type)


def relation_items(relations):
    items = []
    for key, ids in relations.items():
        item_type = RELATION_SPECS[key][4]
        for obj_id in ids:
            items.append({'type': item_type, 'id': obj_id, 'display_name': _name(item_type, obj_id)})
    return items


class RelationsMixin:
    """Resource と組み合わせて relations の検証・保存・表示を加える（Resource より先に継承する）"""
    relation_table = ''
    relation_owner = ''
    relation_keys = ()
    reserved_keys = ('relations',)

    def parse_reserved(self, payload, row, errors):
        if 'relations' not in payload:
            return None
        return parse_relations(payload['relations'], self.relation_keys, errors)

    def after_write(self, obj_id, reserved):
        if reserved is None:
            return  # relations が送られていない → 関連は変更しない
        current = read_relations(self.relation_table, self.relation_owner, obj_id, self.relation_keys)
        current.update(reserved)
        self.model.save_relations(obj_id, {RELATION_SPECS[k][3]: v for k, v in current.items()})

    def describe(self, row):
        relations = read_relations(self.relation_table, self.relation_owner, row['id'], self.relation_keys)
        return {**super().describe(row), 'relations': relations, 'relation_items': relation_items(relations)}
