"""写真プールの振り分け画面（選んだ写真を1枚ずつ登録し、保存したら次の写真へ進む）

状態は URL のパラメーターだけで持つ: ids=写真IDの並び, pos=今の位置, done=登録済みの写真ID, kind=登録する種類
"""
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.datastructures import MultiDict

from app.models.cooking import Cooking
from app.models.crop import Crop
from app.models.diary import DiaryEntry
from app.models.location import Location
from app.models.photo_pool import PhotoPool
from app.models.variety import Variety
from app.routes.photo_pool_routes import usage_url
from app.utils.upload import copy_image, delete_image

bp = Blueprint('photo_sort', __name__, url_prefix='/photo_pool/sort')

# 登録できる種類（表示順）
KINDS = [
    ('planting_record', '栽培記録'),
    ('harvest', '収穫'),
    ('cooking', '料理'),
    ('diary', '日記'),
    ('planting', '植え付け＋栽培記録'),
    ('crop', '作物'),
    ('variety', '品種'),
    ('location', '場所'),
]
KIND_LABELS = dict(KINDS)


def _parse_ids(value):
    ids = []
    for part in (value or '').split(','):
        part = part.strip()
        if part.isdigit() and int(part) not in ids:
            ids.append(int(part))
    return ids


def sort_url(ids, pos, done, kind=None):
    """振り分け画面の URL（カンマはエスケープしない）"""
    query = f'ids={",".join(str(i) for i in ids)}&pos={pos}'
    done_ids = [i for i in ids if i in done]
    if done_ids:
        query += f'&done={",".join(str(i) for i in done_ids)}'
    if kind:
        query += f'&kind={kind}'
    return f'{url_for("photo_sort.index")}?{query}'


def default_date(photo):
    """日付欄の初期値: 撮影日、無ければ今日"""
    taken_at = photo.get('taken_at')
    if taken_at:
        return taken_at.date().isoformat()
    return date.today().isoformat()


def _ordered_photos(ids):
    """存在する写真だけを撮影日時の古い順に（撮影日時が無いものは登録順で後ろ）"""
    photos = [p for p in (PhotoPool.get_by_id(i) for i in ids) if p]
    return sorted(photos, key=lambda p: (p['taken_at'] is None, p['taken_at'] or p['created_at'], p['id']))


def _finish(done_count):
    if done_count:
        flash(f'{done_count}枚の写真を登録しました', 'success')
    else:
        flash('振り分けを終えました', 'info')
    return redirect(url_for('photo_pool.index'))


def _kind_context(kind):
    """種類ごとの入力欄に要るデータ"""
    from app.routes.crop_routes import _get_crop_icon_list
    if kind == 'crop':
        return {'crop_icon_list': _get_crop_icon_list()}
    if kind == 'variety':
        return {'crop_icon_list': _get_crop_icon_list(),
                'crops': sorted(Crop.get_all(), key=lambda c: c.get('name') or '')}
    if kind in ('cooking', 'diary'):
        return _relation_context(include_locations=(kind == 'diary'))
    return {}


def _relation_context(include_locations):
    """関連付けモーダル（_*_select_multi_modal.html）用のデータ。日記の登録画面と同じ組み立て方"""
    from app.models.harvest import Harvest
    from app.models.planting import Planting
    from app.routes.diary_routes import _build_filter_data
    crops = Crop.get_all()
    varieties = [Variety.apply_inheritance(v) for v in Variety.get_all()]
    locations = Location.get_all()
    active_plantings = Planting.get_all_with_stats(status='active')
    harvests = Harvest.get_all()
    data = _build_filter_data(crops, varieties, locations, active_plantings, harvests)
    data['crops'] = data.pop('modal_sorted_crops')
    data.update(varieties=varieties, locations=locations, active_plantings=active_plantings,
                harvests=harvests, categories=Cooking.get_categories(),
                include_locations=include_locations)
    return data


def render_sort_page(ids, pos, done, kind, form_values=None):
    """振り分け画面を描画する（保存エラー時の再表示にも使う）"""
    photos = _ordered_photos(ids)
    ids = [p['id'] for p in photos]
    done = {i for i in done if i in ids}
    if pos >= len(photos):
        return _finish(len(done))
    photo = photos[pos]
    if kind not in KIND_LABELS:
        kind = None
    links = PhotoPool.get_usage_links([photo['id']])[photo['id']]
    return render_template('photo_sort/index.html',
                           photos=photos,
                           photo=photo,
                           ids=ids,
                           pos=pos,
                           done=done,
                           kind=kind,
                           kinds=KINDS,
                           kind_label=KIND_LABELS.get(kind),
                           usage_links=links,
                           usage_url=usage_url,
                           skip_url=sort_url(ids, pos + 1, done),
                           sort_url=sort_url,
                           default_date=default_date(photo),
                           form_values=form_values if form_values is not None else MultiDict(),
                           **_kind_context(kind))


@bp.route('/')
def index():
    """振り分け画面"""
    ids = _parse_ids(request.args.get('ids'))
    pos = max(request.args.get('pos', 0, type=int), 0)
    done = set(_parse_ids(request.args.get('done')))
    return render_sort_page(ids, pos, done, request.args.get('kind'))


class _FormError(Exception):
    """入力エラー（利用者向けの日本語メッセージ）"""


def _create_with_photo(photo, folder, entity_type, create):
    """写真をコピーして create(image_path) -> id を呼び、使用記録を残す。失敗したらコピーを消す"""
    image_path = copy_image(photo['image_path'], folder)
    try:
        entity_id = create(image_path)
    except Exception:
        delete_image(image_path)
        raise
    if image_path:
        PhotoPool.record_usage(photo['id'], entity_type, entity_id, image_path)
    return entity_id


def _save_crop(form, photo):
    data = {
        'name': form.get('name'),
        'crop_type': form.get('crop_type'),
        'notes': form.get('notes'),
        'icon_path': form.get('icon_path') or None,
        'image_color': form.get('image_color') or '#4CAF50',
    }
    if not data['name'] or not data['crop_type']:
        raise _FormError('作物名と作物種類は必須です')
    _create_with_photo(photo, 'crops', 'crop', lambda path: Crop.create({**data, 'image_path': path}))
    return f'作物「{data["name"]}」を登録しました'


def _save_variety(form, photo):
    data = {
        'crop_id': form.get('crop_id', type=int),
        'name': form.get('name'),
        'notes': form.get('notes'),
        'icon_path': form.get('icon_path') or None,
        # 「親作物の色を使う」なら未設定（親から継承）
        'image_color': None if form.get('use_parent_color') else (form.get('image_color') or None),
    }
    if not data['crop_id'] or not data['name']:
        raise _FormError('親作物と品種名は必須です')
    if not Crop.get_by_id(data['crop_id']):
        raise _FormError('指定された作物が存在しません')
    _create_with_photo(photo, 'varieties', 'variety', lambda path: Variety.create({**data, 'image_path': path}))
    return f'品種「{data["name"]}」を登録しました'


def _save_location(form, photo):
    data = {
        'name': form.get('name'),
        'location_type': form.get('location_type'),
        'area_size': form.get('area_size'),
        'sun_exposure': form.get('sun_exposure'),
        'notes': form.get('notes'),
        'bg_image': None,
    }
    if not data['name'] or not data['location_type']:
        raise _FormError('場所名と場所種類は必須です')
    _create_with_photo(photo, 'locations', 'location', lambda path: Location.create({**data, 'image_path': path}))
    return f'場所「{data["name"]}」を登録しました'


def _save_cooking(form, photo):
    data = {
        'title': form.get('title'),
        'category': form.get('category') or None,
        'notes': form.get('notes'),
        'cooked_date': form.get('cooked_date'),
    }
    if not data['title'] or not data['cooked_date']:
        raise _FormError('タイトルと調理日は必須です')
    cooking_id = _create_with_photo(photo, 'cooking', 'cooking',
                                    lambda path: Cooking.create({**data, 'image_path': path}))
    Cooking.save_relations(cooking_id, {
        'crop_ids': form.getlist('crop_ids'),
        'variety_ids': form.getlist('variety_ids'),
        'location_crop_ids': form.getlist('location_crop_ids'),
        'harvest_ids': form.getlist('harvest_ids'),
    })
    return f'料理「{data["title"]}」を登録しました'


def _save_diary(form, photo):
    data = {
        'title': form.get('title'),
        'content': form.get('content'),
        'entry_date': form.get('entry_date'),
        'weather': form.get('weather'),
        'status': 'published',
    }
    if not data['title'] or not data['entry_date']:
        raise _FormError('タイトルと日付は必須です')
    diary_id = _create_with_photo(photo, 'diary', 'diary',
                                  lambda path: DiaryEntry.create({**data, 'image_path': path}))
    DiaryEntry.save_relations(diary_id, {
        'crop_ids': form.getlist('crop_ids'),
        'variety_ids': form.getlist('variety_ids'),
        'location_ids': form.getlist('location_ids'),
        'location_crop_ids': form.getlist('location_crop_ids'),
        'harvest_ids': form.getlist('harvest_ids'),
    })
    return f'日記「{data["title"]}」を登録しました'


_SAVERS = {
    'crop': _save_crop,
    'variety': _save_variety,
    'location': _save_location,
    'cooking': _save_cooking,
    'diary': _save_diary,
}


@bp.route('/save', methods=['POST'])
def save():
    """1枚の写真を選んだ種類で登録し、次の写真（action=stay なら同じ写真）へ"""
    form = request.form
    ids = _parse_ids(form.get('ids'))
    pos = max(form.get('pos', 0, type=int), 0)
    done = set(_parse_ids(form.get('done')))
    kind = form.get('kind')

    photo = PhotoPool.get_by_id(form.get('photo_id', type=int) or 0)
    if not photo:
        flash('写真が見つかりません', 'danger')
        return redirect(sort_url(ids, pos, done))
    saver = _SAVERS.get(kind)
    if not saver:
        flash('種類を選んでください', 'danger')
        return render_sort_page(ids, pos, done, None, form)

    try:
        message = saver(form, photo)
    except _FormError as e:
        flash(str(e), 'danger')
        return render_sort_page(ids, pos, done, kind, form)
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return render_sort_page(ids, pos, done, kind, form)

    flash(message, 'success')
    done.add(photo['id'])
    next_pos = pos if form.get('action') == 'stay' else pos + 1
    return redirect(sort_url(ids, next_pos, done))
