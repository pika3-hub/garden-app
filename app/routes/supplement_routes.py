from flask import Blueprint, request, redirect, url_for, flash
from app.models.supplement import (
    Supplement, extract_youtube_info, format_youtube_content,
    validate_url, VALID_ENTITY_TYPES, VALID_SUPPLEMENT_TYPES,
)
from app.models.photo_pool import PhotoPool
from app.utils.upload import save_image, delete_image, copy_image
from app.utils.ogp_fetcher import fetch_ogp

bp = Blueprint('supplements', __name__, url_prefix='/supplements')

# エンティティ詳細ページへのリダイレクト設定
ENTITY_DETAIL_ROUTES = {
    'crop': ('crops.detail', 'crop_id'),
    'variety': ('varieties.detail', 'variety_id'),
    'location': ('locations.detail', 'location_id'),
    'diary': ('diary.detail', 'diary_id'),
    'task': ('tasks.detail', 'task_id'),
    'harvest': ('harvests.detail', 'harvest_id'),
    'cooking': ('cooking.detail', 'cooking_id'),
}


def _redirect_to_entity(entity_type, entity_id):
    endpoint, param = ENTITY_DETAIL_ROUTES[entity_type]
    return redirect(url_for(endpoint, **{param: entity_id}) + '#supplements')


@bp.route('/<entity_type>/<int:entity_id>/add', methods=['POST'])
def add(entity_type, entity_id):
    """補足情報を追加"""
    if entity_type not in VALID_ENTITY_TYPES:
        flash('無効なエンティティタイプです', 'danger')
        return redirect(url_for('index'))

    supplement_type = request.form.get('supplement_type')
    if supplement_type not in VALID_SUPPLEMENT_TYPES:
        flash('無効な補足タイプです', 'danger')
        return _redirect_to_entity(entity_type, entity_id)

    title = request.form.get('title', '').strip() or None
    content = None
    ogp = {}

    if supplement_type == 'text':
        content = request.form.get('content', '').strip()
        if not content:
            flash('テキストを入力してください', 'danger')
            return _redirect_to_entity(entity_type, entity_id)

    elif supplement_type == 'image':
        photo_pool_id = request.form.get('photo_pool_id', type=int)
        if photo_pool_id:
            pool_photo = PhotoPool.get_by_id(photo_pool_id)
            if not pool_photo:
                flash('写真プールの画像が見つかりません', 'danger')
                return _redirect_to_entity(entity_type, entity_id)
            image_path = copy_image(pool_photo['image_path'], 'supplements')
            if not image_path:
                flash('画像のアップロードに失敗しました', 'danger')
                return _redirect_to_entity(entity_type, entity_id)
            content = image_path
        else:
            if 'image' not in request.files or not request.files['image'].filename:
                flash('画像ファイルを選択してください', 'danger')
                return _redirect_to_entity(entity_type, entity_id)
            image_path = save_image(request.files['image'], 'supplements')
            if not image_path:
                flash('画像のアップロードに失敗しました', 'danger')
                return _redirect_to_entity(entity_type, entity_id)
            content = image_path

    elif supplement_type == 'url':
        url = request.form.get('content', '').strip()
        if not validate_url(url):
            flash('有効なURL（http:// または https://）を入力してください', 'danger')
            return _redirect_to_entity(entity_type, entity_id)
        content = url
        ogp = fetch_ogp(url)

    elif supplement_type == 'youtube':
        youtube_input = request.form.get('content', '').strip()
        video_id, start = extract_youtube_info(youtube_input)
        if not video_id:
            flash('YouTube の URL を正しく認識できませんでした', 'danger')
            return _redirect_to_entity(entity_type, entity_id)
        content = format_youtube_content(video_id, start)

    supplement_id = Supplement.create({
        'entity_type': entity_type,
        'entity_id': entity_id,
        'supplement_type': supplement_type,
        'title': title,
        'content': content,
        **ogp,
    })
    if supplement_type == 'image':
        pool_id = request.form.get('photo_pool_id', type=int)
        if pool_id:
            PhotoPool.record_usage(pool_id, 'supplement', supplement_id, content)
    flash('補足情報を追加しました', 'success')
    return _redirect_to_entity(entity_type, entity_id)


@bp.route('/<int:supplement_id>/update', methods=['POST'])
def update(supplement_id):
    """補足情報を更新"""
    supplement = Supplement.get_by_id(supplement_id)
    if not supplement:
        flash('補足情報が見つかりません', 'danger')
        return redirect(url_for('index'))

    entity_type = supplement['entity_type']
    entity_id = supplement['entity_id']
    supplement_type = supplement['supplement_type']
    title = request.form.get('title', '').strip() or None
    content = supplement['content']
    ogp = {}

    if supplement_type == 'text':
        content = request.form.get('content', '').strip()
        if not content:
            flash('テキストを入力してください', 'danger')
            return _redirect_to_entity(entity_type, entity_id)

    elif supplement_type == 'image':
        # 画像の差し替え（写真プール優先）
        pool_id = request.form.get('photo_pool_id', type=int)
        if pool_id:
            pool_photo = PhotoPool.get_by_id(pool_id)
            if pool_photo:
                delete_image(supplement['content'])
                image_path = copy_image(pool_photo['image_path'], 'supplements')
                if image_path:
                    content = image_path
                    PhotoPool.record_usage(pool_id, 'supplement', supplement_id, image_path)
        elif 'image' in request.files and request.files['image'].filename:
            delete_image(supplement['content'])
            image_path = save_image(request.files['image'], 'supplements')
            if image_path:
                content = image_path

    elif supplement_type == 'url':
        url = request.form.get('content', '').strip()
        if not validate_url(url):
            flash('有効なURL（http:// または https://）を入力してください', 'danger')
            return _redirect_to_entity(entity_type, entity_id)
        content = url
        if url != supplement['content']:
            ogp = fetch_ogp(url)
        else:
            ogp = {
                'ogp_image':       supplement['ogp_image'],
                'ogp_title':       supplement['ogp_title'],
                'ogp_description': supplement['ogp_description'],
            }

    elif supplement_type == 'youtube':
        youtube_input = request.form.get('content', '').strip()
        video_id, start = extract_youtube_info(youtube_input)
        if not video_id:
            flash('YouTube の URL を正しく認識できませんでした', 'danger')
            return _redirect_to_entity(entity_type, entity_id)
        content = format_youtube_content(video_id, start)

    update_data = {'title': title, 'content': content}
    if supplement_type == 'url':
        update_data.update(ogp)
    Supplement.update(supplement_id, update_data)
    flash('補足情報を更新しました', 'success')
    return _redirect_to_entity(entity_type, entity_id)


@bp.route('/<int:supplement_id>/delete', methods=['POST'])
def delete(supplement_id):
    """補足情報を削除"""
    supplement = Supplement.get_by_id(supplement_id)
    if not supplement:
        flash('補足情報が見つかりません', 'danger')
        return redirect(url_for('index'))

    entity_type = supplement['entity_type']
    entity_id = supplement['entity_id']

    # 画像の場合はファイルも削除
    if supplement['supplement_type'] == 'image' and supplement['content']:
        delete_image(supplement['content'])

    Supplement.delete(supplement_id)
    flash('補足情報を削除しました', 'success')
    return _redirect_to_entity(entity_type, entity_id)
