import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image

bp = Blueprint('photo_pool', __name__, url_prefix='/photo_pool')


# プールから登録できる対象エンティティと、対応する new エンドポイント
TARGET_ENDPOINTS = {
    'diary': 'diary.new',
    'harvest': 'harvests.new',
    'crop': 'crops.new',
    'location': 'locations.new',
}


def _extract_taken_at(file_path):
    """EXIFから撮影日時を取得。失敗時はNone"""
    try:
        from PIL import Image
        img = Image.open(file_path)
        exif = img._getexif() if hasattr(img, '_getexif') else None
        if not exif:
            return None
        # 36867 = DateTimeOriginal
        dt = exif.get(36867) or exif.get(306)
        if dt:
            # '2026:04:15 10:30:00' → '2026-04-15 10:30:00'
            return dt.replace(':', '-', 2)
    except Exception:
        pass
    return None


@bp.route('/')
def index():
    """写真プール一覧"""
    from app.models.planting import Planting
    photos = PhotoPool.get_all()
    active_plantings = Planting.get_all_with_stats(status='active')
    filter_types = sorted(set(p['crop_type'] for p in active_plantings if p.get('crop_type')))
    filter_locations = sorted(set(p['location_name'] for p in active_plantings if p.get('location_name')))
    filter_type_icons = {}
    for p in active_plantings:
        t, icon = p.get('crop_type'), p.get('icon_path')
        if t and icon:
            icons = filter_type_icons.setdefault(t, [])
            if not any(i['icon_path'] == icon for i in icons):
                icons.append({'icon_path': icon, 'image_color': p.get('image_color') or '#4CAF50'})
    return render_template('photo_pool/index.html',
                           photos=photos,
                           active_plantings=active_plantings,
                           filter_types=filter_types,
                           filter_type_icons=filter_type_icons,
                           filter_locations=filter_locations)


@bp.route('/upload', methods=['POST'])
def upload():
    """複数ファイル一括アップロード"""
    files = request.files.getlist('images')
    if not files:
        flash('ファイルが選択されていません', 'warning')
        return redirect(url_for('photo_pool.index'))

    upload_folder = current_app.config['UPLOAD_FOLDER']
    success = 0
    failed = 0
    for f in files:
        if not f or not f.filename:
            continue
        image_path = save_image(f, 'photo_pool')
        if not image_path:
            failed += 1
            continue
        full_path = os.path.join(upload_folder, image_path)
        file_size = os.path.getsize(full_path) if os.path.exists(full_path) else None
        taken_at = _extract_taken_at(full_path)
        PhotoPool.create(
            image_path=image_path,
            original_filename=f.filename,
            file_size=file_size,
            taken_at=taken_at,
        )
        success += 1

    if success:
        flash(f'{success}枚の写真をアップロードしました', 'success')
    if failed:
        flash(f'{failed}枚のアップロードに失敗しました', 'warning')
    return redirect(url_for('photo_pool.index'))


@bp.route('/<int:photo_id>/update', methods=['POST'])
def update(photo_id):
    photo = PhotoPool.get_by_id(photo_id)
    if not photo:
        flash('写真が見つかりません', 'danger')
        return redirect(url_for('photo_pool.index'))
    notes = request.form.get('notes', '').strip() or None
    PhotoPool.update_notes(photo_id, notes)
    flash('メモを更新しました', 'success')
    return redirect(url_for('photo_pool.index'))


@bp.route('/<int:photo_id>/delete', methods=['POST'])
def delete(photo_id):
    photo = PhotoPool.get_by_id(photo_id)
    if not photo:
        flash('写真が見つかりません', 'danger')
        return redirect(url_for('photo_pool.index'))
    image_path = PhotoPool.delete(photo_id)
    if image_path:
        delete_image(image_path)
    flash('写真を削除しました', 'success')
    return redirect(url_for('photo_pool.index'))


@bp.route('/bulk-delete', methods=['POST'])
def bulk_delete():
    raw_ids = request.form.getlist('photo_ids')
    ids = [int(x) for x in raw_ids if x.isdigit()]
    if not ids:
        flash('写真が選択されていません', 'warning')
        return redirect(url_for('photo_pool.index'))
    paths = PhotoPool.delete_many(ids)
    for p in paths:
        delete_image(p)
    flash(f'{len(paths)}枚の写真を削除しました', 'success')
    return redirect(url_for('photo_pool.index'))


@bp.route('/<int:photo_id>/use')
def use(photo_id):
    """選択した写真で対象エンティティの登録フォームへ遷移"""
    photo = PhotoPool.get_by_id(photo_id)
    if not photo:
        flash('写真が見つかりません', 'danger')
        return redirect(url_for('photo_pool.index'))
    target = request.args.get('target', '')
    endpoint = TARGET_ENDPOINTS.get(target)
    if not endpoint:
        flash('登録先が不正です', 'danger')
        return redirect(url_for('photo_pool.index'))
    return redirect(url_for(endpoint, photo_pool_id=photo_id))
