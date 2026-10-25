"""写真プールの振り分け画面（選んだ写真を1枚ずつ登録し、保存したら次の写真へ進む）

状態は URL のパラメーターだけで持つ: ids=写真IDの並び, pos=今の位置, done=登録済みの写真ID, kind=登録する種類
"""
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.models.photo_pool import PhotoPool
from app.routes.photo_pool_routes import usage_url

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
                           form_values=form_values or {})


@bp.route('/')
def index():
    """振り分け画面"""
    ids = _parse_ids(request.args.get('ids'))
    pos = max(request.args.get('pos', 0, type=int), 0)
    done = set(_parse_ids(request.args.get('done')))
    return render_sort_page(ids, pos, done, request.args.get('kind'))
