"""リソース共通の一覧・詳細・作成・部分更新・追加画像の処理

各リソースは Resource を継承してクラス属性（項目定義・一覧の SQL 断片）と
必要なフックだけを上書きし、register(bp, res) でルートを登録する。
"""
from flask import g, request

from app.api import images as img
from app.api.errors import ApiError, detail, ok, validation_error
from app.api.payload import parse_request
from app.api.serialize import image_url, plain, web_url
from app.api.validation import SQLITE_MAX_INT, Field, check_value, validate_payload
from app.database import get_db
from app.models.supplement import Supplement

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
LIKE_ESCAPE = "ESCAPE '\\'"


def like_pattern(q):
    """部分一致用パターン。% と _ は文字として扱う（LIKE_ESCAPE と組で使う）"""
    escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def page_arg(args, key, default, low, high, errors):
    """limit / offset などの整数クエリを読む"""
    if key not in args:
        return default
    value, reason = check_value(Field('int', min_value=low), args[key])
    if reason:
        errors.append(detail(key, reason, args[key]))
        return default
    if value is None:
        return default
    if high is not None and value > high:
        errors.append(detail(key, f'{high} 以下で指定してください', args[key]))
        return default
    return value


class Resource:
    """API リソースの定義。サブクラスでクラス属性とフックを上書きする"""
    name = ''               # URL のリソース名（例: 'crops'）
    label = ''              # 日本語名（例: '作物'）
    model = None            # get_by_id / create / update を持つモデルクラス
    fields = {}             # 書き込める項目 {API 項目名: Field}
    read_only = ()          # 送られたら 422 にする項目（COMMON_READ_ONLY に追加）
    web_path = ''           # 既存画面のパス（例: '/crops/{id}'）
    image_folder = None     # 本体画像の保存先（uploads 配下）。None なら本体画像なし
    usage_type = None       # 写真プール使用履歴の entity_type
    supplement_type = None  # 追加画像（補足情報）の entity_type。None なら追加画像なし
    extra_images_hint = ''  # 追加画像を持てないときの案内
    reserved_keys = ()      # parse_reserved で扱う追加キー（relations など）

    # 一覧
    list_from = ''          # FROM 句（エイリアス付き、JOIN 可）
    list_id = ''            # 主キー列（例: 'c.id'）
    list_order = ''         # ORDER BY 句
    search_columns = ()     # q で部分一致させる列
    date_column = None      # date_from / date_to の対象列
    filters = {}            # {クエリ名: (WHERE 断片, Field)}
    extra_list_args = ()    # list_where で扱うクエリ名

    COMMON_READ_ONLY = ('id', 'created_at', 'updated_at', 'image_path')

    # --- フック ---
    def fetch(self, obj_id):
        """DB 行（dict）か None"""
        return self.model.get_by_id(obj_id)

    def to_api(self, row):
        """DB 行 → API 項目名の dict（書き込める項目のみ）"""
        return {name: plain(row.get(f.column or name)) for name, f in self.fields.items()}

    def to_model(self, values):
        """API 項目名の dict → モデルの create / update に渡す dict"""
        return {(f.column or name): values.get(name) for name, f in self.fields.items()}

    def insert(self, model_data):
        return self.model.create(model_data)

    def save(self, obj_id, model_data, row):
        self.model.update(obj_id, model_data)

    def check(self, values, merged, row, errors):
        """項目をまたぐ検証。values=送られた項目、merged=既存値と合成後（変更可）、row=既存行（作成時 None）"""

    def parse_reserved(self, payload, row, errors):
        """reserved_keys の値を検証し、after_write に渡す値を返す"""
        return None

    def after_write(self, obj_id, reserved):
        """本体の保存後に呼ばれる（関連の保存など）"""

    def describe(self, row):
        """詳細に追加する項目（関連先の名前など）"""
        return {}

    def list_where(self, args, where, params, errors):
        """filters で表せない絞り込み（extra_list_args 用）"""

    # --- 共通 ---
    def serialize(self, row):
        data = {'id': row['id'], **self.to_api(row)}
        if self.image_folder:
            data['image_url'] = image_url(row.get('image_path'))
        data.update(self.describe(row))
        if self.supplement_type:
            data['extra_images'] = [
                {'supplement_id': s['id'], 'image_url': image_url(s['content'])}
                for s in Supplement.get_by_entity(self.supplement_type, row['id'])
                if s['supplement_type'] == 'image'
            ]
        data['created_at'] = plain(row.get('created_at'))
        data['updated_at'] = plain(row.get('updated_at'))
        data['web_url'] = web_url(self.web_path.format(id=row['id']))
        return data


def load_or_404(res, obj_id):
    row = res.fetch(obj_id) if 0 < obj_id <= SQLITE_MAX_INT else None
    if row is None:
        raise ApiError(404, 'not_found',
                       f'ID {obj_id} の{res.label}は存在しません。GET /api/v1/{res.name} で一覧を確認してください')
    return row


def _validate_body(res, payload, files, row):
    """本文を検証して (merged, inputs, reserved) を返す。誤りがあれば 422"""
    values, errors = validate_payload(
        res.fields, payload, creating=row is None,
        reserved=(*img.IMAGE_KEYS, *res.reserved_keys),
        read_only=(*res.COMMON_READ_ONLY, *res.read_only))
    inputs = img.collect_image_inputs(payload, files, errors, res)
    reserved = res.parse_reserved(payload, row, errors)
    merged = {**(res.to_api(row) if row else {}), **values}
    if not errors:
        res.check(values, merged, row, errors)
    if errors:
        raise validation_error(errors)
    img.check_files(inputs)
    return merged, inputs, reserved


def list_items(res):
    args = request.args
    errors = []
    allowed = {'q', 'limit', 'offset', *res.filters, *res.extra_list_args}
    if res.date_column:
        allowed |= {'date_from', 'date_to'}
    for key in args:
        if key not in allowed:
            errors.append(detail(key, f'未知の検索条件です。使える条件: {", ".join(sorted(allowed))}'))
    limit = page_arg(args, 'limit', DEFAULT_LIMIT, 1, MAX_LIMIT, errors)
    offset = page_arg(args, 'offset', 0, 0, None, errors)

    where, params = [], []
    q = args.get('q', '').strip()
    if q and res.search_columns:
        where.append('(' + ' OR '.join(f'{c} LIKE ? {LIKE_ESCAPE}' for c in res.search_columns) + ')')
        params += [like_pattern(q)] * len(res.search_columns)
    for key, (clause, field) in res.filters.items():
        if key in args:
            value, reason = check_value(field, args[key])
            if reason:
                errors.append(detail(key, reason, args[key]))
            elif value is not None:
                where.append(clause)
                params.append(value)
    if res.date_column:
        for key, op in (('date_from', '>='), ('date_to', '<=')):
            if key in args:
                value, reason = check_value(Field('date'), args[key])
                if reason:
                    errors.append(detail(key, reason, args[key]))
                elif value is not None:
                    where.append(f'DATE({res.date_column}) {op} ?')
                    params.append(value)
    res.list_where(args, where, params, errors)
    if errors:
        raise validation_error(errors)

    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    db = get_db()
    total = db.execute(f'SELECT COUNT(*) FROM {res.list_from}{where_sql}', params).fetchone()[0]
    ids = [r[0] for r in db.execute(
        f'SELECT {res.list_id} FROM {res.list_from}{where_sql} ORDER BY {res.list_order} LIMIT ? OFFSET ?',
        [*params, limit, offset])]
    items = [res.serialize(res.fetch(i)) for i in ids]
    return ok(items, meta={'total': total, 'limit': limit, 'offset': offset})


def get_item(res, obj_id):
    return ok(res.serialize(load_or_404(res, obj_id)))


def create_item(res):
    payload, files = parse_request(('image', 'extra_images'))
    values, inputs, reserved = _validate_body(res, payload, files, None)
    with img.SavedFiles() as saved:
        model_data = res.to_model(values)
        if res.image_folder:
            model_data['image_path'] = img.apply_main_image(inputs, saved, res.image_folder, None)
        obj_id = res.insert(model_data)
        saved.keep_all()
        g.api_target_id = obj_id
        res.after_write(obj_id, reserved)
        if res.image_folder:
            img.finish_main_image(inputs, res.usage_type, obj_id, model_data['image_path'], None)
        img.add_extra_images(inputs, saved, res.supplement_type, obj_id)
    return ok(res.serialize(res.fetch(obj_id)), 201)


def patch_item(res, obj_id):
    row = load_or_404(res, obj_id)
    g.api_target_id = obj_id
    payload, files = parse_request(('image', 'extra_images'))
    merged, inputs, reserved = _validate_body(res, payload, files, row)
    with img.SavedFiles() as saved:
        model_data = res.to_model(merged)
        old_path = row.get('image_path') if res.image_folder else None
        if res.image_folder:
            model_data['image_path'] = img.apply_main_image(inputs, saved, res.image_folder, old_path)
        res.save(obj_id, model_data, row)
        saved.keep_all()
        res.after_write(obj_id, reserved)
        if res.image_folder:
            img.finish_main_image(inputs, res.usage_type, obj_id, model_data['image_path'], old_path)
        img.add_extra_images(inputs, saved, res.supplement_type, obj_id)
    return ok(res.serialize(res.fetch(obj_id)))


def add_images(res, obj_id):
    """POST /{res}/{id}/images: 追加画像（補足情報）を添付する"""
    load_or_404(res, obj_id)
    g.api_target_id = obj_id
    payload, files = parse_request(('extra_images',))
    errors = [detail(k, '未知の項目です。使える項目: extra_photo_pool_ids')
              for k in payload if k != 'extra_photo_pool_ids']
    inputs = img.collect_image_inputs(
        {k: v for k, v in payload.items() if k == 'extra_photo_pool_ids'}, files, errors, res)
    if not errors and not inputs.extra_files and not inputs.extra_pool_photos:
        errors.append(detail('extra_images', 'extra_images（ファイル）か extra_photo_pool_ids で画像を1枚以上指定してください'))
    if errors:
        raise validation_error(errors)
    img.check_files(inputs)
    with img.SavedFiles() as saved:
        img.add_extra_images(inputs, saved, res.supplement_type, obj_id)
    return ok(res.serialize(res.fetch(obj_id)), 201)


def register(bp, res):
    """リソースの共通ルートを登録する"""
    base = f'/{res.name}'
    bp.add_url_rule(base, f'{res.name}_list', lambda: list_items(res), methods=['GET'])
    bp.add_url_rule(base, f'{res.name}_create', lambda: create_item(res), methods=['POST'])
    bp.add_url_rule(f'{base}/<int:obj_id>', f'{res.name}_get',
                    lambda obj_id: get_item(res, obj_id), methods=['GET'])
    bp.add_url_rule(f'{base}/<int:obj_id>', f'{res.name}_patch',
                    lambda obj_id: patch_item(res, obj_id), methods=['PATCH'])
    if res.supplement_type:
        bp.add_url_rule(f'{base}/<int:obj_id>/images', f'{res.name}_images',
                        lambda obj_id: add_images(res, obj_id), methods=['POST'])
