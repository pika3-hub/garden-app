from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.harvest import Harvest
from app.models.location_crop import LocationCrop
from app.models.location import Location
from app.models.crop import Crop
from app.utils.upload import save_image, delete_image
from datetime import date

bp = Blueprint('harvests', __name__, url_prefix='/harvests')


@bp.route('/')
def list():
    """収穫記録一覧"""
    keyword = request.args.get('keyword', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    location_id = request.args.get('location_id', '')
    crop_id = request.args.get('crop_id', '')

    if keyword or date_from or date_to or location_id or crop_id:
        harvests = Harvest.search(
            keyword=keyword if keyword else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            location_id=int(location_id) if location_id else None,
            crop_id=int(crop_id) if crop_id else None
        )
    else:
        harvests = Harvest.get_all()

    locations = Location.get_all()
    crops = Crop.get_all()

    return render_template('harvests/list.html',
                          harvests=harvests,
                          keyword=keyword,
                          date_from=date_from,
                          date_to=date_to,
                          selected_location_id=location_id,
                          selected_crop_id=crop_id,
                          locations=locations,
                          crops=crops)


@bp.route('/<int:harvest_id>')
def detail(harvest_id):
    """収穫記録詳細"""
    harvest = Harvest.get_by_id(harvest_id)
    if not harvest:
        flash('収穫記録が見つかりません', 'danger')
        return redirect(url_for('harvests.list'))

    return render_template('harvests/detail.html', harvest=harvest)


@bp.route('/new/<int:location_crop_id>')
def new(location_crop_id):
    """収穫記録登録フォーム"""
    location_crop = LocationCrop.get_by_id(location_crop_id)
    if not location_crop:
        flash('栽培記録が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    today = date.today().isoformat()

    return render_template('harvests/form.html',
                          harvest=None,
                          action='create',
                          location_crop=location_crop,
                          today=today)


@bp.route('/create', methods=['POST'])
def create():
    """収穫記録作成"""
    location_crop_id = request.form.get('location_crop_id')

    location_crop = LocationCrop.get_by_id(location_crop_id)
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

    # 画像アップロード処理
    if 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'harvests')
        data['image_path'] = image_path

    try:
        Harvest.create(data)
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

    location_crop = LocationCrop.get_by_id(harvest['location_crop_id'])

    return render_template('harvests/form.html',
                          harvest=harvest,
                          action='update',
                          location_crop=location_crop,
                          today=None)


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

    # 画像アップロード処理
    if 'image' in request.files:
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
        if harvest.get('image_path'):
            delete_image(harvest['image_path'])
        Harvest.delete(harvest_id)
        flash('収穫記録を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    if location_id:
        return redirect(url_for('locations.detail', location_id=location_id))
    return redirect(url_for('harvests.list'))
