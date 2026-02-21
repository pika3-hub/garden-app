from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.planting_record import PlantingRecord
from app.models.planting import Planting
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
    return render_template('plantings/list.html', crops=crops, current_status=status)


@bp.route('/<int:location_crop_id>')
def detail(location_crop_id):
    """栽培詳細（＋栽培記録一覧）"""
    location_crop = Planting.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培情報が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    records = PlantingRecord.get_by_location_crop(location_crop_id)

    return render_template('plantings/detail.html',
                          records=records,
                          location_crop=location_crop)


@bp.route('/record/<int:record_id>')
def record_detail(record_id):
    """栽培記録個別詳細"""
    record = PlantingRecord.get_by_id(record_id)
    if not record:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('plantings.index'))

    return render_template('plantings/record_detail.html', record=record)


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
