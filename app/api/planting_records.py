"""栽培記録 API（/api/v1/planting_records）"""
from app.api import bp
from app.api.errors import detail
from app.api.resource import Resource, register
from app.api.serialize import planting_label
from app.api.validation import REF_PLANTING, Field
from app.models.planting import _CV_JOIN, Planting
from app.models.planting_record import PlantingRecord


def planting_ref(row):
    """記録・収穫の行（location_crop_id と植え付けの表示情報を持つ）→ 植え付けの要約"""
    return {'id': row['location_crop_id'], 'display_name': planting_label(row)}


def check_planting_unchanged(values, row, label, errors):
    """既存モデルの update は植え付けを変更しないため、変更要求は誤りにする"""
    if row is not None and 'planting_id' in values and values['planting_id'] != row['location_crop_id']:
        errors.append(detail('planting_id', f'{label}の植え付けは変更できません。'
                                            f'別の植え付けの{label}は新しく作成してください'))


def check_planting_active(values, row, label, errors):
    """画面と同じく、栽培終了した植え付けには新しく作成させない（既存の記録の修正はできる）"""
    if row is None and 'planting_id' in values:
        planting = Planting.get_by_id(values['planting_id'])
        if planting and planting['status'] != 'active':
            errors.append(detail('planting_id', f'植え付け ID {values["planting_id"]} は栽培中ではありません'
                                                f'（{planting["end_date"] or "終了日なし"} に栽培終了）。'
                                                f'{label}は栽培中の植え付けにだけ作成できます'))


class PlantingRecordResource(Resource):
    name = 'planting_records'
    label = '栽培記録'
    model = PlantingRecord
    web_path = '/plantings/record/{id}'
    image_folder = 'growth_records'
    usage_type = 'planting_record'
    extra_images_hint = '。複数枚の写真は栽培記録を複数件作成してください'
    fields = {
        'planting_id': Field('ref', required=True, ref=REF_PLANTING, column='location_crop_id'),
        'recorded_at': Field('date', required=True),
        'notes': Field('str'),
    }
    list_from = f'planting_records pr JOIN plantings lc ON pr.location_crop_id = lc.id {_CV_JOIN}'
    list_id = 'pr.id'
    list_order = 'pr.recorded_at DESC, pr.id DESC'
    search_columns = ('pr.notes', 'cv.crop_name', 'cv.variety')
    date_column = 'pr.recorded_at'
    filters = {
        'planting_id': ('pr.location_crop_id = ?', Field('int', min_value=1)),
        'crop_id': ('cv.effective_crop_id = ?', Field('int', min_value=1)),
    }

    def check(self, values, merged, row, errors):
        check_planting_unchanged(values, row, self.label, errors)
        check_planting_active(values, row, self.label, errors)

    def describe(self, row):
        return {'planting': planting_ref(row), 'days_from_planting': row.get('days_from_planting')}


register(bp, PlantingRecordResource())
