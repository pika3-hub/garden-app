"""植え付け API（/api/v1/plantings）

作物で植えた場合は crop_id のみ、品種で植えた場合は variety_id のみを持つ（DB の CHECK 制約）。
status は直接変更させず、栽培終了は POST /plantings/{id}/end で見取り図の処理も含めて行う。
"""
from flask import g

from app.api import bp
from app.api.choices import PLANTING_STATUSES
from app.api.errors import detail, ok, validation_error
from app.api.payload import parse_request
from app.api.resource import Resource, load_or_404, register
from app.api.serialize import display_name
from app.api.validation import (REF_CROP, REF_LOCATION, REF_VARIETY, SQLITE_MAX_INT, Field,
                                validate_payload)
from app.models.location import Location
from app.models.planting import _CV_JOIN, Planting
from app.utils.canvas_areas import (CROWDED_DISTANCE, AreaError, area_name, crowded_warning,
                                    parse_area)


class PlantingResource(Resource):
    name = 'plantings'
    label = '植え付け'
    model = Planting
    web_path = '/plantings/{id}'
    fields = {
        'location_id': Field('ref', required=True, ref=REF_LOCATION),
        'crop_id': Field('ref', ref=REF_CROP),
        'variety_id': Field('ref', ref=REF_VARIETY),
        'planted_date': Field('date'),
        'quantity': Field('int', min_value=0),
        'notes': Field('str'),
        'end_date': Field('date'),
    }
    read_only = ('status', 'position_x', 'position_y', 'canvas_snapshot')
    list_from = f'plantings lc {_CV_JOIN} JOIN locations l ON lc.location_id = l.id'
    list_id = 'lc.id'
    list_order = 'lc.planted_date IS NULL, lc.planted_date DESC, lc.id DESC'
    search_columns = ('cv.crop_name', 'cv.variety', 'l.name')
    filters = {
        'crop_id': ('cv.effective_crop_id = ?', Field('int', min_value=1)),
        'variety_id': ('lc.variety_id = ?', Field('int', min_value=1)),
        'location_id': ('lc.location_id = ?', Field('int', min_value=1)),
    }
    extra_list_args = ('status', 'area')
    reserved_keys = ('area',)

    def insert(self, model_data):
        return Planting.plant(model_data)

    def save(self, obj_id, model_data, row):
        Planting.update_all(obj_id, model_data)
        if row['status'] == 'ended':
            Planting.update_end_date_notes(obj_id, model_data['end_date'], model_data['notes'])

    def parse_reserved(self, payload, row, errors):
        """作成時の area を、場所の上の方角に合わせて検証してマスにする"""
        if 'area' not in payload:
            return None
        if row is not None:
            errors.append(detail('area', '登録済みの植え付けには POST /api/v1/plantings/{id}/place で置いてください',
                                 payload['area']))
            return None
        location_id = payload.get('location_id')
        if not isinstance(location_id, int) or isinstance(location_id, bool):
            return None  # location_id の誤りは項目の検証が報告する
        return _parse_area_for(location_id, payload['area'], errors)

    def after_write(self, obj_id, reserved):
        if reserved is not None:
            _place(obj_id, reserved)

    def check(self, values, merged, row, errors):
        if values.get('crop_id') and values.get('variety_id'):
            errors.append(detail('variety_id', '作物で植えた場合は crop_id のみ、品種で植えた場合は variety_id のみを'
                                               '指定してください（両方は指定できません）'))
            return
        if values.get('variety_id'):
            merged['crop_id'] = None
        elif values.get('crop_id'):
            merged['variety_id'] = None
        if not merged.get('crop_id') and not merged.get('variety_id'):
            errors.append(detail('crop_id', 'crop_id（作物）か variety_id（品種）のどちらか一方を指定してください'))
        if row is not None and values.get('planted_date'):
            # 画面（planting_routes.planting_update）と同じく、子レコードより後の植え付け日は不可
            earliest = Planting.get_earliest_child_date(row['id'])
            if earliest and values['planted_date'] > str(earliest)[:10]:
                errors.append(detail('planted_date', f'植え付け日は栽培記録・収穫記録の日付（{str(earliest)[:10]}）'
                                                     'より前の日付にしてください', values['planted_date']))
        if 'end_date' in values:
            if row is None:
                errors.append(detail('end_date', '作成時は指定できません。栽培終了は POST /api/v1/plantings/{id}/end で行ってください'))
            elif row['status'] != 'ended':
                errors.append(detail('end_date', '栽培中の植え付けの終了日は変更できません。'
                                                 '栽培終了は POST /api/v1/plantings/{id}/end で行ってください'))

    def list_where(self, args, where, params, errors):
        status = args.get('status', 'active')
        if status == 'all':
            return
        if status not in PLANTING_STATUSES:
            errors.append(detail('status', f'次のいずれかで指定してください: {", ".join([*PLANTING_STATUSES, "all"])}', status))
            return
        where.append('lc.status = ?')
        params.append(status)

    def list_keep(self, args, errors):
        """area（見取り図のエリア）で絞る。配置は DB の列でないので Python 側で残す"""
        if 'area' not in args:
            return None
        location_id = args.get('location_id', '')
        if not location_id:
            errors.append(detail('area', 'area で絞るときは location_id も指定してください', args['area']))
            return None
        try:
            location = Location.get_by_id(int(location_id)) if location_id.isdigit() else None
        except OverflowError:
            location = None
        top = location['canvas_top_direction'] if location else None
        try:
            wanted = area_name(parse_area(args['area'], top), top)
        except AreaError as e:
            errors.append(detail('area', str(e), args['area']))
            return None
        areas = Planting.area_map(location['id']) if location else {}
        return lambda row: wanted in areas.get(row['id'], [])

    def serialize(self, row):
        data = super().serialize(row)
        placed = g.get('api_placement')
        if placed and placed[0] == row['id']:  # 置いた植え付けの応答にだけ付ける
            data['placement'] = placed[1]
        return data

    def describe(self, row):
        return {
            'status': row['status'],
            'display_name': display_name(row['crop_name'], row['variety']),
            'crop': {'id': row['effective_crop_id'], 'name': row['crop_name']},
            'variety': {'id': row['variety_id'], 'name': row['variety']} if row['variety_id'] else None,
            'location': {'id': row['location_id'], 'name': row['location_name']},
            'days_from_planting': row.get('days_from_planting'),
            'areas': Planting.area_map(row['location_id']).get(row['id'], []),
        }


def _parse_area_for(location_id, area, errors):
    """area を場所の上の方角に合わせて (row, col) にする。誤りは errors に足して None"""
    location = Location.get_by_id(location_id) if 0 < location_id <= SQLITE_MAX_INT else None
    if location is None:
        return None  # 場所が無い誤りは項目の検証が報告する
    try:
        return parse_area(area if isinstance(area, str) else '', location['canvas_top_direction'])
    except AreaError as e:
        errors.append(detail('area', str(e), area))
        return None


def _place(planting_id, cell):
    """見取り図に置き、結果を g.api_placement（植え付け ID 付き）に入れる"""
    top = Location.get_by_id(Planting.get_by_id(planting_id)['location_id'])['canvas_top_direction']
    spot = Planting.place_in_area(planting_id, cell)
    area = area_name(cell, top)
    crowded = spot.nearest is not None and spot.nearest < CROWDED_DISTANCE
    g.api_placement = (planting_id, {'area': area, 'x': spot.x, 'y': spot.y,
                                     'warning': crowded_warning(area) if crowded else None})


PLANTINGS = PlantingResource()
register(bp, PLANTINGS)


@bp.post('/plantings/<int:obj_id>/end')
def end_planting(obj_id):
    """栽培終了（見取り図のスナップショット保存・配置解除を含む）"""
    row = load_or_404(PLANTINGS, obj_id)
    g.api_target_id = obj_id
    payload, _ = parse_request()
    values, errors = validate_payload({'end_date': Field('date')}, payload, creating=False)
    if row['status'] != 'active':
        errors.append(detail('status', f'栽培中（active）の植え付けだけ終了できます（現在: {row["status"]}）'))
    if errors:
        raise validation_error(errors)
    Planting.end_cultivation(obj_id, row['location_id'], values.get('end_date'))
    return ok(PLANTINGS.serialize(PLANTINGS.fetch(obj_id)))


@bp.post('/plantings/<int:obj_id>/place')
def place_planting(obj_id):
    """登録済みの栽培中の植え付けのアイコンを、見取り図のエリアに1つ足して置く"""
    row = load_or_404(PLANTINGS, obj_id)
    g.api_target_id = obj_id
    payload, _ = parse_request()
    values, errors = validate_payload({'area': Field('str', required=True)}, payload, creating=True)
    if row['status'] != 'active':
        errors.append(detail('status', f'栽培中（active）の植え付けだけ置けます（現在: {row["status"]}）'))
    cell = None
    if not errors:
        cell = _parse_area_for(row['location_id'], values['area'], errors)
    if errors:
        raise validation_error(errors)
    _place(obj_id, cell)
    return ok(PLANTINGS.serialize(PLANTINGS.fetch(obj_id)))
