from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.harvest import Harvest
from app.models.planting import Planting
from app.models.location import Location
from app.models.crop import Crop
from app.models.diary import DiaryEntry
from app.models.supplement import Supplement
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
    return render_template('harvests/list.html', harvests=harvests, filter_types=filter_types, filter_locations=filter_locations)


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

    # 補足情報
    supplements = Supplement.get_by_entity('harvest', harvest_id)

    return render_template('harvests/detail.html',
                          harvest=harvest,
                          prev_harvest=prev_harvest,
                          next_harvest=next_harvest,
                          related_plantings=related_plantings,
                          related_diaries=related_diaries,
                          supplements=supplements,
                          photo_pool_photos=PhotoPool.get_all())


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

    active_plantings = Planting.get_all_with_stats(status='active')
    filter_types = sorted(set(p['crop_type'] for p in active_plantings if p.get('crop_type')))
    filter_locations = sorted(set(p['location_name'] for p in active_plantings if p.get('location_name')))
    today = date.today().isoformat()

    photo_pool_id = request.args.get('photo_pool_id', type=int)
    preselected_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None

    return render_template('harvests/form.html',
                          harvest=None,
                          action='create',
                          location_crop=location_crop,
                          active_plantings=active_plantings,
                          filter_types=filter_types,
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
