"""作物 API（/api/v1/crops）"""
from app.api import bp
from app.api.choices import crop_icons
from app.api.resource import Resource, register
from app.api.validation import Field
from app.database import get_db
from app.models.crop import Crop


class CropResource(Resource):
    name = 'crops'
    label = '作物'
    model = Crop
    web_path = '/crops/{id}'
    image_folder = 'crops'
    usage_type = 'crop'
    supplement_type = 'crop'
    fields = {
        'name': Field('str', required=True, max_len=100),
        'crop_type': Field('str', required=True, max_len=50),
        'notes': Field('str'),
        'icon_path': Field('enum', choices=crop_icons),
        'image_color': Field('color'),
    }
    list_from = 'crops c'
    list_id = 'c.id'
    list_order = 'c.name, c.id'
    search_columns = ('c.name',)
    filters = {'crop_type': ('c.crop_type = ?', Field('str'))}

    def to_model(self, values):
        data = super().to_model(values)
        data['image_color'] = data['image_color'] or '#4CAF50'  # 画面と同じ既定色
        return data

    def describe(self, row):
        rows = get_db().execute(
            'SELECT id, name FROM varieties WHERE crop_id = ? ORDER BY name, id', (row['id'],)
        ).fetchall()
        return {'varieties': [{'id': r['id'], 'name': r['name']} for r in rows]}


register(bp, CropResource())
