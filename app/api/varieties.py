"""品種 API（/api/v1/varieties）"""
from app.api import bp
from app.api.choices import crop_icons
from app.api.resource import Resource, register
from app.api.serialize import display_name, image_url
from app.api.validation import REF_CROP, Field
from app.models.variety import Variety


class VarietyResource(Resource):
    name = 'varieties'
    label = '品種'
    model = Variety
    web_path = '/varieties/{id}'
    image_folder = 'varieties'
    usage_type = 'variety'
    supplement_type = 'variety'
    fields = {
        'crop_id': Field('ref', required=True, ref=REF_CROP),
        'name': Field('str', required=True, max_len=100),
        'notes': Field('str'),
        # 外観3項目は未設定なら親作物から継承（NULL のまま保存する）
        'icon_path': Field('enum', choices=crop_icons),
        'image_color': Field('color'),
    }
    list_from = 'varieties v JOIN crops c ON v.crop_id = c.id'
    list_id = 'v.id'
    list_order = 'c.name, v.name, v.id'
    search_columns = ('v.name', 'c.name')
    filters = {'crop_id': ('v.crop_id = ?', Field('int', min_value=1))}

    def describe(self, row):
        effective = Variety.apply_inheritance(dict(row))
        return {
            'crop': {'id': row['crop_id'], 'name': row['crop_name']},
            'display_name': display_name(row['crop_name'], row['name']),
            'effective_icon_path': effective['effective_icon_path'],
            'effective_image_color': effective['effective_image_color'],
            'effective_image_url': image_url(effective['effective_image_path']),
        }


register(bp, VarietyResource())
