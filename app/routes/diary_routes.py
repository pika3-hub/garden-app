from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.diary import DiaryEntry
from app.models.crop import Crop
from app.models.location import Location
from app.models.location_crop import LocationCrop
from app.models.harvest import Harvest
from app.utils.upload import save_image, delete_image

bp = Blueprint('diary', __name__, url_prefix='/diary')


@bp.route('/')
def list():
    """日記一覧"""
    keyword = request.args.get('keyword', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if keyword or date_from or date_to:
        entries = DiaryEntry.search(
            keyword=keyword if keyword else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None
        )
    else:
        entries = DiaryEntry.get_all()

    return render_template('diary/list.html',
                          entries=entries,
                          keyword=keyword,
                          date_from=date_from,
                          date_to=date_to)


@bp.route('/<int:diary_id>')
def detail(diary_id):
    """日記詳細"""
    entry = DiaryEntry.get_by_id(diary_id)
    if not entry:
        flash('日記が見つかりません', 'danger')
        return redirect(url_for('diary.list'))

    relations = DiaryEntry.get_relations(diary_id)
    prev_entry, next_entry = DiaryEntry.get_adjacent(diary_id)

    return render_template('diary/detail.html',
                          entry=entry,
                          relations=relations,
                          prev_entry=prev_entry,
                          next_entry=next_entry)


@bp.route('/new')
def new():
    """日記登録フォーム"""
    crops = Crop.get_all()
    locations = Location.get_all()
    # 栽培中の植え付け場所を取得
    location_crops = _get_active_location_crops()
    # 収穫記録を取得
    harvests = Harvest.get_all()

    today = date.today().isoformat()

    return render_template('diary/form.html',
                          entry=None,
                          action='create',
                          crops=crops,
                          locations=locations,
                          location_crops=location_crops,
                          harvests=harvests,
                          selected_relations=None,
                          today=today)


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

    # 画像アップロード処理
    if 'image' in request.files:
        image = request.files['image']
        image_path = save_image(image, 'diary')
        data['image_path'] = image_path

    try:
        diary_id = DiaryEntry.create(data)

        # 関連を保存
        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
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
    locations = Location.get_all()
    location_crops = _get_active_location_crops()
    harvests = Harvest.get_all()
    relations = DiaryEntry.get_relations(diary_id)

    # 選択済みのIDを抽出
    selected_relations = {
        'crop_ids': [str(r['crop_id']) for r in relations['crops']],
        'location_ids': [str(r['location_id']) for r in relations['locations']],
        'location_crop_ids': [str(r['location_crop_id']) for r in relations['location_crops']],
        'harvest_ids': [str(r['harvest_id']) for r in relations['harvests']]
    }

    return render_template('diary/form.html',
                          entry=entry,
                          action='update',
                          crops=crops,
                          locations=locations,
                          location_crops=location_crops,
                          harvests=harvests,
                          selected_relations=selected_relations)


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

    # 画像アップロード処理
    if 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            # 古い画像を削除
            if entry.get('image_path'):
                delete_image(entry['image_path'])
            # 新しい画像を保存
            image_path = save_image(image, 'diary')
            data['image_path'] = image_path

    # 画像削除チェック
    if request.form.get('delete_image') == '1':
        if entry.get('image_path'):
            delete_image(entry['image_path'])
        data['image_path'] = None

    try:
        DiaryEntry.update(diary_id, data)

        # 関連を保存
        relations = {
            'crop_ids': request.form.getlist('crop_ids'),
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
        # 画像を削除
        if entry.get('image_path'):
            delete_image(entry['image_path'])
        DiaryEntry.delete(diary_id)
        flash(f'日記「{entry["title"]}」を削除しました', 'success')
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')

    return redirect(url_for('diary.list'))


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
