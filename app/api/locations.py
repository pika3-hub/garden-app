"""場所 API（/api/v1/locations）"""
from app.api import bp
from app.api.choices import SUN_EXPOSURES, bg_images
from app.api.resource import Resource, register
from app.api.serialize import planting_label
from app.api.validation import Field
from app.database import get_db
from app.models.location import Location
from app.models.planting import _CV_JOIN


class LocationResource(Resource):
    name = 'locations'
    label = '場所'
    model = Location
    web_path = '/locations/{id}'
    image_folder = 'locations'
    usage_type = 'location'
    supplement_type = 'location'
    fields = {
        'name': Field('str', required=True, max_len=100),
        'location_type': Field('str', required=True, max_len=50),
        'area_size': Field('decimal', min_value=0),
        'sun_exposure': Field('enum', choices=SUN_EXPOSURES),
        'notes': Field('str'),
        'bg_image': Field('enum', choices=bg_images),
    }
    read_only = ('canvas_data',)  # 見取り図は画面専用
    list_from = 'locations l'
    list_id = 'l.id'
    list_order = 'l.name, l.id'
    search_columns = ('l.name',)
    filters = {'location_type': ('l.location_type = ?', Field('str'))}

    def describe(self, row):
        rows = get_db().execute(
            f'''SELECT lc.id, lc.planted_date, cv.crop_name, cv.variety, l.name AS location_name
                FROM plantings lc {_CV_JOIN} JOIN locations l ON lc.location_id = l.id
                WHERE lc.location_id = ? AND lc.status = 'active'
                ORDER BY lc.planted_date, lc.id''', (row['id'],)
        ).fetchall()
        return {'active_plantings': [{'id': r['id'], 'display_name': planting_label(dict(r))} for r in rows]}


register(bp, LocationResource())
