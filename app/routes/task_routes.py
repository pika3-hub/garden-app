from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.task import Task
from app.models.crop import Crop
from app.models.location import Location

bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@bp.route('/')
def list():
    """タスク一覧"""
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if keyword or status or date_from or date_to:
        tasks = Task.search(
            keyword=keyword if keyword else None,
            status=status if status else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None
        )
    else:
        tasks = Task.get_all()

    return render_template('tasks/list.html',
                          tasks=tasks,
                          keyword=keyword,
                          status=status,
                          date_from=date_from,
                          date_to=date_to,
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

    return render_template('tasks/detail.html',
                          task=task,
                          relations=relations,
                          today=date.today(),
                          Task=Task)


@bp.route('/new')
def new():
    """タスク登録フォーム"""
    crops = Crop.get_all()
    locations = Location.get_all()
    location_crops = _get_active_location_crops()

    today = date.today().isoformat()

    return render_template('tasks/form.html',
                          task=None,
                          action='create',
                          crops=crops,
                          locations=locations,
                          location_crops=location_crops,
                          selected_relations=None,
                          today=today,
                          Task=Task)


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
    location_crops = _get_active_location_crops()
    relations = Task.get_relations(task_id)

    # 選択済みのIDを抽出
    selected_relations = {
        'crop_ids': [str(r['crop_id']) for r in relations['crops']],
        'location_ids': [str(r['location_id']) for r in relations['locations']],
        'location_crop_ids': [str(r['location_crop_id']) for r in relations['location_crops']]
    }

    return render_template('tasks/form.html',
                          task=task,
                          action='update',
                          crops=crops,
                          locations=locations,
                          location_crops=location_crops,
                          selected_relations=selected_relations,
                          Task=Task)


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
        Task.delete(task_id)
        flash(f'タスク「{task["title"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('tasks.list'))


def _get_active_location_crops():
    """栽培中の植え付け場所を取得するヘルパー"""
    from app.database import get_db
    db = get_db()
    location_crops = db.execute(
        '''SELECT lc.id, lc.planted_date,
                  c.name as crop_name, l.name as location_name
           FROM location_crops lc
           JOIN crops c ON lc.crop_id = c.id
           JOIN locations l ON lc.location_id = l.id
           WHERE lc.status = 'active'
           ORDER BY lc.planted_date DESC'''
    ).fetchall()
    return [dict(lc) for lc in location_crops]
