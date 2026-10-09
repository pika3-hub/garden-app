"""タスク API（/api/v1/tasks）"""
from app.api import bp
from app.api.choices import TASK_RELATION_KEYS, TASK_STATUSES
from app.api.relations import RelationsMixin
from app.api.resource import Resource, register
from app.api.validation import Field
from app.models.task import Task


class TaskResource(RelationsMixin, Resource):
    name = 'tasks'
    label = 'タスク'
    model = Task
    web_path = '/tasks/{id}'
    supplement_type = 'task'  # 本体画像は無く、追加画像（補足情報）のみ
    relation_table = 'task_relations'
    relation_owner = 'task_id'
    relation_keys = TASK_RELATION_KEYS
    fields = {
        'title': Field('str', required=True, max_len=200),
        'description': Field('str'),
        'due_date': Field('date'),
        'status': Field('enum', choices=TASK_STATUSES),
    }
    list_from = 'tasks t'
    list_id = 't.id'
    list_order = 't.due_date IS NULL, t.due_date, t.id'
    search_columns = ('t.title', 't.description')
    date_column = 't.due_date'
    filters = {'status': ('t.status = ?', Field('enum', choices=TASK_STATUSES))}

    def to_model(self, values):
        data = super().to_model(values)
        data['status'] = data['status'] or Task.STATUS_PENDING
        return data


register(bp, TaskResource())
