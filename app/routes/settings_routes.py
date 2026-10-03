from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.app_settings import AppSettings
from app.models.crop import Crop
from app.utils.ai_notes import AiNotesError, NO_API_KEY_MESSAGE, generate_notes, is_available

bp = Blueprint('settings', __name__, url_prefix='/settings')

REGION_MAX_LENGTH = 500


@bp.route('/', methods=['GET'])
def index():
    """設定画面"""
    return render_template('settings/index.html', region=AppSettings.get('region', ''),
                           region_max_length=REGION_MAX_LENGTH)


@bp.route('/', methods=['POST'])
def update():
    """設定保存"""
    region = (request.form.get('region') or '').strip()
    if len(region) > REGION_MAX_LENGTH:
        flash(f'地域・栽培環境は{REGION_MAX_LENGTH}文字以内で入力してください', 'danger')
        return render_template('settings/index.html', region=region,
                               region_max_length=REGION_MAX_LENGTH), 400
    AppSettings.set('region', region)
    flash('設定を保存しました', 'success')
    return redirect(url_for('settings.index'))


def _draft_error(message, status=400, **extra):
    return jsonify({'ok': False, 'error': message, **extra}), status


def _parse_crop_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@bp.route('/ai/notes-draft', methods=['POST'])
def ai_notes_draft():
    """作物・品種メモの AI 下書きを生成（JSON）"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _draft_error('不正なリクエストです')

    mode = payload.get('mode')
    use_web_search = bool(payload.get('use_web_search'))

    if mode == 'crop':
        crop_name = (payload.get('crop_name') or '').strip()
        crop_type = (payload.get('crop_type') or '').strip() or None
        variety_name = None
        if not crop_name:
            return _draft_error('作物名を入力してください')
    elif mode == 'variety':
        crop_id = _parse_crop_id(payload.get('crop_id'))
        crop = Crop.get_by_id(crop_id) if crop_id is not None else None
        if not crop:
            return _draft_error('親作物が見つかりません。選び直してください')
        crop_name, crop_type = crop['name'], crop['crop_type']
        variety_name = (payload.get('variety_name') or '').strip()
        if not variety_name:
            return _draft_error('品種名を入力してください')
    else:
        return _draft_error('不正なリクエストです')

    region = (AppSettings.get('region') or '').strip()
    if not region:
        return _draft_error('先に設定画面で地域・栽培環境を登録してください', need_settings=True)
    if not is_available():
        return _draft_error(NO_API_KEY_MESSAGE)

    try:
        markdown = generate_notes(crop_name, crop_type, variety_name, region, use_web_search)
    except AiNotesError as e:
        return _draft_error(str(e), status=502)
    return jsonify({'ok': True, 'markdown': markdown})
