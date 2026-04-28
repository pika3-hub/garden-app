from datetime import date
from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.diary import DiaryEntry
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.location import Location
from app.models.planting import Planting
from app.models.harvest import Harvest
from app.models.supplement import Supplement
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image, copy_image

bp = Blueprint('diary', __name__, url_prefix='/diary')


@bp.route('/')
def list():
    """日記一覧"""
    keyword = request.args.get('keyword', '')

    if keyword:
        entries = DiaryEntry.search(keyword=keyword)
    else:
        entries = DiaryEntry.get_all()

    years = sorted(set(str(e['entry_date'])[:4] for e in entries if e.get('entry_date')), reverse=True)

    def _ym_key(e):
        d = e.get('entry_date')
        return str(d)[:7] if d else ''

    grouped_entries = [(k, [item for item in g]) for k, g in groupby(entries, key=_ym_key)]

    return render_template('diary/list.html',
                          entries=entries,
                          grouped_entries=grouped_entries,
                          keyword=keyword,
                          years=years)


@bp.route('/<int:diary_id>')
def detail(diary_id):
    """日記詳細"""
    entry = DiaryEntry.get_by_id(diary_id)
    if not entry:
        flash('日記が見つかりません', 'danger')
        return redirect(url_for('diary.list'))

    relations = DiaryEntry.get_relations(diary_id)
    prev_entry, next_entry = DiaryEntry.get_adjacent(diary_id)
    supplements = Supplement.get_by_entity('diary', diary_id)
    photo_pool_photos = PhotoPool.get_all()

    return render_template('diary/detail.html',
                          entry=entry,
                          relations=relations,
                          prev_entry=prev_entry,
                          next_entry=next_entry,
                          supplements=supplements,
                          photo_pool_photos=photo_pool_photos)


@bp.route('/new')
def new():
    """日記登録フォーム"""
    crops = Crop.get_all()
    varieties = Variety.get_all()
    for v in varieties:
        Variety.apply_inheritance(v)
    locations = Location.get_all()
    active_plantings = Planting.get_all_with_stats(status='active')
    harvests = Harvest.get_all()

    today = date.today().isoformat()

    photo_pool_id = request.args.get('photo_pool_id', type=int)
    preselected_photo = PhotoPool.get_by_id(photo_pool_id) if photo_pool_id else None

    filter_data = _build_filter_data(crops, varieties, locations, active_plantings, harvests)
    sorted_crops = filter_data.pop('modal_sorted_crops')

    return render_template('diary/form.html',
                          entry=None,
                          action='create',
                          crops=sorted_crops,
                          varieties=varieties,
                          locations=locations,
                          active_plantings=active_plantings,
                          harvests=harvests,
                          selected_relations=None,
                          today=today,
                          preselected_photo=preselected_photo,
                          photo_pool_photos=PhotoPool.get_all(),
                          **filter_data)


@bp.route('/create', methods=['POST'])
def create():
    """日記登録処理"""
    data = {
        'title': request.form.get('title'),
        'content': request.form.get('content'),
        'entry_date': request.form.get('entry_date'),
        'weather': request.form.get('weather'),
        'status': request.form.get('status', 'published')
    }

    # バリデーション
    if not data['title'] or not data['entry_date']:
        flash('タイトルと日付は必須です', 'danger')
        return redirect(url_for('diary.new'))

    # 画像アップロード処理（写真プール優先）
    photo_pool_id = request.form.get('photo_pool_id', type=int)
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            data['image_path'] = copy_image(pool_photo['image_path'], 'diary')
    elif 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'diary')
        data['image_path'] = image_path

    try:
        diary_id = DiaryEntry.create(data)
        if photo_pool_id and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'diary', diary_id, data['image_path'])

        # 関連を保存
        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
            'variety_ids': request.form.getlist('variety_ids'),
            'location_ids': request.form.getlist('location_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids'),
            'harvest_ids': request.form.getlist('harvest_ids')
        }
        DiaryEntry.save_relations(diary_id, relations)

        flash(f'日記「{data["title"]}」を登録しました', 'success')
        return redirect(url_for('diary.detail', diary_id=diary_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('diary.new'))


@bp.route('/<int:diary_id>/edit')
def edit(diary_id):
    """日記編集フォーム"""
    entry = DiaryEntry.get_by_id(diary_id)
    if not entry:
        flash('日記が見つかりません', 'danger')
        return redirect(url_for('diary.list'))

    crops = Crop.get_all()
    varieties = Variety.get_all()
    for v in varieties:
        Variety.apply_inheritance(v)
    locations = Location.get_all()
    active_plantings = Planting.get_all_with_stats(status='active')
    harvests = Harvest.get_all()
    relations = DiaryEntry.get_relations(diary_id)

    # 選択済みのIDを抽出
    selected_relations = {
        'crop_ids': [str(r['crop_id']) for r in relations['crops']],
        'variety_ids': [str(r['variety_id']) for r in relations['varieties']],
        'location_ids': [str(r['location_id']) for r in relations['locations']],
        'location_crop_ids': [str(r['location_crop_id']) for r in relations['location_crops']],
        'harvest_ids': [str(r['harvest_id']) for r in relations['harvests']]
    }

    filter_data = _build_filter_data(crops, varieties, locations, active_plantings, harvests)
    sorted_crops = filter_data.pop('modal_sorted_crops')

    return render_template('diary/form.html',
                          entry=entry,
                          action='update',
                          crops=sorted_crops,
                          varieties=varieties,
                          locations=locations,
                          active_plantings=active_plantings,
                          harvests=harvests,
                          selected_relations=selected_relations,
                          selected_crop_ids=selected_relations['crop_ids'],
                          selected_variety_ids=selected_relations['variety_ids'],
                          selected_location_ids=selected_relations['location_ids'],
                          selected_location_crop_ids=selected_relations['location_crop_ids'],
                          selected_harvest_ids=selected_relations['harvest_ids'],
                          photo_pool_photos=PhotoPool.get_all(),
                          **filter_data)


@bp.route('/<int:diary_id>/update', methods=['POST'])
def update(diary_id):
    """日記更新処理"""
    entry = DiaryEntry.get_by_id(diary_id)
    if not entry:
        flash('日記が見つかりません', 'danger')
        return redirect(url_for('diary.list'))

    data = {
        'title': request.form.get('title'),
        'content': request.form.get('content'),
        'entry_date': request.form.get('entry_date'),
        'weather': request.form.get('weather'),
        'status': request.form.get('status', 'published'),
        'image_path': entry.get('image_path')  # 既存の画像パスを保持
    }

    # バリデーション
    if not data['title'] or not data['entry_date']:
        flash('タイトルと日付は必須です', 'danger')
        return redirect(url_for('diary.edit', diary_id=diary_id))

    # 画像アップロード処理（写真プール優先）
    photo_pool_id = request.form.get('photo_pool_id', type=int)
    replaced_from_pool = False
    if photo_pool_id:
        pool_photo = PhotoPool.get_by_id(photo_pool_id)
        if pool_photo:
            if entry.get('image_path'):
                delete_image(entry['image_path'])
            data['image_path'] = copy_image(pool_photo['image_path'], 'diary')
            replaced_from_pool = True
    elif 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            if entry.get('image_path'):
                delete_image(entry['image_path'])
            image_path = save_image(image, 'diary')
            data['image_path'] = image_path

    # 画像削除チェック
    if request.form.get('delete_image') == '1':
        if entry.get('image_path'):
            delete_image(entry['image_path'])
        data['image_path'] = None

    try:
        DiaryEntry.update(diary_id, data)
        if replaced_from_pool and data.get('image_path'):
            PhotoPool.record_usage(photo_pool_id, 'diary', diary_id, data['image_path'])

        # 関連を保存
        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
            'variety_ids': request.form.getlist('variety_ids'),
            'location_ids': request.form.getlist('location_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids'),
            'harvest_ids': request.form.getlist('harvest_ids')
        }
        DiaryEntry.save_relations(diary_id, relations)

        flash(f'日記「{data["title"]}」を更新しました', 'success')
        return redirect(url_for('diary.detail', diary_id=diary_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('diary.edit', diary_id=diary_id))


@bp.route('/<int:diary_id>/delete', methods=['POST'])
def delete(diary_id):
    """日記削除処理"""
    entry = DiaryEntry.get_by_id(diary_id)
    if not entry:
        flash('日記が見つかりません', 'danger')
        return redirect(url_for('diary.list'))

    try:
        # 補足情報の画像を削除
        supplement_images = Supplement.delete_by_entity('diary', diary_id)
        for img_path in supplement_images:
            delete_image(img_path)
        # 画像を削除
        if entry.get('image_path'):
            delete_image(entry['image_path'])
        DiaryEntry.delete(diary_id)
        flash(f'日記「{entry["title"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('diary.list'))


def _build_filter_data(crops, varieties, locations, active_plantings, harvests):
    """モーダル用フィルターデータを構築するヘルパー"""
    # 作物フィルター
    crop_filter_types = sorted(set(c['crop_type'] for c in crops if c['crop_type']))
    crop_filter_type_icons = {}
    for c in crops:
        t, icon = c['crop_type'], c.get('icon_path')
        if t and icon:
            icons = crop_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': c.get('image_color') or '#4CAF50'})

    # 品種フィルター（親作物の crop_type、品種一覧と同じ規約）
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

    # 場所フィルター
    location_filter_types = sorted(set(l['location_type'] for l in locations if l['location_type']))

    # 植え付けフィルター
    planting_filter_types = sorted(set(p['crop_type'] for p in active_plantings if p.get('crop_type')))
    planting_filter_type_icons = {}
    for p in active_plantings:
        t, icon = p.get('crop_type'), p.get('icon_path')
        if t and icon:
            icons = planting_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': p.get('image_color') or '#4CAF50'})
    planting_filter_locations = sorted(set(p['location_name'] for p in active_plantings if p.get('location_name')))

    # 収穫フィルター
    harvest_filter_types = sorted(set(h['crop_type'] for h in harvests if h['crop_type']))
    harvest_filter_type_icons = {}
    for h in harvests:
        t, icon = h['crop_type'], h.get('icon_path')
        if t and icon:
            icons = harvest_filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': h.get('image_color') or '#4CAF50'})
    harvest_filter_locations = sorted(set(h['location_name'] for h in harvests if h.get('location_name')))

    # モーダル表示用グルーピング
    modal_sorted_crops = sorted(crops, key=lambda c: c.get('name') or '')

    _v_sorted = sorted(varieties, key=lambda v: v.get('crop_id') or 0)
    grouped_varieties = [(k, [item for item in g]) for k, g in groupby(_v_sorted, key=lambda v: v.get('crop_id'))]
    grouped_varieties.sort(key=lambda kv: len(kv[1]), reverse=True)

    _l_sorted = sorted(locations, key=lambda l: l.get('location_type') or '')
    grouped_locations = [(k, [item for item in g]) for k, g in groupby(_l_sorted, key=lambda l: l.get('location_type') or '')]
    grouped_locations.sort(key=lambda kv: len(kv[1]), reverse=True)
    _multi = [kv for kv in grouped_locations if len(kv[1]) > 1]
    _singles = [items[0] for _, items in grouped_locations if len(items) == 1]
    if _singles:
        _multi.append(('その他', _singles))
    grouped_locations = _multi

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
        'location_filter_types': location_filter_types,
        'planting_filter_types': planting_filter_types,
        'planting_filter_type_icons': planting_filter_type_icons,
        'planting_filter_locations': planting_filter_locations,
        'harvest_filter_types': harvest_filter_types,
        'harvest_filter_type_icons': harvest_filter_type_icons,
        'harvest_filter_locations': harvest_filter_locations,
        'modal_sorted_crops': modal_sorted_crops,
        'grouped_varieties': grouped_varieties,
        'grouped_locations': grouped_locations,
        'grouped_plantings': grouped_plantings,
        'grouped_harvests': grouped_harvests,
    }
