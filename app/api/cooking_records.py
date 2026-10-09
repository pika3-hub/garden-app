"""料理 API（/api/v1/cooking_records）"""
from app.api import bp
from app.api.choices import COOKING_RELATION_KEYS
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field
from app.models.cooking import Cooking


class CookingRecordResource(RelationsMixin, Resource):
    name = 'cooking_records'
    label = '料理'
    model = Cooking
    web_path = '/cooking/{id}'
    image_folder = 'cooking'
    usage_type = 'cooking'
    supplement_type = 'cooking'
    relation_table = 'cooking_relations'
    relation_owner = 'cooking_id'
    relation_keys = COOKING_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'cooked_date': Field('date', required=True),
        'category': Field('str', max_len=100),
        'notes': Field('str'),
    }
    list_from = 'cooking k'
    list_id = 'k.id'
    list_order = 'k.cooked_date DESC, k.id DESC'
    search_columns = ('k.title', 'k.notes')
    date_column = 'k.cooked_date'
    filters = {'category': ('k.category = ?', Field('str'))}


register(bp, CookingRecordResource())
