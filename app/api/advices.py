"""アドバイス API（/api/v1/advices）。Hermes が確認なしで保存・更新する。削除は無い"""
from app.api import bp
from app.api.choices import ADVICE_RELATION_KEYS
from app.api.errors import detail
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field, check_value
from app.models.advice import Advice
from app.utils.timezone import get_jst_now


class AdviceResource(RelationsMixin, Resource):
    name = 'advices'
    label = 'アドバイス'
    model = Advice
    web_path = '/advices/{id}'  # 本体画像・追加画像は無い
    relation_table = 'advice_relations'
    relation_owner = 'advice_id'
    relation_keys = ADVICE_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'question': Field('str'),
        'answer': Field('str', required=True),
        'advised_on': Field('date'),
    }
    list_from = 'advices a'
    list_id = 'a.id'
    list_order = 'a.advised_on DESC, a.id DESC'
    search_columns = ('a.title', 'a.question', 'a.answer')
    date_column = 'a.advised_on'
    extra_list_args = ('crop_id', 'variety_id', 'planting_id')

    def to_model(self, values):
        data = super().to_model(values)
        data['advised_on'] = data['advised_on'] or get_jst_now()[:10]
        return data

    def list_where(self, args, where, params, errors):
        for key in self.extra_list_args:
            if key not in args:
                continue
            value, reason = check_value(Field('int', min_value=1), args[key])
            if reason:
                errors.append(detail(key, reason, args[key]))
            elif value is not None:
                sql, n = Advice.scope_clause(key.removesuffix('_id'))
                where.append(f'a.id IN ({sql})')
                params.extend([value] * n)


register(bp, AdviceResource())
