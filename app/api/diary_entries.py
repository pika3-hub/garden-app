"""日記 API（/api/v1/diary_entries）"""
from app.api import bp
from app.api.choices import DIARY_RELATION_KEYS
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field
from app.models.diary import DiaryEntry


class DiaryEntryResource(RelationsMixin, Resource):
    name = 'diary_entries'
    label = '日記'
    model = DiaryEntry
    web_path = '/diary/{id}'
    image_folder = 'diary'
    usage_type = 'diary'
    supplement_type = 'diary'
    relation_table = 'diary_relations'
    relation_owner = 'diary_id'
    relation_keys = DIARY_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'entry_date': Field('date', required=True),
        'content': Field('str'),
        'weather': Field('str', max_len=50),
        'status': Field('str', max_len=20),
    }
    list_from = 'diary_entries d'
    list_id = 'd.id'
    list_order = 'd.entry_date DESC, d.id DESC'
    search_columns = ('d.title', 'd.content')
    date_column = 'd.entry_date'

    def to_model(self, values):
        data = super().to_model(values)
        data['status'] = data['status'] or 'published'
        return data


register(bp, DiaryEntryResource())
