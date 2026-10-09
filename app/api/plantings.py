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
from app.api.validation import REF_CROP, REF_LOCATION, REF_VARIETY, Field, validate_payload
from app.models.planting import _CV_JOIN, Planting


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
    extra_list_args = ('status',)

    def insert(self, model_data):
        return Planting.plant(model_data)

    def save(self, obj_id, model_data, row):
        Planting.update_all(obj_id, model_data)
        if row['status'] == 'harvested':
            Planting.update_end_date_notes(obj_id, model_data['end_date'], model_data['notes'])

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
            elif row['status'] != 'harvested':
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

    def describe(self, row):
        return {
            'status': row['status'],
            'display_name': display_name(row['crop_name'], row['variety']),
            'crop': {'id': row['effective_crop_id'], 'name': row['crop_name']},
            'variety': {'id': row['variety_id'], 'name': row['variety']} if row['variety_id'] else None,
            'location': {'id': row['location_id'], 'name': row['location_name']},
            'days_from_planting': row.get('days_from_planting'),
        }


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
