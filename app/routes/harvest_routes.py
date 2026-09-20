from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.harvest import Harvest
from app.models.planting import Planting
from app.models.location import Location
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.diary import DiaryEntry
from app.models.supplement import Supplement
from app.models.cooking import Cooking
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image, copy_image
from datetime import date

bp = Blueprint('harvests', __name__, url_prefix='/harvests')


@bp.route('/')
def list():
    """収穫記録一覧"""
    harvests = Harvest.get_all()
    filter_types = sorted(set(h['crop_type'] for h in harvests if h['crop_type']))
    filter_locations = sorted(set(h['location_name'] for h in harvests if h['location_name']))
    filter_type_icons = {}
    for h in harvests:
        t, icon = h['crop_type'], h['icon_path']
        if t and icon:
            icons = filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': h['image_color'] or '#4CAF50'})

    def _ym_key(h):
        d = h.get('harvest_date')
        return str(d)[:7] if d else ''

    grouped_harvests = [(k, [item for item in g]) for k, g in groupby(harvests, key=_ym_key)]

    return render_template('harvests/list.html', harvests=harvests, grouped_harvests=grouped_harvests, filter_types=filter_types, filter_type_icons=filter_type_icons, filter_locations=filter_locations)


@bp.route('/<int:harvest_id>')
def detail(harvest_id):
    """収穫記録詳細"""
    harvest = Harvest.get_by_id(harvest_id)
    if not harvest:
        flash('収穫記録が見つかりません', 'danger')
        return redirect(url_for('harvests.list'))

    prev_harvest, next_harvest = Harvest.get_adjacent(harvest_id)

    # 関連する植え付け
    planting = Planting.get_by_id(harvest['location_crop_id'])
    related_plantings = [planting] if planting else []

    # 関連する日記
    related_diaries = DiaryEntry.get_by_harvest(harvest_id, limit=10)

    # 関連する料理
    related_cookings = Cooking.get_by_harvest(harvest_id, limit=10)

    # 補足情報
    supplements = Supplement.get_by_entity('harvest', harvest_id)

    parent_crop = Crop.get_by_id(harvest['effective_crop_id'])
    variety = None
    if harvest.get('variety_id'):
        variety = Variety.apply_inheritance(Variety.get_by_id(harvest['variety_id']))

    return render_template('harvests/detail.html',
                          harvest=harvest,
                          prev_harvest=prev_harvest,
                          next_harvest=next_harvest,
                          related_plantings=related_plantings,
                          related_diaries=related_diaries,
                          related_cookings=related_cookings,
                          supplements=supplements,
                          parent_crop=parent_crop,
                          variety=variety,
                          photo_pool_photos=PhotoPool.get_all())


def _build_planting_filter_data():
    """栽培中の植え付け一覧と種類・場所バッジフィルタ用データを組み立てる"""
    active_plantings = Planting.get_all_with_stats(status='active')
    filter_types = sorted(set(p['crop_type'] for p in active_plantings if p.get('crop_type')))
    filter_locations = sorted(set(p['location_name'] for p in active_plantings if p.get('location_name')))
    filter_type_icons = {}
    for p in active_plantings:
        t, icon = p.get('crop_type'), p.get('icon_path')
        if t and icon:
            icons = filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': p.get('image_color') or '#4CAF50'})
    return active_plantings, filter_types, filter_locations, filter_type_icons


@bp.route('/new')
def new():
    """収穫記録登録フォーム"""
    location_crop_id = request.args.get('location_crop_id', type=int)
    location_crop = None
    if location_crop_id:
        location_crop = Planting.get_by_id(location_crop_id)
        if not location_crop:
            flash('栽培記録が見つかりません', 'danger')
            return redirect(url_for('harvests.list'))

    active_plantings, filter_types, filter_locations, filter_type_icons = _build_planting_filter_data()
    today = date.today().isoformat()

    photo_pool_id = request.args.get('photo_pool_id', type=int)
    preselected_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None

    return render_template('harvests/form.html',
                          harvest=None,
                          action='create',
                          location_crop=location_crop,
                          active_plantings=active_plantings,
                          filter_types=filter_types,
                          filter_type_icons=filter_type_icons,
                          filter_locations=filter_locations,
                          today=today,
                          preselected_photo=preselected_photo,
                          photo_pool_photos=PhotoPool.get_all())


@bp.route('/create', methods=['POST'])
def create():
    """収穫記録作成"""
    location_crop_id = request.form.get('location_crop_id')

    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    data = {
        'location_crop_id': location_crop_id,
        'harvest_date': request.form.get('harvest_date'),
        'quantity': request.form.get('quantity') or None,
        'unit': request.form.get('unit') or None,
        'notes': request.form.get('notes')
    }

    # バリデーション
    if not data['harvest_date']:
        flash('収穫日は必須です', 'danger')
        return redirect(url_for('harvests.new', location_crop_id=location_crop_id))

    # 数量を数値に変換
    if data['quantity']:
        try:
            data['quantity'] = float(data['quantity'])
        except ValueError:
            flash('収穫量は数値で入力してください', 'danger')
            return redirect(url_for('harvests.new', location_crop_id=location_crop_id))

    # 画像アップロード処理（写真プール優先）
    photo_pool_id = request.form.get('photo_pool_id', type=int)
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            data['image_path'] = copy_image(pool_photo['image_path'], 'harvests')
    elif 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'harvests')
        data['image_path'] = image_path

    try:
        harvest_id = Harvest.create(data)
        if photo_pool_id and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'harvest', harvest_id, data['image_path'])
        flash('収穫記録を登録しました', 'success')
        return redirect(url_for('locations.detail',
                                location_id=location_crop['location_id']))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('harvests.new', location_crop_id=location_crop_id))


def _build_planting_multi_select_data():
    """_planting_select_multi_modal.html が要求する変数名でフィルタ・グルーピングデータを組み立てる"""
    active_plantings, planting_filter_types, planting_filter_locations, planting_filter_type_icons = \
        _build_planting_filter_data()

    def _ym(p):
        d = p.get('planted_date')
        return str(d)[:7] if d else ''
    grouped_plantings = [(k, [item for item in g]) for k, g in groupby(active_plantings, key=_ym)]

    return {
        'active_plantings': active_plantings,
        'planting_filter_types': planting_filter_types,
        'planting_filter_type_icons': planting_filter_type_icons,
        'planting_filter_locations': planting_filter_locations,
        'grouped_plantings': grouped_plantings,
    }


def _render_bulk_rows(location_crops, harvest_date_value=None, rows_values=None, preselected_photo_id=None):
    """一括登録フォームの行入力ステップを描画する"""
    preselected_photo = PhotoPool.get_by_id(preselected_photo_id) if preselected_photo_id else None
    rows_values = rows_values or {}
    row_preselected_photos = {}
    for lc_id_str, rv in rows_values.items():
        pool_id = rv.get('override_photo_pool_id')
        if pool_id:
            row_preselected_photos[lc_id_str] = PhotoPool.get_by_id(pool_id)
    return render_template('harvests/bulk_form.html',
                          location_crops=location_crops,
                          harvest_date_value=harvest_date_value or date.today().isoformat(),
                          rows_values=rows_values,
                          preselected_photo=preselected_photo,
                          row_preselected_photos=row_preselected_photos,
                          photo_pool_photos=PhotoPool.get_all(),
                          **_build_planting_multi_select_data())


@bp.route('/bulk/new')
def bulk_new():
    """収穫記録の一括登録フォーム（植え付け選択 → 行入力の2ステップ）"""
    location_crop_ids = request.args.getlist('location_crop_id', type=int)

    if not location_crop_ids:
        return render_template('harvests/bulk_form.html',
                              location_crops=None,
                              photo_pool_photos=PhotoPool.get_all(),
                              **_build_planting_multi_select_data())

    location_crops = [lc for lc in (Planting.get_by_id(lc_id) for lc_id in location_crop_ids) if lc]
    if not location_crops:
        flash('選択された栽培記録が見つかりません', 'danger')
        return redirect(url_for('harvests.bulk_new'))

    return _render_bulk_rows(location_crops)


@bp.route('/bulk/create', methods=['POST'])
def bulk_create():
    """収穫記録の一括登録処理"""
    location_crop_ids = request.form.getlist('location_crop_id', type=int)
    harvest_date = request.form.get('harvest_date')

    location_crops = [lc for lc in (Planting.get_by_id(lc_id) for lc_id in location_crop_ids) if lc]
    if not location_crops:
        flash('選択された栽培記録が見つかりません', 'danger')
        return redirect(url_for('harvests.bulk_new'))

    rows_values = {}
    errors = []

    if not harvest_date:
        errors.append('収穫日は必須です')

    parsed_rows = []
    for lc in location_crops:
        lc_id = lc['id']
        raw_quantity = request.form.get(f'quantity_{lc_id}') or ''
        unit = request.form.get(f'unit_{lc_id}') or None
        notes = request.form.get(f'notes_{lc_id}') or None
        override = request.form.get(f'override_image_{lc_id}') == '1'
        override_photo_pool_id = request.form.get(f'photo_pool_id_{lc_id}', type=int) if override else None
        rows_values[str(lc_id)] = {'quantity': raw_quantity, 'unit': unit or '', 'notes': notes or '',
                                    'override': override, 'override_photo_pool_id': override_photo_pool_id}

        quantity = None
        if raw_quantity:
            try:
                quantity = float(raw_quantity)
            except ValueError:
                errors.append(f'「{lc.get("crop_name")}」の収穫量は数値で入力してください')

        override_file = request.files.get(f'image_override_{lc_id}') if override else None
        parsed_rows.append({
            'location_crop_id': lc_id,
            'quantity': quantity,
            'unit': unit,
            'notes': notes,
            'override': override,
            'override_photo_pool_id': override_photo_pool_id,
            'override_file': override_file,
        })

    if errors:
        for e in errors:
            flash(e, 'danger')
        return _render_bulk_rows(location_crops, harvest_date_value=harvest_date, rows_values=rows_values,
                                 preselected_photo_id=request.form.get('photo_pool_id', type=int))

    # デフォルト画像の確定（写真プール優先）。同一ファイルを複数行のimage_pathに
    # 使い回すと片方の削除で他方まで壊れるため、行ごとに独立したコピーを作る。
    photo_pool_id = request.form.get('photo_pool_id', type=int)
    default_pool_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None
    default_upload_path = None
    if not default_pool_photo and 'image' in request.files and request.files['image'].filename:
        default_upload_path = save_image(request.files['image'], 'harvests')
    default_upload_used = False

    try:
        for row in parsed_rows:
            used_pool_id = None
            if row['override']:
                override_pool_photo = PhotoPool.get_by_id(row['override_photo_pool_id']) if row['override_photo_pool_id'] else None
                if override_pool_photo:
                    image_path = copy_image(override_pool_photo['image_path'], 'harvests')
                    used_pool_id = row['override_photo_pool_id']
                elif row['override_file'] and row['override_file'].filename:
                    image_path = save_image(row['override_file'], 'harvests')
                else:
                    image_path = None
            elif default_pool_photo:
                image_path = copy_image(default_pool_photo['image_path'], 'harvests')
                used_pool_id = photo_pool_id
            elif default_upload_path:
                if not default_upload_used:
                    image_path = default_upload_path
                    default_upload_used = True
                else:
                    image_path = copy_image(default_upload_path, 'harvests')
            else:
                image_path = None

            data = {
                'location_crop_id': row['location_crop_id'],
                'harvest_date': harvest_date,
                'quantity': row['quantity'],
                'unit': row['unit'],
                'notes': row['notes'],
                'image_path': image_path,
            }
            harvest_id = Harvest.create(data)
            if used_pool_id and image_path:
                PhotoPool.record_usage(used_pool_id, 'harvest', harvest_id, image_path)

        flash(f'{len(parsed_rows)}件の収穫記録を登録しました', 'success')
        return redirect(url_for('harvests.list'))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return _render_bulk_rows(location_crops, harvest_date_value=harvest_date, rows_values=rows_values,
                                 preselected_photo_id=request.form.get('photo_pool_id', type=int))


@bp.route('/<int:harvest_id>/edit')
def edit(harvest_id):
    """収穫記録編集フォーム"""
    harvest = Harvest.get_by_id(harvest_id)
    if not harvest:
        flash('収穫記録が見つかりません', 'danger')
        return redirect(url_for('harvests.list'))

    location_crop = Planting.get_by_id(harvest['location_crop_id'])

    return render_template('harvests/form.html',
                          harvest=harvest,
                          action='update',
                          location_crop=location_crop,
                          today=None,
                          photo_pool_photos=PhotoPool.get_all())


@bp.route('/<int:harvest_id>/update', methods=['POST'])
def update(harvest_id):
    """収穫記録更新"""
    harvest = Harvest.get_by_id(harvest_id)
    if not harvest:
        flash('収穫記録が見つかりません', 'danger')
        return redirect(url_for('harvests.list'))

    data = {
        'harvest_date': request.form.get('harvest_date'),
        'quantity': request.form.get('quantity') or None,
        'unit': request.form.get('unit') or None,
        'notes': request.form.get('notes'),
        'image_path': harvest.get('image_path')
    }

    # バリデーション
    if not data['harvest_date']:
        flash('収穫日は必須です', 'danger')
        return redirect(url_for('harvests.edit', harvest_id=harvest_id))

    # 数量を数値に変換
    if data['quantity']:
        try:
            data['quantity'] = float(data['quantity'])
        except ValueError:
            flash('収穫量は数値で入力してください', 'danger')
            return redirect(url_for('harvests.edit', harvest_id=harvest_id))

    # 画像アップロード処理（写真プール優先）
    photo_pool_id = request.form.get('photo_pool_id', type=int)
    replaced_from_pool = False
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            if harvest.get('image_path'):
                delete_image(harvest['image_path'])
            data['image_path'] = copy_image(pool_photo['image_path'], 'harvests')
            replaced_from_pool = True
    elif 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            if harvest.get('image_path'):
                delete_image(harvest['image_path'])
            image_path = save_image(image, 'harvests')
            data['image_path'] = image_path

    # 画像削除チェック
    if request.form.get('delete_image') == '1':
        if harvest.get('image_path'):
            delete_image(harvest['image_path'])
        data['image_path'] = None

    try:
        Harvest.update(harvest_id, data)
        if replaced_from_pool and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'harvest', harvest_id, data['image_path'])
        flash('収穫記録を更新しました', 'success')
        return redirect(url_for('harvests.detail', harvest_id=harvest_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('harvests.edit', harvest_id=harvest_id))


@bp.route('/<int:harvest_id>/delete', methods=['POST'])
def delete(harvest_id):
    """収穫記録削除"""
    harvest = Harvest.get_by_id(harvest_id)
    if not harvest:
        flash('収穫記録が見つかりません', 'danger')
        return redirect(url_for('harvests.list'))

    location_id = harvest.get('location_id')

    try:
        # 補足情報の連動削除（画像クリーンアップ）
        supplement_images = Supplement.delete_by_entity('harvest', harvest_id)
        for img_path in supplement_images:
            delete_image(img_path)
        if harvest.get('image_path'):
            delete_image(harvest['image_path'])
        Harvest.delete(harvest_id)
        flash('収穫記録を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    if location_id:
        return redirect(url_for('locations.detail', location_id=location_id))
    return redirect(url_for('harvests.list'))
