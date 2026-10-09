"""疎通確認・選択肢一覧・名前検索"""
from flask import current_app, request

from app.api import bp
from app.api.choices import (
    COOKING_RELATION_KEYS, DIARY_RELATION_KEYS, PLANTING_STATUSES, SUN_EXPOSURES,
    TASK_RELATION_KEYS, TASK_STATUSES, WEATHERS, bg_images, crop_icons, distinct_values,
)
from app.api.errors import detail, ok, validation_error
from app.api.resource import LIKE_ESCAPE, like_pattern, page_arg
from app.api.serialize import display_name, web_url
from app.database import get_db

RESOURCE_NAMES = ['crops', 'varieties', 'locations', 'plantings', 'planting_records', 'harvests',
                  'cooking_records', 'diary_entries', 'tasks', 'photos']
LOOKUP_TYPES = ('crop', 'variety', 'location')


@bp.get('/health')
def health():
    return ok({'status': 'ok'})


@bp.get('/meta')
def meta():
    """エージェントが最初に読む選択肢の一覧"""
    return ok({
        'resources': RESOURCE_NAMES,
        'date_format': 'YYYY-MM-DD',
        'planting_statuses': PLANTING_STATUSES,
        'task_statuses': TASK_STATUSES,
        'sun_exposures': SUN_EXPOSURES,
        'weathers': WEATHERS,
        'crop_types': distinct_values('crops', 'crop_type'),
        'location_types': distinct_values('locations', 'location_type'),
        'harvest_units': distinct_values('harvests', 'unit'),
        'cooking_categories': distinct_values('cooking', 'category'),
        'crop_icons': crop_icons(),
        'bg_images': bg_images(),
        'relation_keys': {
            'diary_entries': list(DIARY_RELATION_KEYS),
            'cooking_records': list(COOKING_RELATION_KEYS),
            'tasks': list(TASK_RELATION_KEYS),
        },
        'image_formats': ['jpeg', 'png', 'gif', 'webp'],
        'max_image_mb': current_app.config['API_MAX_IMAGE_MB'],
    })


def _rank(name, q):
    n, k = name.casefold(), q.casefold()
    return 0 if n == k else 1 if n.startswith(k) else 2


@bp.get('/lookup')
def lookup():
    """作物・品種・場所を名前で横断検索（完全一致 → 前方一致 → 部分一致）"""
    args = request.args
    errors = [detail(k, '未知の検索条件です。使える条件: q, types, limit')
              for k in args if k not in ('q', 'types', 'limit')]
    q = args.get('q', '').strip()
    if not q:
        errors.append(detail('q', '検索する名前を指定してください（例: q=ミニトマト）'))
    types_raw = args.get('types')
    types = [t.strip() for t in types_raw.split(',')] if types_raw else list(LOOKUP_TYPES)
    if any(t not in LOOKUP_TYPES for t in types):
        errors.append(detail('types', 'crop, variety, location をカンマ区切りで指定してください', types_raw))
    limit = page_arg(args, 'limit', 20, 1, 100, errors)
    if errors:
        raise validation_error(errors)

    db = get_db()
    pattern = like_pattern(q)
    items = []
    if 'crop' in types:
        for r in db.execute(f'SELECT id, name, crop_type FROM crops WHERE name LIKE ? {LIKE_ESCAPE}', (pattern,)):
            items.append({'type': 'crop', 'id': r['id'], 'name': r['name'], 'display_name': r['name'],
                          'crop_type': r['crop_type'], 'web_url': web_url(f'/crops/{r["id"]}')})
    if 'variety' in types:
        for r in db.execute(
                f'''SELECT v.id, v.name, v.crop_id, c.name AS crop_name
                    FROM varieties v JOIN crops c ON v.crop_id = c.id
                    WHERE v.name LIKE ? {LIKE_ESCAPE}''', (pattern,)):
            items.append({'type': 'variety', 'id': r['id'], 'name': r['name'],
                          'display_name': display_name(r['crop_name'], r['name']),
                          'crop_id': r['crop_id'], 'web_url': web_url(f'/varieties/{r["id"]}')})
    if 'location' in types:
        for r in db.execute(f'SELECT id, name, location_type FROM locations WHERE name LIKE ? {LIKE_ESCAPE}',
                            (pattern,)):
            items.append({'type': 'location', 'id': r['id'], 'name': r['name'], 'display_name': r['name'],
                          'location_type': r['location_type'], 'web_url': web_url(f'/locations/{r["id"]}')})

    order = {t: i for i, t in enumerate(LOOKUP_TYPES)}
    items.sort(key=lambda it: (_rank(it['name'], q), order[it['type']], it['name']))
    return ok(items[:limit], meta={'total': len(items), 'limit': limit})
