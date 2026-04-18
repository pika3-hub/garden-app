from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.task import Task
from app.models.crop import Crop
from app.models.location import Location
from app.models.planting import Planting
from app.models.supplement import Supplement
from app.models.photo_pool import PhotoPool
from app.utils.upload import delete_image

bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@bp.route('/')
def list():
    """タスク一覧"""
    keyword = request.args.get('keyword', '')

    if keyword:
        tasks = Task.search(keyword=keyword)
    else:
        tasks = Task.get_all()

    years = sorted(set(str(t['due_date'])[:4] for t in tasks if t.get('due_date')), reverse=True)
    filter_statuses = sorted(set(t['status'] for t in tasks if t.get('status')))

    return render_template('tasks/list.html',
                          tasks=tasks,
                          keyword=keyword,
                          filter_statuses=filter_statuses,
                          years=years,
                          today=date.today(),
                          Task=Task)


@bp.route('/<int:task_id>')
def detail(task_id):
    """タスク詳細"""
    task = Task.get_by_id(task_id)
    if not task:
        flash('タスクが見つかりません', 'danger')
        return redirect(url_for('tasks.list'))

    relations = Task.get_relations(task_id)
    prev_task, next_task = Task.get_adjacent(task_id)
    supplements = Supplement.get_by_entity('task', task_id)

    return render_template('tasks/detail.html',
                          task=task,
                          relations=relations,
                          today=date.today(),
                          Task=Task,
                          prev_task=prev_task,
                          next_task=next_task,
                          supplements=supplements,
                          photo_pool_photos=PhotoPool.get_all())


@bp.route('/new')
def new():
    """タスク登録フォーム"""
    crops = Crop.get_all()
    locations = Location.get_all()
    active_plantings = Planting.get_all_with_stats(status='active')

    today = date.today().isoformat()

    filter_data = _build_filter_data(crops, locations, active_plantings)

    return render_template('tasks/form.html',
                          task=None,
                          action='create',
                          crops=crops,
                          locations=locations,
                          active_plantings=active_plantings,
                          selected_relations=None,
                          today=today,
                          Task=Task,
                          **filter_data)


@bp.route('/create', methods=['POST'])
def create():
    """タスク登録処理"""
    data = {
        'title': request.form.get('title'),
        'description': request.form.get('description'),
        'due_date': request.form.get('due_date') or None,
        'status': request.form.get('status', Task.STATUS_PENDING)
    }

    # バリデーション
    if not data['title']:
        flash('タイトルは必須です', 'danger')
        return redirect(url_for('tasks.new'))

    try:
        task_id = Task.create(data)

        # 関連を保存
        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
            'location_ids': request.form.getlist('location_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids')
        }
        Task.save_relations(task_id, relations)

        flash(f'タスク「{data["title"]}」を登録しました', 'success')
        return redirect(url_for('tasks.detail', task_id=task_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('tasks.new'))


@bp.route('/<int:task_id>/edit')
def edit(task_id):
    """タスク編集フォーム"""
    task = Task.get_by_id(task_id)
    if not task:
        flash('タスクが見つかりません', 'danger')
        return redirect(url_for('tasks.list'))

    crops = Crop.get_all()
    locations = Location.get_all()
    active_plantings = Planting.get_all_with_stats(status='active')
    relations = Task.get_relations(task_id)

    # 選択済みのIDを抽出
    selected_relations = {
        'crop_ids': [str(r['crop_id']) for r in relations['crops']],
        'location_ids': [str(r['location_id']) for r in relations['locations']],
        'location_crop_ids': [str(r['location_crop_id']) for r in relations['location_crops']]
    }

    filter_data = _build_filter_data(crops, locations, active_plantings)

    return render_template('tasks/form.html',
                          task=task,
                          action='update',
                          crops=crops,
                          locations=locations,
                          active_plantings=active_plantings,
                          selected_relations=selected_relations,
                          selected_crop_ids=selected_relations['crop_ids'],
                          selected_location_ids=selected_relations['location_ids'],
                          selected_location_crop_ids=selected_relations['location_crop_ids'],
                          Task=Task,
                          **filter_data)


@bp.route('/<int:task_id>/update', methods=['POST'])
def update(task_id):
    """タスク更新処理"""
    task = Task.get_by_id(task_id)
    if not task:
        flash('タスクが見つかりません', 'danger')
        return redirect(url_for('tasks.list'))

    data = {
        'title': request.form.get('title'),
        'description': request.form.get('description'),
        'due_date': request.form.get('due_date') or None,
        'status': request.form.get('status', Task.STATUS_PENDING)
    }

    # バリデーション
    if not data['title']:
        flash('タイトルは必須です', 'danger')
        return redirect(url_for('tasks.edit', task_id=task_id))

    try:
        Task.update(task_id, data)

        # 関連を保存
        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
            'location_ids': request.form.getlist('location_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids')
        }
        Task.save_relations(task_id, relations)

        flash(f'タスク「{data["title"]}」を更新しました', 'success')
        return redirect(url_for('tasks.detail', task_id=task_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('tasks.edit', task_id=task_id))


@bp.route('/<int:task_id>/delete', methods=['POST'])
def delete(task_id):
    """タスク削除処理"""
    task = Task.get_by_id(task_id)
    if not task:
        flash('タスクが見つかりません', 'danger')
        return redirect(url_for('tasks.list'))

    try:
        # 補足情報の画像を削除
        supplement_images = Supplement.delete_by_entity('task', task_id)
        for img_path in supplement_images:
            delete_image(img_path)
        Task.delete(task_id)
        flash(f'タスク「{task["title"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('tasks.list'))


def _build_filter_data(crops, locations, active_plantings):
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

    return {
        'crop_filter_types': crop_filter_types,
        'crop_filter_type_icons': crop_filter_type_icons,
        'location_filter_types': location_filter_types,
        'planting_filter_types': planting_filter_types,
        'planting_filter_type_icons': planting_filter_type_icons,
        'planting_filter_locations': planting_filter_locations,
    }
