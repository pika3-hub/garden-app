import json
from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.planting_record import PlantingRecord
from app.models.planting import Planting
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.location import Location
from app.models.task import Task
from app.models.harvest import Harvest
from app.models.diary import DiaryEntry
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image, copy_image
from datetime import date

bp = Blueprint('plantings', __name__, url_prefix='/plantings')


@bp.route('/')
def index():
    """栽培記録一覧（タブフィルター付き）"""
    status = request.args.get('status', 'active')
    if status == 'all':
        crops = Planting.get_all_with_stats(status=None)
    else:
        crops = Planting.get_all_with_stats(status=status)
    planting_ids = [c['id'] for c in crops]
    task_counts = Task.get_upcoming_task_counts('location_crop', planting_ids)
    filter_types = sorted(set(c['crop_type'] for c in crops if c['crop_type']))
    filter_locations = sorted(set(c['location_name'] for c in crops if c['location_name']))
    filter_type_icons = {}
    for c in crops:
        t, icon = c['crop_type'], c['icon_path']
        if t and icon:
            icons = filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': c['image_color'] or '#4CAF50'})

    def _ym_key(c):
        d = c.get('planted_date')
        return str(d)[:7] if d else ''

    grouped_crops = [(k, [item for item in g]) for k, g in groupby(crops, key=_ym_key)]

    return render_template('plantings/list.html', crops=crops, grouped_crops=grouped_crops, current_status=status, task_counts=task_counts, filter_types=filter_types, filter_type_icons=filter_type_icons, filter_locations=filter_locations)


@bp.route('/<int:location_crop_id>')
def detail(location_crop_id):
    """栽培詳細（＋栽培記録一覧）"""
    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    records = PlantingRecord.get_by_location_crop(location_crop_id)
    location = Location.get_by_id(location_crop['location_id'])
    today = date.today().isoformat()

    canvas_snapshot = None
    if location_crop.get('canvas_snapshot'):
        try:
            canvas_snapshot = json.loads(location_crop['canvas_snapshot'])
        except (json.JSONDecodeError, TypeError):
            canvas_snapshot = None

    prev_planting, next_planting = Planting.get_adjacent(location_crop_id)
    related_tasks = Task.get_incomplete_tasks_for_entity('location_crop', location_crop_id)
    related_harvests = Harvest.get_by_location_crop(location_crop_id, limit=10)
    related_diaries = DiaryEntry.get_by_location_crop(location_crop_id, limit=10)
    photo_pool_photos = PhotoPool.get_all()

    parent_crop = Crop.get_by_id(location_crop['effective_crop_id'])
    variety = None
    if location_crop.get('variety_id'):
        variety = Variety.apply_inheritance(Variety.get_by_id(location_crop['variety_id']))

    return render_template('plantings/detail.html',
                          photo_pool_photos=photo_pool_photos,
                          records=records,
                          location_crop=location_crop,
                          location=location,
                          today=today,
                          canvas_snapshot=canvas_snapshot,
                          prev_planting=prev_planting,
                          next_planting=next_planting,
                          related_tasks=related_tasks,
                          related_harvests=related_harvests,
                          related_diaries=related_diaries,
                          parent_crop=parent_crop,
                          variety=variety)


@bp.route('/<int:location_crop_id>/end', methods=['POST'])
def end_cultivation(location_crop_id):
    """栽培終了（植え付け詳細から）"""
    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    try:
        end_date = request.form.get('end_date') or None
        location_id = location_crop['location_id']

        # スナップショット取得（作物が配置されている場合のみ）
        canvas_data = Location.get_canvas_data(location_id)
        snapshot = None
        if canvas_data and 'placements' in canvas_data:
            is_placed = any(
                p.get('locationCropId') == location_crop_id
                for p in canvas_data['placements']
            )
            if is_placed:
                snapshot = canvas_data

        Planting.harvest(location_crop_id, end_date=end_date, canvas_snapshot=snapshot)
        Location.remove_from_canvas(location_id, location_crop_id)
        flash('栽培を終了しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('plantings.detail', location_crop_id=location_crop_id))


@bp.route('/record/<int:record_id>')
def record_detail(record_id):
    """栽培記録個別詳細"""
    record = PlantingRecord.get_by_id(record_id)
    if not record:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    prev_record, next_record = PlantingRecord.get_adjacent(record_id)

    parent_crop = Crop.get_by_id(record['effective_crop_id'])
    variety = None
    if record.get('variety_id'):
        variety = Variety.apply_inheritance(Variety.get_by_id(record['variety_id']))

    return render_template('plantings/record_detail.html',
                          record=record,
                          prev_record=prev_record,
                          next_record=next_record,
                          parent_crop=parent_crop,
                          variety=variety,
                          photo_pool_photos=PhotoPool.get_all())


@bp.route('/new/<int:location_crop_id>')
def new(location_crop_id):
    """栽培記録登録フォーム"""
    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    today = date.today().isoformat()

    photo_pool_id = request.args.get('photo_pool_id', type=int)
    preselected_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None

    return render_template('plantings/form.html',
                          record=None,
                          action='create',
                          location_crop=location_crop,
                          today=today,
                          preselected_photo=preselected_photo,
                          photo_pool_photos=PhotoPool.get_all())


@bp.route('/create', methods=['POST'])
def create():
    """栽培記録作成"""
    location_crop_id = request.form.get('location_crop_id')

    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    data = {
        'location_crop_id': location_crop_id,
        'recorded_at': request.form.get('recorded_at'),
        'notes': request.form.get('notes')
    }

    if not data['recorded_at']:
        flash('記録日は必須です', 'danger')
        return redirect(url_for('plantings.new', location_crop_id=location_crop_id))

    photo_pool_id = request.form.get('photo_pool_id', type=int)
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            data['image_path'] = copy_image(pool_photo['image_path'], 'growth_records')
    elif 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'growth_records')
        data['image_path'] = image_path

    try:
        record_id = PlantingRecord.create(data)
        if photo_pool_id and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'planting_record', record_id, data['image_path'])
        flash('栽培記録を登録しました', 'success')
        return redirect(url_for('plantings.detail', location_crop_id=location_crop_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('plantings.new', location_crop_id=location_crop_id))


@bp.route('/record/<int:record_id>/edit')
def edit(record_id):
    """栽培記録編集フォーム"""
    record = PlantingRecord.get_by_id(record_id)
    if not record:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    location_crop = Planting.get_by_id(record['location_crop_id'])

    return render_template('plantings/form.html',
                          record=record,
                          action='update',
                          location_crop=location_crop,
                          today=None,
                          photo_pool_photos=PhotoPool.get_all())


@bp.route('/record/<int:record_id>/update', methods=['POST'])
def update(record_id):
    """栽培記録更新"""
    record = PlantingRecord.get_by_id(record_id)
    if not record:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    data = {
        'recorded_at': request.form.get('recorded_at'),
        'notes': request.form.get('notes'),
        'image_path': record.get('image_path')
    }

    if not data['recorded_at']:
        flash('記録日は必須です', 'danger')
        return redirect(url_for('plantings.edit', record_id=record_id))

    photo_pool_id = request.form.get('photo_pool_id', type=int)
    replaced_from_pool = False
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            if record.get('image_path'):
                delete_image(record['image_path'])
            data['image_path'] = copy_image(pool_photo['image_path'], 'growth_records')
            replaced_from_pool = True
    elif 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            if record.get('image_path'):
                delete_image(record['image_path'])
            image_path = save_image(image, 'growth_records')
            data['image_path'] = image_path

    if request.form.get('delete_image') == '1':
        if record.get('image_path'):
            delete_image(record['image_path'])
        data['image_path'] = None

    try:
        PlantingRecord.update(record_id, data)
        if replaced_from_pool and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'planting_record', record_id, data['image_path'])
        flash('栽培記録を更新しました', 'success')
        return redirect(url_for('plantings.record_detail', record_id=record_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('plantings.edit', record_id=record_id))


@bp.route('/record/<int:record_id>/delete', methods=['POST'])
def delete(record_id):
    """栽培記録削除"""
    record = PlantingRecord.get_by_id(record_id)
    if not record:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    location_crop_id = record.get('location_crop_id')

    try:
        if record.get('image_path'):
            delete_image(record['image_path'])
        PlantingRecord.delete(record_id)
        flash('栽培記録を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    if location_crop_id:
        return redirect(url_for('plantings.detail', location_crop_id=location_crop_id))
    return redirect(url_for('plantings.index'))


@bp.route('/<int:location_crop_id>/edit-harvested')
def planting_edit_harvested(location_crop_id):
    """栽培終了済み植え付けの限定編集フォーム"""
    planting = Planting.get_by_id(location_crop_id)
    if not planting or planting['status'] != 'harvested':
        flash('対象の植え付けが見つかりません', 'danger')
        return redirect(url_for('plantings.index'))
    return render_template('plantings/harvested_edit.html', planting=planting)


@bp.route('/<int:location_crop_id>/update-harvested', methods=['POST'])
def planting_update_harvested(location_crop_id):
    """栽培終了済み植え付けの限定更新処理"""
    planting = Planting.get_by_id(location_crop_id)
    if not planting or planting['status'] != 'harvested':
        flash('対象の植え付けが見つかりません', 'danger')
        return redirect(url_for('plantings.index'))
    end_date = request.form.get('end_date') or None
    notes = request.form.get('notes') or None
    try:
        Planting.update_end_date_notes(location_crop_id, end_date, notes)
        flash('植え付け情報を更新しました', 'success')
        return redirect(url_for('plantings.detail', location_crop_id=location_crop_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('plantings.planting_edit_harvested', location_crop_id=location_crop_id))


@bp.route('/<int:location_crop_id>/place')
def place(location_crop_id):
    """見取り図配置ページ"""
    planting = Planting.get_by_id(location_crop_id)
    if not planting:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))
    location = Location.get_by_id(planting['location_id'])
    crops_with_position = Planting.get_crops_with_position(location['id'])
    return render_template('plantings/place.html',
                           planting=planting,
                           location=location,
                           crops=crops_with_position,
                           new_location_crop_id=location_crop_id)


@bp.route('/plant/new')
def plant_new():
    """植え付け登録フォーム"""
    crops = Crop.get_all()
    varieties = [Variety.apply_inheritance(v) for v in Variety.get_all()]
    locations = Location.get_all()
    crop_filter_types = sorted(set(c['crop_type'] for c in crops if c['crop_type']))
    crop_filter_type_icons = {}
    for c in crops:
        t, icon = c['crop_type'], c['icon_path']
        if t and icon:
            icons = crop_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': c['image_color'] or '#4CAF50'})
    location_filter_types = sorted(set(l['location_type'] for l in locations if l['location_type']))
    today = date.today().isoformat()
    preselected_location_id = request.args.get('location_id', type=int)
    preselected_crop_id = request.args.get('crop_id', type=int)
    preselected_variety_id = request.args.get('variety_id', type=int)
    preselected_crop = next((c for c in crops if c['id'] == preselected_crop_id), None) if preselected_crop_id else None
    preselected_location = next((l for l in locations if l['id'] == preselected_location_id), None) if preselected_location_id else None
    preselected_variety = next((v for v in varieties if v['id'] == preselected_variety_id), None) if preselected_variety_id else None
    return render_template('plantings/planting_form.html',
                           planting=None,
                           crops=crops,
                           varieties=varieties,
                           locations=locations,
                           crop_filter_types=crop_filter_types,
                           crop_filter_type_icons=crop_filter_type_icons,
                           location_filter_types=location_filter_types,
                           today=today,
                           preselected_location=preselected_location,
                           preselected_crop=preselected_crop,
                           preselected_variety=preselected_variety)


@bp.route('/plant/create', methods=['POST'])
def plant_create():
    """植え付け登録処理"""
    location_id = request.form.get('location_id')
    crop_id = request.form.get('crop_id', type=int) or None
    variety_id = request.form.get('variety_id', type=int) or None

    if not location_id or (not crop_id and not variety_id):
        flash('場所と作物（または品種）は必須です', 'danger')
        return redirect(url_for('plantings.plant_new'))

    data = {
        'location_id': location_id,
        'crop_id': crop_id,
        'variety_id': variety_id,
        'planted_date': request.form.get('planted_date') or None,
        'quantity': request.form.get('quantity') or None,
        'notes': request.form.get('notes') or None,
    }

    try:
        new_id = Planting.plant(data)
        flash('植え付けを登録しました', 'success')
        return redirect(url_for('plantings.place', location_crop_id=new_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('plantings.plant_new'))


@bp.route('/<int:location_crop_id>/edit')
def planting_edit(location_crop_id):
    """植え付け編集フォーム"""
    planting = Planting.get_by_id(location_crop_id)
    if not planting:
        flash('植え付け情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    crops = Crop.get_all()
    varieties = [Variety.apply_inheritance(v) for v in Variety.get_all()]
    locations = Location.get_all()
    crop_filter_types = sorted(set(c['crop_type'] for c in crops if c['crop_type']))
    crop_filter_type_icons = {}
    for c in crops:
        t, icon = c['crop_type'], c['icon_path']
        if t and icon:
            icons = crop_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': c['image_color'] or '#4CAF50'})
    location_filter_types = sorted(set(l['location_type'] for l in locations if l['location_type']))
    earliest_child_date = Planting.get_earliest_child_date(location_crop_id)
    preselected_crop = next((c for c in crops if c['id'] == planting.get('crop_id')), None) if planting.get('crop_id') else None
    preselected_variety = next((v for v in varieties if v['id'] == planting.get('variety_id')), None) if planting.get('variety_id') else None
    preselected_location = next((l for l in locations if l['id'] == planting['location_id']), None)

    return render_template('plantings/planting_form.html',
                           planting=planting,
                           crops=crops,
                           varieties=varieties,
                           locations=locations,
                           crop_filter_types=crop_filter_types,
                           crop_filter_type_icons=crop_filter_type_icons,
                           location_filter_types=location_filter_types,
                           earliest_child_date=earliest_child_date,
                           preselected_crop=preselected_crop,
                           preselected_variety=preselected_variety,
                           preselected_location=preselected_location,
                           today=None)


@bp.route('/<int:location_crop_id>/update', methods=['POST'])
def planting_update(location_crop_id):
    """植え付け更新処理"""
    planting = Planting.get_by_id(location_crop_id)
    if not planting:
        flash('植え付け情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    location_id = request.form.get('location_id')
    crop_id = request.form.get('crop_id', type=int) or None
    variety_id = request.form.get('variety_id', type=int) or None

    if not location_id or (not crop_id and not variety_id):
        flash('場所と作物（または品種）は必須です', 'danger')
        return redirect(url_for('plantings.planting_edit', location_crop_id=location_crop_id))

    planted_date = request.form.get('planted_date') or None
    if planted_date:
        earliest = Planting.get_earliest_child_date(location_crop_id)
        if earliest and planted_date > earliest[:10]:
            flash(f'植え付け日は栽培記録・収穫記録の日付（{earliest[:10]}）より前の日付にしてください', 'danger')
            return redirect(url_for('plantings.planting_edit', location_crop_id=location_crop_id))

    data = {
        'location_id': location_id,
        'crop_id': crop_id,
        'variety_id': variety_id,
        'planted_date': planted_date,
        'quantity': request.form.get('quantity') or None,
        'notes': request.form.get('notes') or None,
    }

    try:
        Planting.update_all(location_crop_id, data)
        flash('植え付けを更新しました', 'success')
        return redirect(url_for('plantings.detail', location_crop_id=location_crop_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('plantings.planting_edit', location_crop_id=location_crop_id))
