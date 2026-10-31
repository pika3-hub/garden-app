from app.database import get_db
from app.models.planting import _CV_JOIN
from app.utils.timezone import get_jst_now
from app.utils.search_text import fold


def _like_escape(keyword):
    return keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class Advice:
    """Hermes のアドバイスモデル"""

    ORDER = 'ORDER BY advised_on DESC, id DESC'

    @staticmethod
    def get_by_id(advice_id):
        row = get_db().execute('SELECT * FROM advices WHERE id = ?', (advice_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        db = get_db()
        now = get_jst_now()
        cursor = db.execute(
            '''INSERT INTO advices (title, question, answer, advised_on, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (data['title'], data.get('question'), data['answer'], data['advised_on'], now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(advice_id, data):
        db = get_db()
        db.execute(
            '''UPDATE advices SET title = ?, question = ?, answer = ?, advised_on = ?, updated_at = ?
               WHERE id = ?''',
            (data['title'], data.get('question'), data['answer'], data['advised_on'],
             get_jst_now(), advice_id)
        )
        db.commit()

    @staticmethod
    def delete(advice_id):
        db = get_db()
        # PRAGMA foreign_keys は有効にしていないので CASCADE に頼らず消す
        db.execute('DELETE FROM advice_relations WHERE advice_id = ?', (advice_id,))
        db.execute('DELETE FROM advices WHERE id = ?', (advice_id,))
        db.commit()

    @staticmethod
    def get_all():
        rows = get_db().execute(f'SELECT * FROM advices {Advice.ORDER}').fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def search(keyword):
        rows = get_db().execute(
            f'''SELECT * FROM advices
                WHERE search_fold(title) LIKE :p ESCAPE '\\' OR search_fold(question) LIKE :p ESCAPE '\\'
                   OR search_fold(answer) LIKE :p ESCAPE '\\'
                {Advice.ORDER}''',
            {'p': f'%{_like_escape(fold(keyword))}%'}
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_adjacent(advice_id):
        """一覧の並びで前（新しい側）と後ろを返す"""
        rows = get_db().execute(f'SELECT id, title FROM advices {Advice.ORDER}').fetchall()
        items = [dict(r) for r in rows]
        for i, item in enumerate(items):
            if item['id'] == advice_id:
                prev_item = items[i - 1] if i > 0 else None
                next_item = items[i + 1] if i < len(items) - 1 else None
                return prev_item, next_item
        return None, None

    @staticmethod
    def get_relations(advice_id):
        db = get_db()
        crops = db.execute(
            '''SELECT ar.crop_id, c.name as crop_name, c.crop_type, NULL as variety,
                      c.icon_path, c.image_color, c.image_path as crop_image_path
               FROM advice_relations ar
               JOIN crops c ON ar.crop_id = c.id
               WHERE ar.advice_id = ? AND ar.relation_type = 'crop' ''',
            (advice_id,)
        ).fetchall()
        varieties = db.execute(
            '''SELECT ar.variety_id, v.name as variety,
                      c.id as crop_id, c.name as crop_name, c.crop_type,
                      COALESCE(v.icon_path, c.icon_path) as icon_path,
                      COALESCE(v.image_color, c.image_color) as image_color,
                      COALESCE(v.image_path, c.image_path) as variety_image_path
               FROM advice_relations ar
               JOIN varieties v ON ar.variety_id = v.id
               JOIN crops c ON v.crop_id = c.id
               WHERE ar.advice_id = ? AND ar.relation_type = 'variety' ''',
            (advice_id,)
        ).fetchall()
        location_crops = db.execute(
            f'''SELECT lc.id as id, lc.id as location_crop_id, cv.crop_name, cv.variety,
                       cv.icon_path, cv.image_color, l.name as location_name,
                       lc.location_id, lc.planted_date, lc.status,
                       (SELECT pr.image_path FROM planting_records pr
                        WHERE pr.location_crop_id = lc.id AND pr.image_path IS NOT NULL AND pr.image_path != ''
                        ORDER BY pr.recorded_at DESC, pr.created_at DESC LIMIT 1) as latest_record_image
                FROM advice_relations ar
                JOIN plantings lc ON ar.location_crop_id = lc.id
                {_CV_JOIN}
                JOIN locations l ON lc.location_id = l.id
                WHERE ar.advice_id = ? AND ar.relation_type = 'location_crop' ''',
            (advice_id,)
        ).fetchall()
        return {
            'crops': [dict(r) for r in crops],
            'varieties': [dict(r) for r in varieties],
            'location_crops': [dict(r) for r in location_crops],
        }

    @staticmethod
    def save_relations(advice_id, relations):
        db = get_db()
        db.execute('DELETE FROM advice_relations WHERE advice_id = ?', (advice_id,))
        for crop_id in relations.get('crop_ids', []):
            db.execute(
                "INSERT INTO advice_relations (advice_id, relation_type, crop_id) VALUES (?, 'crop', ?)",
                (advice_id, int(crop_id)))
        for variety_id in relations.get('variety_ids', []):
            db.execute(
                "INSERT INTO advice_relations (advice_id, relation_type, variety_id) VALUES (?, 'variety', ?)",
                (advice_id, int(variety_id)))
        for lc_id in relations.get('location_crop_ids', []):
            db.execute(
                "INSERT INTO advice_relations (advice_id, relation_type, location_crop_id) "
                "VALUES (?, 'location_crop', ?)",
                (advice_id, int(lc_id)))
        db.commit()

    @staticmethod
    def scope_clause(entity_type):
        """advices.id を返す副問い合わせの SQL と、渡す ID の個数を返す"""
        if entity_type == 'planting':
            return ('SELECT ar.advice_id FROM advice_relations ar WHERE ar.location_crop_id = ?', 1)
        if entity_type == 'variety':
            return ('SELECT ar.advice_id FROM advice_relations ar WHERE ar.variety_id = ? '
                    'UNION SELECT ar.advice_id FROM advice_relations ar '
                    'JOIN plantings lc ON ar.location_crop_id = lc.id WHERE lc.variety_id = ?', 2)
        if entity_type == 'crop':
            return ('SELECT ar.advice_id FROM advice_relations ar WHERE ar.crop_id = ? '
                    'UNION SELECT ar.advice_id FROM advice_relations ar '
                    'JOIN varieties v ON ar.variety_id = v.id WHERE v.crop_id = ? '
                    'UNION SELECT ar.advice_id FROM advice_relations ar '
                    'JOIN plantings lc ON ar.location_crop_id = lc.id '
                    f'{_CV_JOIN} WHERE cv.effective_crop_id = ?', 3)
        raise ValueError(f'不明な種類: {entity_type}')

    @staticmethod
    def get_for_entity(entity_type, entity_id):
        scope, n = Advice.scope_clause(entity_type)
        rows = get_db().execute(
            f'SELECT * FROM advices WHERE id IN ({scope}) {Advice.ORDER}',
            [entity_id] * n
        ).fetchall()
        result = []
        for row in rows:
            advice = dict(row)
            advice['via_labels'] = Advice._via_labels(advice['id'], entity_type, entity_id)
            result.append(advice)
        return result

    @staticmethod
    def _via_labels(advice_id, entity_type, entity_id):
        """その画面のデータ自身以外の関連の表示"""
        if entity_type == 'planting':
            return []
        rel = Advice.get_relations(advice_id)
        labels = []
        for c in rel['crops']:
            if not (entity_type == 'crop' and c['crop_id'] == entity_id):
                labels.append(f"作物: {c['crop_name']}")
        for v in rel['varieties']:
            if not (entity_type == 'variety' and v['variety_id'] == entity_id):
                labels.append(f"品種: {v['variety']}（{v['crop_name']}）")
        for lc in rel['location_crops']:
            name = f"{lc['variety']}（{lc['crop_name']}）" if lc['variety'] else lc['crop_name']
            labels.append(f"植え付け: {name} {lc['location_name']}")
        return labels
