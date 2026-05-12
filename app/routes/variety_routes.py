import os
from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.planting import Planting
from app.models.diary import DiaryEntry
from app.models.harvest import Harvest
from app.models.task import Task
from app.models.supplement import Supplement
from app.models.cooking import Cooking
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image, copy_image

bp = Blueprint('varieties', __name__, url_prefix='/varieties')


def _get_crop_icon_list():
    icon_dir = os.path.join(current_app.static_folder, 'images', 'crop_icons')
    return sorted(os.listdir(icon_dir))


@bp.route('/')
def list():
    """品種一覧（親作物でグルーピング表示、品種数の多い順）"""
    varieties = Variety.get_all()
    for v in varieties:
        Variety.apply_inheritance(v)

    active_variety_ids = Planting.get_active_variety_ids()

    # フィルター用データ（作物一覧と同じ規約）
    filter_types = sorted(set(v['crop_type'] for v in varieties if v.get('crop_type')))
    filter_type_icons = {}
    for v in varieties:
        t = v.get('crop_type')
        icon = v.get('crop_icon_path')
        color = v.get('crop_image_color') or '#4CAF50'
        if t and icon:
            icons = filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': color})

    # crop_id 単位でグループ化（同名異作物を混在させない）
    def _crop_id_key(v):
        return v.get('crop_id')

    sorted_varieties = sorted(varieties, key=lambda v: (_crop_id_key(v) or 0))
    grouped = [(k, [item for item in g]) for k, g in groupby(sorted_varieties, key=_crop_id_key)]
    # 品種数の多い順（stable sort で同件数は元順序を維持）
    grouped.sort(key=lambda kv: len(kv[1]), reverse=True)

    return render_template('varieties/list.html',
                           varieties=varieties,
                           grouped_varieties=grouped,
                           active_variety_ids=active_variety_ids,
                           filter_types=filter_types,
                           filter_type_icons=filter_type_icons)


@bp.route('/<int:variety_id>')
def detail(variety_id):
    """品種詳細"""
    variety = Variety.get_by_id(variety_id)
    if not variety:
        flash('品種が見つかりません', 'danger')
        return redirect(url_for('varieties.list'))
    Variety.apply_inheritance(variety)

    related_plantings = Planting.get_by_variety(variety_id, status='active')
    related_harvests = Harvest.get_by_variety(variety_id, limit=10)
    related_diaries = DiaryEntry.get_by_variety(variety_id, limit=10)
    related_cookings = Cooking.get_by_variety(variety_id, limit=10)
    related_tasks = Task.get_incomplete_tasks_for_entity('variety', variety_id)
    prev_v, next_v = Variety.get_adjacent(variety_id)
    supplements = Supplement.get_by_entity('variety', variety_id)
    photo_pool_photos = PhotoPool.get_all()

    return render_template('varieties/detail.html',
                           variety=variety,
                           related_plantings=related_plantings,
                           related_harvests=related_harvests,
                           related_diaries=related_diaries,
                           related_cookings=related_cookings,
                           related_tasks=related_tasks,
                           prev_variety=prev_v,
                           next_variety=next_v,
                           supplements=supplements,
                           photo_pool_photos=photo_pool_photos)


def _build_crop_filter_data(crops):
    crop_filter_types = sorted(set(c['crop_type'] for c in crops if c.get('crop_type')))
    crop_filter_type_icons = {}
    for c in crops:
        t = c.get('crop_type')
        icon = c.get('icon_path')
        color = c.get('image_color') or '#4CAF50'
        if t and icon:
            icons = crop_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': color})
    return crop_filter_types, crop_filter_type_icons


@bp.route('/new')
def new():
    """品種登録フォーム"""
    preselected_crop_id = request.args.get('crop_id', type=int)
    photo_pool_id = request.args.get('photo_pool_id', type=int)
    preselected_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None
    crops = Crop.get_all()
    preselected_crop = next((c for c in crops if c['id'] == preselected_crop_id), None) if preselected_crop_id else None
    crop_filter_types, crop_filter_type_icons = _build_crop_filter_data(crops)
    photo_pool_photos = PhotoPool.get_all()
    return render_template('varieties/form.html', variety=None, action='create',
                           crops=crops,
                           preselected_crop=preselected_crop,
                           crop_icon_list=_get_crop_icon_list(),
                           preselected_photo=preselected_photo,
                           photo_pool_photos=photo_pool_photos,
                           crop_filter_types=crop_filter_types,
                           crop_filter_type_icons=crop_filter_type_icons,
                           selected_crop_ids=[str(preselected_crop_id)] if preselected_crop_id else [])


@bp.route('/create', methods=['POST'])
def create():
    """品種登録処理"""
    crop_id = request.form.get('crop_id', type=int)
    data = {
        'crop_id': crop_id,
        'name': request.form.get('name'),
        'notes': request.form.get('notes'),
        'icon_path': request.form.get('icon_path') or None,
        'image_color': request.form.get('image_color') or None,
    }

    if not data['crop_id'] or not data['name']:
        flash('親作物と品種名は必須です', 'danger')
        return redirect(url_for('varieties.new'))

    # 親作物の存在チェック
    if not Crop.get_by_id(data['crop_id']):
        flash('指定された作物が存在しません', 'danger')
        return redirect(url_for('varieties.new'))

    photo_pool_id = request.form.get('photo_pool_id', type=int)
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            data['image_path'] = copy_image(pool_photo['image_path'], 'varieties')
    elif 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'varieties')
        data['image_path'] = image_path

    try:
        variety_id = Variety.create(data)
        if photo_pool_id and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'variety', variety_id, data['image_path'])
        flash(f'品種「{data["name"]}」を登録しました', 'success')
        return redirect(url_for('varieties.detail', variety_id=variety_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('varieties.new'))


@bp.route('/<int:variety_id>/edit')
def edit(variety_id):
    """品種編集フォーム"""
    variety = Variety.get_by_id(variety_id)
    if not variety:
        flash('品種が見つかりません', 'danger')
        return redirect(url_for('varieties.list'))
    crops = Crop.get_all()
    crop_filter_types, crop_filter_type_icons = _build_crop_filter_data(crops)
    photo_pool_photos = PhotoPool.get_all()
    return render_template('varieties/form.html', variety=variety, action='update',
                           crops=crops,
                           preselected_crop=None,
                           crop_icon_list=_get_crop_icon_list(),
                           photo_pool_photos=photo_pool_photos,
                           crop_filter_types=crop_filter_types,
                           crop_filter_type_icons=crop_filter_type_icons,
                           selected_crop_ids=[str(variety['crop_id'])] if variety.get('crop_id') else [])


@bp.route('/<int:variety_id>/update', methods=['POST'])
def update(variety_id):
    """品種更新処理"""
    variety = Variety.get_by_id(variety_id)
    if not variety:
        flash('品種が見つかりません', 'danger')
        return redirect(url_for('varieties.list'))

    crop_id = request.form.get('crop_id', type=int)
    data = {
        'crop_id': crop_id,
        'name': request.form.get('name'),
        'notes': request.form.get('notes'),
        'image_path': variety.get('image_path'),
        'icon_path': request.form.get('icon_path') or None,
        'image_color': request.form.get('image_color') or None,
    }

    if not data['crop_id'] or not data['name']:
        flash('親作物と品種名は必須です', 'danger')
        return redirect(url_for('varieties.edit', variety_id=variety_id))

    if not Crop.get_by_id(data['crop_id']):
        flash('指定された作物が存在しません', 'danger')
        return redirect(url_for('varieties.edit', variety_id=variety_id))

    photo_pool_id = request.form.get('photo_pool_id', type=int)
    replaced_from_pool = False
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            if variety.get('image_path'):
                delete_image(variety['image_path'])
            data['image_path'] = copy_image(pool_photo['image_path'], 'varieties')
            replaced_from_pool = True
    elif 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            if variety.get('image_path'):
                delete_image(variety['image_path'])
            image_path = save_image(image, 'varieties')
            data['image_path'] = image_path

    if request.form.get('delete_image') == '1':
        if variety.get('image_path'):
            delete_image(variety['image_path'])
        data['image_path'] = None

    try:
        Variety.update(variety_id, data)
        if replaced_from_pool and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'variety', variety_id, data['image_path'])
        flash(f'品種「{data["name"]}」を更新しました', 'success')
        return redirect(url_for('varieties.detail', variety_id=variety_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('varieties.edit', variety_id=variety_id))


@bp.route('/<int:variety_id>/delete', methods=['POST'])
def delete(variety_id):
    """品種削除処理（plantings.variety_id は FK で SET NULL）"""
    variety = Variety.get_by_id(variety_id)
    if not variety:
        flash('品種が見つかりません', 'danger')
        return redirect(url_for('varieties.list'))

    parent_crop_id = variety['crop_id']
    try:
        supplement_images = Supplement.delete_by_entity('variety', variety_id)
        for img_path in supplement_images:
            delete_image(img_path)
        if variety.get('image_path'):
            delete_image(variety['image_path'])
        Variety.delete(variety_id)
        flash(f'品種「{variety["name"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('crops.detail', crop_id=parent_crop_id))
