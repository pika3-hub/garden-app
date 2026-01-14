from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.location import Location
from app.models.location_crop import LocationCrop
from app.models.crop import Crop
from app.models.diary import DiaryEntry

bp = Blueprint('locations', __name__, url_prefix='/locations')


@bp.route('/')
def list():
    """場所一覧"""
    keyword = request.args.get('keyword', '')
    if keyword:
        locations = Location.search(keyword)
    else:
        locations = Location.get_all()
    return render_template('locations/list.html', locations=locations, keyword=keyword)


@bp.route('/<int:location_id>')
def detail(location_id):
    """場所詳細"""
    location = Location.get_by_id(location_id)
    if not location:
        flash('場所が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    # 栽培中の作物を取得
    active_crops = LocationCrop.get_by_location(location_id, status='active')

    # 植え付け用の作物リストを取得
    all_crops = Crop.get_all()

    # 関連する日記を取得
    related_diaries = DiaryEntry.get_by_location(location_id)

    return render_template('locations/detail.html',
                          location=location,
                          active_crops=active_crops,
                          all_crops=all_crops,
                          related_diaries=related_diaries)


@bp.route('/new')
def new():
    """場所登録フォーム"""
    return render_template('locations/form.html', location=None, action='create')


@bp.route('/create', methods=['POST'])
def create():
    """場所登録処理"""
    data = {
        'name': request.form.get('name'),
        'location_type': request.form.get('location_type'),
        'area_size': request.form.get('area_size'),
        'sun_exposure': request.form.get('sun_exposure'),
        'notes': request.form.get('notes')
    }

    # バリデーション
    if not data['name'] or not data['location_type']:
        flash('場所名と場所種類は必須です', 'danger')
        return redirect(url_for('locations.new'))

    try:
        location_id = Location.create(data)
        flash(f'場所「{data["name"]}」を登録しました', 'success')
        return redirect(url_for('locations.detail', location_id=location_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('locations.new'))


@bp.route('/<int:location_id>/edit')
def edit(location_id):
    """場所編集フォーム"""
    location = Location.get_by_id(location_id)
    if not location:
        flash('場所が見つかりません', 'danger')
        return redirect(url_for('locations.list'))
    return render_template('locations/form.html', location=location, action='update')


@bp.route('/<int:location_id>/update', methods=['POST'])
def update(location_id):
    """場所更新処理"""
    location = Location.get_by_id(location_id)
    if not location:
        flash('場所が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    data = {
        'name': request.form.get('name'),
        'location_type': request.form.get('location_type'),
        'area_size': request.form.get('area_size'),
        'sun_exposure': request.form.get('sun_exposure'),
        'notes': request.form.get('notes')
    }

    # バリデーション
    if not data['name'] or not data['location_type']:
        flash('場所名と場所種類は必須です', 'danger')
        return redirect(url_for('locations.edit', location_id=location_id))

    try:
        Location.update(location_id, data)
        flash(f'場所「{data["name"]}」を更新しました', 'success')
        return redirect(url_for('locations.detail', location_id=location_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('locations.edit', location_id=location_id))


@bp.route('/<int:location_id>/delete', methods=['POST'])
def delete(location_id):
    """場所削除処理"""
    location = Location.get_by_id(location_id)
    if not location:
        flash('場所が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    try:
        Location.delete(location_id)
        flash(f'場所「{location["name"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('locations.list'))


@bp.route('/<int:location_id>/plant', methods=['POST'])
def plant(location_id):
    """作物を場所に植え付け"""
    location = Location.get_by_id(location_id)
    if not location:
        flash('場所が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    data = {
        'location_id': location_id,
        'crop_id': request.form.get('crop_id'),
        'planted_date': request.form.get('planted_date'),
        'quantity': request.form.get('quantity'),
        'notes': request.form.get('notes')
    }

    # バリデーション
    if not data['crop_id']:
        flash('作物を選択してください', 'danger')
        return redirect(url_for('locations.detail', location_id=location_id))

    try:
        LocationCrop.plant(data)
        crop = Crop.get_by_id(data['crop_id'])
        flash(f'「{crop["name"]}」を植え付けました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('locations.detail', location_id=location_id))


@bp.route('/<int:location_id>/harvest/<int:location_crop_id>', methods=['POST'])
def harvest(location_id, location_crop_id):
    """作物を収穫済みに変更"""
    try:
        LocationCrop.harvest(location_crop_id)
        flash('収穫済みに変更しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('locations.detail', location_id=location_id))


@bp.route('/<int:location_id>/remove/<int:location_crop_id>', methods=['POST'])
def remove_crop(location_id, location_crop_id):
    """作物を削除（取り除く）"""
    try:
        LocationCrop.delete(location_crop_id)
        flash('作物を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('locations.detail', location_id=location_id))


@bp.route('/<int:location_id>/canvas')
def canvas(location_id):
    """キャンバス編集ページ"""
    location = Location.get_by_id(location_id)
    if not location:
        flash('場所が見つかりません', 'danger')
        return redirect(url_for('locations.list'))

    crops = LocationCrop.get_crops_with_position(location_id)
    return render_template('locations/canvas.html',
                          location=location,
                          crops=crops)


@bp.route('/<int:location_id>/canvas/data', methods=['GET'])
def get_canvas_data(location_id):
    """キャンバスデータ取得API"""
    canvas_data = Location.get_canvas_data(location_id)
    if canvas_data:
        return jsonify(canvas_data)
    else:
        return jsonify({'version': '1.0', 'objects': []})


@bp.route('/<int:location_id>/canvas/save', methods=['POST'])
def save_canvas_data(location_id):
    """キャンバスデータ保存API"""
    try:
        canvas_data = request.get_json()
        Location.save_canvas_data(location_id, canvas_data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@bp.route('/<int:location_id>/crops/<int:location_crop_id>/position', methods=['POST'])
def update_crop_position(location_id, location_crop_id):
    """作物位置更新API"""
    try:
        data = request.get_json()
        LocationCrop.update_position(location_crop_id, data['x'], data['y'])
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
