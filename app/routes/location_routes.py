from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.location import Location
from app.models.planting import Planting
from app.models.crop import Crop
from app.models.diary import DiaryEntry
from app.models.harvest import Harvest
from app.utils.upload import save_image, delete_image

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
    active_crops = Planting.get_by_location(location_id, status='active')

    # 各栽培記録に収穫履歴を追加
    for crop in active_crops:
        crop['harvests'] = Harvest.get_by_location_crop(crop['id'])

    # 植え付け用の作物リストを取得
    all_crops = Crop.get_all()

    # 関連する日記を取得
    related_diaries = DiaryEntry.get_by_location(location_id)

    today = date.today().isoformat()
    prev_location, next_location = Location.get_adjacent(location_id)

    return render_template('locations/detail.html',
                          location=location,
                          active_crops=active_crops,
                          all_crops=all_crops,
                          related_diaries=related_diaries,
                          today=today,
                          prev_location=prev_location,
                          next_location=next_location)


@bp.route('/new')
def new():
    """場所登録フォーム"""
    bg_images = Location.get_bg_images()
    return render_template('locations/form.html', location=None, action='create', bg_images=bg_images)


@bp.route('/create', methods=['POST'])
def create():
    """場所登録処理"""
    data = {
        'name': request.form.get('name'),
        'location_type': request.form.get('location_type'),
        'area_size': request.form.get('area_size'),
        'sun_exposure': request.form.get('sun_exposure'),
        'notes': request.form.get('notes'),
        'bg_image': request.form.get('bg_image') or None
    }

    # バリデーション
    if not data['name'] or not data['location_type']:
        flash('場所名と場所種類は必須です', 'danger')
        return redirect(url_for('locations.new'))

    # 画像アップロード処理
    if 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'locations')
        data['image_path'] = image_path

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
    bg_images = Location.get_bg_images()
    return render_template('locations/form.html', location=location, action='update', bg_images=bg_images)


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
        'notes': request.form.get('notes'),
        'image_path': location.get('image_path'),  # 既存の画像パスを保持
        'bg_image': request.form.get('bg_image') or None
    }

    # バリデーション
    if not data['name'] or not data['location_type']:
        flash('場所名と場所種類は必須です', 'danger')
        return redirect(url_for('locations.edit', location_id=location_id))

    # 画像アップロード処理
    if 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            # 古い画像を削除
            if location.get('image_path'):
                delete_image(location['image_path'])
            # 新しい画像を保存
            image_path = save_image(image, 'locations')
            data['image_path'] = image_path

    # 画像削除チェック
    if request.form.get('delete_image') == '1':
        if location.get('image_path'):
            delete_image(location['image_path'])
        data['image_path'] = None

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
        # 画像を削除
        if location.get('image_path'):
            delete_image(location['image_path'])
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
        Planting.plant(data)
        crop = Crop.get_by_id(data['crop_id'])
        flash(f'「{crop["name"]}」を植え付けました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('locations.detail', location_id=location_id))


@bp.route('/<int:location_id>/complete-harvest/<int:location_crop_id>', methods=['POST'])
def complete_harvest(location_id, location_crop_id):
    """栽培終了（収穫済みステータスに変更）"""
    try:
        end_date = request.form.get('end_date') or None

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

    return redirect(url_for('locations.detail', location_id=location_id))


@bp.route('/<int:location_id>/remove/<int:location_crop_id>', methods=['POST'])
def remove_crop(location_id, location_crop_id):
    """作物を削除（取り除く）"""
    try:
        Planting.delete(location_crop_id)
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

    crops = Planting.get_crops_with_position(location_id)
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
        return jsonify({'version': '2.0', 'placements': []})


@bp.route('/<int:location_id>/canvas/history/range', methods=['GET'])
def canvas_history_range(location_id):
    """見取り図に変化がある日付一覧を返すAPI"""
    dates = Planting.get_historical_change_dates(location_id)
    if dates:
        return jsonify({'dates': dates})
    return jsonify({'dates': []})


@bp.route('/<int:location_id>/canvas/history', methods=['GET'])
def canvas_history(location_id):
    """指定日付の見取り図配置データを返すAPI"""
    target_date = request.args.get('date')
    if not target_date:
        return jsonify({'error': 'date parameter is required'}), 400
    data = Planting.get_historical_canvas_data(location_id, target_date)
    return jsonify(data)


@bp.route('/<int:location_id>/canvas/save', methods=['POST'])
def save_canvas_data(location_id):
    """キャンバスデータ保存API"""
    try:
        canvas_data = request.get_json()
        Location.save_canvas_data(location_id, canvas_data)

        # placements から各作物の位置を更新
        if canvas_data and 'placements' in canvas_data:
            # 同一 locationCropId の最初の配置座標を保存
            seen = set()
            for p in canvas_data['placements']:
                lc_id = p.get('locationCropId')
                if lc_id and lc_id not in seen:
                    seen.add(lc_id)
                    Planting.update_position(lc_id, p.get('x', 0), p.get('y', 0))

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
