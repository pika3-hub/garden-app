import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.planting_record import PlantingRecord
from app.models.planting import Planting
from app.models.crop import Crop
from app.models.location import Location
from app.models.task import Task
from app.utils.upload import save_image, delete_image
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
    return render_template('plantings/list.html', crops=crops, current_status=status, task_counts=task_counts)


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

    return render_template('plantings/detail.html',
                          records=records,
                          location_crop=location_crop,
                          location=location,
                          today=today,
                          canvas_snapshot=canvas_snapshot,
                          prev_planting=prev_planting,
                          next_planting=next_planting,
                          related_tasks=related_tasks)


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

    return render_template('plantings/record_detail.html',
                          record=record,
                          prev_record=prev_record,
                          next_record=next_record)


@bp.route('/new/<int:location_crop_id>')
def new(location_crop_id):
    """栽培記録登録フォーム"""
    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    today = date.today().isoformat()

    return render_template('plantings/form.html',
                          record=None,
                          action='create',
                          location_crop=location_crop,
                          today=today)


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

    if 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'growth_records')
        data['image_path'] = image_path

    try:
        PlantingRecord.create(data)
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
                          today=None)


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

    if 'image' in request.files:
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
    locations = Location.get_all()
    today = date.today().isoformat()
    preselected_location_id = request.args.get('location_id', type=int)
    preselected_crop_id = request.args.get('crop_id', type=int)
    return render_template('plantings/planting_form.html',
                           planting=None,
                           crops=crops,
                           locations=locations,
                           today=today,
                           preselected_location_id=preselected_location_id,
                           preselected_crop_id=preselected_crop_id)


@bp.route('/plant/create', methods=['POST'])
def plant_create():
    """植え付け登録処理"""
    location_id = request.form.get('location_id')
    crop_id = request.form.get('crop_id')

    if not location_id or not crop_id:
        flash('場所と作物は必須です', 'danger')
        return redirect(url_for('plantings.plant_new'))

    data = {
        'location_id': location_id,
        'crop_id': crop_id,
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
    locations = Location.get_all()
    earliest_child_date = Planting.get_earliest_child_date(location_crop_id)

    return render_template('plantings/planting_form.html',
                           planting=planting,
                           crops=crops,
                           locations=locations,
                           earliest_child_date=earliest_child_date,
                           today=None)


@bp.route('/<int:location_crop_id>/update', methods=['POST'])
def planting_update(location_crop_id):
    """植え付け更新処理"""
    planting = Planting.get_by_id(location_crop_id)
    if not planting:
        flash('植え付け情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    location_id = request.form.get('location_id')
    crop_id = request.form.get('crop_id')

    if not location_id or not crop_id:
        flash('場所と作物は必須です', 'danger')
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
