"""収穫 API（/api/v1/harvests）"""
from app.api import bp
from app.api.planting_records import check_planting_active, check_planting_unchanged, planting_ref
from app.api.resource import Resource, register
from app.api.validation import REF_PLANTING, Field
from app.models.harvest import Harvest
from app.models.planting import _CV_JOIN


class HarvestResource(Resource):
    name = 'harvests'
    label = '収穫'
    model = Harvest
    web_path = '/harvests/{id}'
    image_folder = 'harvests'
    usage_type = 'harvest'
    supplement_type = 'harvest'
    fields = {
        'planting_id': Field('ref', required=True, ref=REF_PLANTING, column='location_crop_id'),
        'harvest_date': Field('date', required=True),
        'quantity': Field('decimal', min_value=0),
        'unit': Field('str', max_len=20),
        'notes': Field('str'),
    }
    list_from = f'harvests h JOIN plantings lc ON h.location_crop_id = lc.id {_CV_JOIN}'
    list_id = 'h.id'
    list_order = 'h.harvest_date DESC, h.id DESC'
    search_columns = ('h.notes', 'cv.crop_name', 'cv.variety')
    date_column = 'h.harvest_date'
    filters = {
        'planting_id': ('h.location_crop_id = ?', Field('int', min_value=1)),
        'crop_id': ('cv.effective_crop_id = ?', Field('int', min_value=1)),
    }

    def check(self, values, merged, row, errors):
        check_planting_unchanged(values, row, self.label, errors)
        check_planting_active(values, row, self.label, errors)

    def describe(self, row):
        return {'planting': planting_ref(row), 'days_from_planting': row.get('days_from_planting')}


register(bp, HarvestResource())
