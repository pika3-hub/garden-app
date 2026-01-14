from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.crop import Crop
from app.models.location_crop import LocationCrop
from app.models.diary import DiaryEntry

bp = Blueprint('crops', __name__, url_prefix='/crops')


@bp.route('/')
def list():
    """作物一覧"""
    keyword = request.args.get('keyword', '')
    if keyword:
        crops = Crop.search(keyword)
    else:
        crops = Crop.get_all()
    return render_template('crops/list.html', crops=crops, keyword=keyword)


@bp.route('/<int:crop_id>')
def detail(crop_id):
    """作物詳細"""
    crop = Crop.get_by_id(crop_id)
    if not crop:
        flash('作物が見つかりません', 'danger')
        return redirect(url_for('crops.list'))

    # 栽培中の場所を取得
    active_locations = LocationCrop.get_by_crop(crop_id, status='active')
    # 収穫済みの場所を取得
    harvested_locations = LocationCrop.get_by_crop(crop_id, status='harvested')
    # 関連する日記を取得
    related_diaries = DiaryEntry.get_by_crop(crop_id)

    return render_template('crops/detail.html',
                          crop=crop,
                          active_locations=active_locations,
                          harvested_locations=harvested_locations,
                          related_diaries=related_diaries)


@bp.route('/new')
def new():
    """作物登録フォーム"""
    return render_template('crops/form.html', crop=None, action='create')


@bp.route('/create', methods=['POST'])
def create():
    """作物登録処理"""
    data = {
        'name': request.form.get('name'),
        'crop_type': request.form.get('crop_type'),
        'variety': request.form.get('variety'),
        'characteristics': request.form.get('characteristics'),
        'planting_season': request.form.get('planting_season'),
        'harvest_season': request.form.get('harvest_season'),
        'notes': request.form.get('notes')
    }

    # バリデーション
    if not data['name'] or not data['crop_type']:
        flash('作物名と作物種類は必須です', 'danger')
        return redirect(url_for('crops.new'))

    try:
        crop_id = Crop.create(data)
        flash(f'作物「{data["name"]}」を登録しました', 'success')
        return redirect(url_for('crops.detail', crop_id=crop_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('crops.new'))


@bp.route('/<int:crop_id>/edit')
def edit(crop_id):
    """作物編集フォーム"""
    crop = Crop.get_by_id(crop_id)
    if not crop:
        flash('作物が見つかりません', 'danger')
        return redirect(url_for('crops.list'))
    return render_template('crops/form.html', crop=crop, action='update')


@bp.route('/<int:crop_id>/update', methods=['POST'])
def update(crop_id):
    """作物更新処理"""
    crop = Crop.get_by_id(crop_id)
    if not crop:
        flash('作物が見つかりません', 'danger')
        return redirect(url_for('crops.list'))

    data = {
        'name': request.form.get('name'),
        'crop_type': request.form.get('crop_type'),
        'variety': request.form.get('variety'),
        'characteristics': request.form.get('characteristics'),
        'planting_season': request.form.get('planting_season'),
        'harvest_season': request.form.get('harvest_season'),
        'notes': request.form.get('notes')
    }

    # バリデーション
    if not data['name'] or not data['crop_type']:
        flash('作物名と作物種類は必須です', 'danger')
        return redirect(url_for('crops.edit', crop_id=crop_id))

    try:
        Crop.update(crop_id, data)
        flash(f'作物「{data["name"]}」を更新しました', 'success')
        return redirect(url_for('crops.detail', crop_id=crop_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('crops.edit', crop_id=crop_id))


@bp.route('/<int:crop_id>/delete', methods=['POST'])
def delete(crop_id):
    """作物削除処理"""
    crop = Crop.get_by_id(crop_id)
    if not crop:
        flash('作物が見つかりません', 'danger')
        return redirect(url_for('crops.list'))

    try:
        Crop.delete(crop_id)
        flash(f'作物「{crop["name"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('crops.list'))
