from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.advice import Advice
from app.models.crop import Crop
from app.models.variety import Variety
from app.models.planting import Planting
from app.routes.task_routes import _build_filter_data

bp = Blueprint('advices', __name__, url_prefix='/advices')

PREVIEW_LENGTH = 100


def _ym(advice):
    d = advice.get('advised_on')
    return str(d)[:7] if d else ''


@bp.route('/')
def list():
    """アドバイス一覧"""
    keyword = request.args.get('keyword', '')
    advices = Advice.search(keyword) if keyword else Advice.get_all()

    years = sorted({str(a['advised_on'])[:4] for a in advices if a.get('advised_on')}, reverse=True)
    grouped_advices = [(k, [item for item in g]) for k, g in groupby(advices, key=_ym)]

    for a in advices:
        a['preview'] = (a['answer'] or '').replace('\r', '').replace('\n', ' ')[:PREVIEW_LENGTH]
        rel = Advice.get_relations(a['id'])
        a['relation_labels'] = (
            [c['crop_name'] for c in rel['crops']]
            + [f"{v['variety']}（{v['crop_name']}）" for v in rel['varieties']]
            + [f"{lc['variety']}（{lc['crop_name']}）" if lc['variety'] else lc['crop_name']
               for lc in rel['location_crops']])

    return render_template('advices/list.html',
                           advices=advices,
                           grouped_advices=grouped_advices,
                           keyword=keyword,
                           years=years)


@bp.route('/<int:advice_id>')
def detail(advice_id):
    """アドバイス詳細"""
    advice = Advice.get_by_id(advice_id)
    if not advice:
        flash('アドバイスが見つかりません', 'danger')
        return redirect(url_for('advices.list'))

    prev_advice, next_advice = Advice.get_adjacent(advice_id)
    return render_template('advices/detail.html',
                           advice=advice,
                           relations=Advice.get_relations(advice_id),
                           prev_advice=prev_advice,
                           next_advice=next_advice)


@bp.route('/<int:advice_id>/edit')
def edit(advice_id):
    """アドバイス編集フォーム（新規作成は Hermes の API だけ）"""
    advice = Advice.get_by_id(advice_id)
    if not advice:
        flash('アドバイスが見つかりません', 'danger')
        return redirect(url_for('advices.list'))

    crops = Crop.get_all()
    varieties = Variety.get_all()
    for v in varieties:
        Variety.apply_inheritance(v)
    relations = Advice.get_relations(advice_id)

    selected_crop_ids = [str(r['crop_id']) for r in relations['crops']]
    selected_variety_ids = [str(r['variety_id']) for r in relations['varieties']]
    selected_location_crop_ids = [str(r['location_crop_id']) for r in relations['location_crops']]

    # 栽培終了の植え付けに付いたアドバイスも直せるよう、削除済み以外と選択済みを渡す
    plantings = [p for p in Planting.get_all_with_stats()
                 if p['status'] != 'removed' or str(p['id']) in selected_location_crop_ids]

    filter_data = _build_filter_data(crops, varieties, [], plantings)
    sorted_crops = filter_data.pop('modal_sorted_crops')

    return render_template('advices/form.html',
                           advice=advice,
                           crops=sorted_crops,
                           varieties=varieties,
                           active_plantings=plantings,
                           selected_relations={'crop_ids': selected_crop_ids,
                                               'variety_ids': selected_variety_ids,
                                               'location_crop_ids': selected_location_crop_ids},
                           selected_crop_ids=selected_crop_ids,
                           selected_variety_ids=selected_variety_ids,
                           selected_location_crop_ids=selected_location_crop_ids,
                           **filter_data)


@bp.route('/<int:advice_id>/update', methods=['POST'])
def update(advice_id):
    """アドバイス更新処理"""
    advice = Advice.get_by_id(advice_id)
    if not advice:
        flash('アドバイスが見つかりません', 'danger')
        return redirect(url_for('advices.list'))

    data = {
        'title': (request.form.get('title') or '').strip(),
        'question': request.form.get('question') or None,
        'answer': (request.form.get('answer') or '').strip(),
        'advised_on': request.form.get('advised_on') or '',
    }
    if not data['title'] or not data['answer'] or not data['advised_on']:
        flash('見出し・日付・アドバイスは必須です', 'danger')
        return redirect(url_for('advices.edit', advice_id=advice_id))

    try:
        Advice.update(advice_id, data)
        Advice.save_relations(advice_id, {
            'crop_ids': request.form.getlist('crop_ids'),
            'variety_ids': request.form.getlist('variety_ids'),
            'location_crop_ids': request.form.getlist('location_crop_ids'),
        })
        flash(f'アドバイス「{data["title"]}」を更新しました', 'success')
        return redirect(url_for('advices.detail', advice_id=advice_id))
    except Exception as e:
        flash(f'エラーが発生しました: {str(e)}', 'danger')
        return redirect(url_for('advices.edit', advice_id=advice_id))


@bp.route('/<int:advice_id>/delete', methods=['POST'])
def delete(advice_id):
    """アドバイス削除処理"""
    advice = Advice.get_by_id(advice_id)
    if not advice:
        flash('アドバイスが見つかりません', 'danger')
        return redirect(url_for('advices.list'))

    Advice.delete(advice_id)
    flash(f'アドバイス「{advice["title"]}」を削除しました', 'success')
    return redirect(url_for('advices.list'))
