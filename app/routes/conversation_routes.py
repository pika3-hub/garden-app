import re
from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_db
from app.models.conversation import Conversation, KIND_LABELS, KIND_PRIORITY
from app.models.photo_pool import PhotoPool, _labels
from app.routes.photo_pool_routes import usage_url

bp = Blueprint('conversations', __name__, url_prefix='/conversations')

_IMAGE_MARKER_RE = re.compile(r'\[Image attached at:\s*([^\]]*)\]')
_SCREENSHOT_RE = re.compile(r'\[screenshot\]')
# 作った・変えた・見たの順
_KIND_ORDER = sorted(KIND_PRIORITY, key=lambda k: -KIND_PRIORITY[k])


def strip_image_markers(text):
    """印 [Image attached at: …] と [screenshot] を除いた本文と、印のファイル名のリストを返す"""
    names = []
    for m in _IMAGE_MARKER_RE.finditer(text or ''):
        path = m.group(1).strip().replace('\\', '/')
        names.append(path.rsplit('/', 1)[-1])
    text = _IMAGE_MARKER_RE.sub('', text or '')
    text = _SCREENSHOT_RE.sub('', text)
    return text, names


def link_items(links):
    """結び付けの行に label / target_type / target_id / kind_label を付け、
    同じデータは優先の高い区分1つにまとめ、作った・変えた・見たの順に並べる"""
    merged = {}
    for link in links:
        key = (link['entity_type'], link['entity_id'])
        cur = merged.get(key)
        if cur is None:
            merged[key] = dict(link)
        elif KIND_PRIORITY[link['kind']] > KIND_PRIORITY[cur['kind']]:
            cur['kind'] = link['kind']

    db = get_db()
    ids_by_type = {}
    for t, i in merged:
        ids_by_type.setdefault(t, []).append(i)
    labels = {t: _labels(db, t, ids) for t, ids in ids_by_type.items() if t != 'photo_pool'}

    items = []
    for (t, i), item in merged.items():
        if t == 'photo_pool':
            exists = PhotoPool.get_by_id(i) is not None
            item['label'] = f'写真プールの写真 #{i}' if exists else None
        else:
            item['label'] = labels.get(t, {}).get(i)
        item['target_type'] = t if item['label'] else None
        item['target_id'] = i if item['label'] else None
        if t == 'photo_pool':
            item['url'] = url_for('photo_pool.index') if item['label'] else None
        else:
            item['url'] = usage_url(item)
        item['kind_label'] = KIND_LABELS[item['kind']]
        items.append(item)
    items.sort(key=lambda x: _KIND_ORDER.index(x['kind']))
    return items


@bp.route('/')
def list():
    """会話一覧"""
    keyword = request.args.get('keyword', '')
    conversations = Conversation.search(keyword) if keyword else Conversation.get_all()
    for c in conversations:
        c['ts'] = str(c.get('last_activity_at') or c.get('started_at') or '')

    years = sorted({c['ts'][:4] for c in conversations if c['ts']}, reverse=True)
    grouped = [(k, [c for c in g]) for k, g in groupby(conversations, key=lambda c: c['ts'][:7])]
    return render_template('conversations/list.html',
                           conversations=conversations,
                           grouped_conversations=grouped,
                           keyword=keyword,
                           years=years)


@bp.route('/<int:conversation_id>')
def detail(conversation_id):
    """会話詳細"""
    conversation = Conversation.get_by_id(conversation_id)
    if not conversation:
        flash('会話が見つかりません', 'danger')
        return redirect(url_for('conversations.list'))

    images = Conversation.get_images(conversation_id)
    messages = []
    for m in Conversation.get_messages(conversation_id):
        text, names = strip_image_markers(m['content'])
        m['text'] = text.strip()
        m['time'] = str(m['timestamp'] or '')
        m['photos'] = [{'file_name': n, 'image_path': images.get(n)} for n in names]
        messages.append(m)

    parent = None
    if conversation.get('parent_hermes_id'):
        parent = Conversation.get_by_hermes_id(conversation['parent_hermes_id'])

    prev_item, next_item = Conversation.get_adjacent(conversation_id)
    for adj in (prev_item, next_item):
        if adj:
            adj['last_activity_at'] = str(adj['last_activity_at'] or '')
    links = link_items(Conversation.get_links(conversation_id))

    return render_template('conversations/detail.html',
                           conversation=conversation,
                           messages=messages,
                           parent=parent,
                           prev_item=prev_item,
                           next_item=next_item,
                           links=links)
