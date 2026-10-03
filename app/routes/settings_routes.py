from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.app_settings import AppSettings

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
