from datetime import date
from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.cooking import Cooking
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.planting import Planting
from app.models.harvest import Harvest
from app.models.supplement import Supplement
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image, copy_image

bp = Blueprint('cooking', __name__, url_prefix='/cooking')


@bp.route('/')
def list():
    """料理一覧"""
    keyword = request.args.get('keyword', '')
    category = request.args.get('category', '')

    if keyword or category:
        items = Cooking.search(keyword=keyword or None, category=category or None)
    else:
        items = Cooking.get_all()

    categories = Cooking.get_categories()

    def _ym_key(e):
        d = e.get('cooked_date')
        return str(d)[:7] if d else ''

    grouped_items = [(k, [item for item in g]) for k, g in groupby(items, key=_ym_key)]

    return render_template('cooking/list.html',
                           items=items,
                           grouped_items=grouped_items,
                           keyword=keyword,
                           category=category,
                           categories=categories)


@bp.route('/<int:cooking_id>')
def detail(cooking_id):
    """料理詳細"""
    item = Cooking.get_by_id(cooking_id)
    if not item:
        flash('料理が見つかりません', 'danger')
        return redirect(url_for('cooking.list'))

    relations = Cooking.get_relations(cooking_id)
    prev_item, next_item = Cooking.get_adjacent(cooking_id)
    supplements = Supplement.get_by_entity('cooking', cooking_id)
    photo_pool_photos = PhotoPool.get_all()

    return render_template('cooking/detail.html',
                           item=item,
                           relations=relations,
                           prev_item=prev_item,
                           next_item=next_item,
                           supplements=supplements,
                           photo_pool_photos=photo_pool_photos)


@bp.route('/new')
def new():
    """料理登録フォーム"""
    crops = Crop.get_all()
    varieties = Variety.get_all()
    for v in varieties:
        Variety.apply_inheritance(v)
    active_plantings = Planting.get_all_with_stats(status='active')
    harvests = Harvest.get_all()

    today = date.today().isoformat()
    categories = Cooking.get_categories()

    photo_pool_id = request.args.get('photo_pool_id', type=int)
    preselected_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None

    filter_data = _build_filter_data(crops, varieties, active_plantings, harvests)
    sorted_crops = filter_data.pop('modal_sorted_crops')

    return render_template('cooking/form.html',
                           item=None,
                           action='create',
                           crops=sorted_crops,
                           varieties=varieties,
                           active_plantings=active_plantings,
                           harvests=harvests,
                           selected_relations=None,
                           today=today,
                           categories=categories,
                           preselected_photo=preselected_photo,
                           photo_pool_photos=PhotoPool.get_all(),
                           **filter_data)


@bp.route('/create', methods=['POST'])
def create():
    """料理登録処理"""
    data = {
        'title': request.form.get('title'),
        'category': request.form.get('category') or None,
        'notes': request.form.get('notes'),
        'cooked_date': request.form.get('cooked_date'),
    }

    if not data['title'] or not data['cooked_date']:
        flash('タイトルと調理日は必須です', 'danger')
        return redirect(url_for('cooking.new'))

    photo_pool_id = request.form.get('photo_pool_id', type=int)
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            data['image_path'] = copy_image(pool_photo['image_path'], 'cooking')
    elif 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'cooking')
        data['image_path'] = image_path

    try:
        cooking_id = Cooking.create(data)
        if photo_pool_id and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'cooking', cooking_id, data['image_path'])

        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
            'variety_ids': request.form.getlist('variety_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids'),
            'harvest_ids': request.form.getlist('harvest_ids')
        }
        Cooking.save_relations(cooking_id, relations)

        flash(f'料理「{data["title"]}」を登録しました', 'success')
        return redirect(url_for('cooking.detail', cooking_id=cooking_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('cooking.new'))


@bp.route('/<int:cooking_id>/edit')
def edit(cooking_id):
    """料理編集フォーム"""
    item = Cooking.get_by_id(cooking_id)
    if not item:
        flash('料理が見つかりません', 'danger')
        return redirect(url_for('cooking.list'))

    crops = Crop.get_all()
    varieties = Variety.get_all()
    for v in varieties:
        Variety.apply_inheritance(v)
    active_plantings = Planting.get_all_with_stats(status='active')
    harvests = Harvest.get_all()
    relations = Cooking.get_relations(cooking_id)
    categories = Cooking.get_categories()

    selected_relations = {
        'crop_ids': [str(r['crop_id']) for r in relations['crops']],
        'variety_ids': [str(r['variety_id']) for r in relations['varieties']],
        'location_crop_ids': [str(r['location_crop_id']) for r in relations['location_crops']],
        'harvest_ids': [str(r['harvest_id']) for r in relations['harvests']]
    }

    filter_data = _build_filter_data(crops, varieties, active_plantings, harvests)
    sorted_crops = filter_data.pop('modal_sorted_crops')

    return render_template('cooking/form.html',
                           item=item,
                           action='update',
                           crops=sorted_crops,
                           varieties=varieties,
                           active_plantings=active_plantings,
                           harvests=harvests,
                           selected_relations=selected_relations,
                           selected_crop_ids=selected_relations['crop_ids'],
                           selected_variety_ids=selected_relations['variety_ids'],
                           selected_location_crop_ids=selected_relations['location_crop_ids'],
                           selected_harvest_ids=selected_relations['harvest_ids'],
                           categories=categories,
                           photo_pool_photos=PhotoPool.get_all(),
                           **filter_data)


@bp.route('/<int:cooking_id>/update', methods=['POST'])
def update(cooking_id):
    """料理更新処理"""
    item = Cooking.get_by_id(cooking_id)
    if not item:
        flash('料理が見つかりません', 'danger')
        return redirect(url_for('cooking.list'))

    data = {
        'title': request.form.get('title'),
        'category': request.form.get('category') or None,
        'notes': request.form.get('notes'),
        'cooked_date': request.form.get('cooked_date'),
        'image_path': item.get('image_path')
    }

    if not data['title'] or not data['cooked_date']:
        flash('タイトルと調理日は必須です', 'danger')
        return redirect(url_for('cooking.edit', cooking_id=cooking_id))

    photo_pool_id = request.form.get('photo_pool_id', type=int)
    replaced_from_pool = False
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            if item.get('image_path'):
                delete_image(item['image_path'])
            data['image_path'] = copy_image(pool_photo['image_path'], 'cooking')
            replaced_from_pool = True
    elif 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            if item.get('image_path'):
                delete_image(item['image_path'])
            data['image_path'] = save_image(image, 'cooking')

    if request.form.get('delete_image') == '1':
        if item.get('image_path'):
            delete_image(item['image_path'])
        data['image_path'] = None

    try:
        Cooking.update(cooking_id, data)
        if replaced_from_pool and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'cooking', cooking_id, data['image_path'])

        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
            'variety_ids': request.form.getlist('variety_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids'),
            'harvest_ids': request.form.getlist('harvest_ids')
        }
        Cooking.save_relations(cooking_id, relations)

        flash(f'料理「{data["title"]}」を更新しました', 'success')
        return redirect(url_for('cooking.detail', cooking_id=cooking_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('cooking.edit', cooking_id=cooking_id))


@bp.route('/<int:cooking_id>/delete', methods=['POST'])
def delete(cooking_id):
    """料理削除処理"""
    item = Cooking.get_by_id(cooking_id)
    if not item:
        flash('料理が見つかりません', 'danger')
        return redirect(url_for('cooking.list'))

    try:
        supplement_images = Supplement.delete_by_entity('cooking', cooking_id)
        for img_path in supplement_images:
            delete_image(img_path)
        if item.get('image_path'):
            delete_image(item['image_path'])
        Cooking.delete(cooking_id)
        flash(f'料理「{item["title"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('cooking.list'))


def _build_filter_data(crops, varieties, active_plantings, harvests):
    """モーダル用フィルターデータを構築するヘルパー"""
    crop_filter_types = sorted(set(c['crop_type'] for c in crops if c['crop_type']))
    crop_filter_type_icons = {}
    for c in crops:
        t, icon = c['crop_type'], c.get('icon_path')
        if t and icon:
            icons = crop_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': c.get('image_color') or '#4CAF50'})

    variety_filter_types = sorted({v['crop_type'] for v in varieties if v.get('crop_type')})
    variety_filter_type_icons = {}
    for v in varieties:
        t = v.get('crop_type')
        icon = v.get('crop_icon_path')
        color = v.get('crop_image_color') or '#4CAF50'
        if t and icon:
            icons = variety_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': color})

    planting_filter_types = sorted(set(p['crop_type'] for p in active_plantings if p.get('crop_type')))
    planting_filter_type_icons = {}
    for p in active_plantings:
        t, icon = p.get('crop_type'), p.get('icon_path')
        if t and icon:
            icons = planting_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': p.get('image_color') or '#4CAF50'})
    planting_filter_locations = sorted(set(p['location_name'] for p in active_plantings if p.get('location_name')))

    harvest_filter_types = sorted(set(h['crop_type'] for h in harvests if h['crop_type']))
    harvest_filter_type_icons = {}
    for h in harvests:
        t, icon = h['crop_type'], h.get('icon_path')
        if t and icon:
            icons = harvest_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': h.get('image_color') or '#4CAF50'})
    harvest_filter_locations = sorted(set(h['location_name'] for h in harvests if h.get('location_name')))

    modal_sorted_crops = sorted(crops, key=lambda c: c.get('name') or '')

    _v_sorted = sorted(varieties, key=lambda v: v.get('crop_id') or 0)
    grouped_varieties = [(k, [item for item in g]) for k, g in groupby(_v_sorted, key=lambda v: v.get('crop_id'))]
    grouped_varieties.sort(key=lambda kv: len(kv[1]), reverse=True)

    def _ym_p(p):
        d = p.get('planted_date')
        return str(d)[:7] if d else ''
    grouped_plantings = [(k, [item for item in g]) for k, g in groupby(active_plantings, key=_ym_p)]

    def _ym_h(h):
        d = h.get('harvest_date')
        return str(d)[:7] if d else ''
    grouped_harvests = [(k, [item for item in g]) for k, g in groupby(harvests, key=_ym_h)]

    return {
        'crop_filter_types': crop_filter_types,
        'crop_filter_type_icons': crop_filter_type_icons,
        'variety_filter_types': variety_filter_types,
        'variety_filter_type_icons': variety_filter_type_icons,
        'planting_filter_types': planting_filter_types,
        'planting_filter_type_icons': planting_filter_type_icons,
        'planting_filter_locations': planting_filter_locations,
        'harvest_filter_types': harvest_filter_types,
        'harvest_filter_type_icons': harvest_filter_type_icons,
        'harvest_filter_locations': harvest_filter_locations,
        'modal_sorted_crops': modal_sorted_crops,
        'grouped_varieties': grouped_varieties,
        'grouped_plantings': grouped_plantings,
        'grouped_harvests': grouped_harvests,
    }
