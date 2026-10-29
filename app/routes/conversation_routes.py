import re
from itertools import groupby
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_db
from app.models.conversation import Conversation, KIND_LABELS, KIND_PRIORITY
from app.models.photo_pool import PhotoPool, _labels
from app.models.hermes_chat import HermesChat
from app.routes.photo_pool_routes import _DETAIL_ENDPOINTS, usage_url
from app.utils.hermes_context import describe_target

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


_SOURCE_LABELS = {'api_server': 'アプリ', 'matrix': 'Element X'}


def attach_origin(conversations):
    """各会話に source_label（経路）と chat_target（アプリのパネルの対象）を付ける。
    対象は hermes_id、無ければ parent_hermes_id（圧縮で ID が変わった続き）で hermes_chats から探す。
    対象が消えていれば {'deleted': True}、対象なしの会話や対応する行が無ければ None"""
    ids = set()
    for c in conversations:
        ids.add(c['hermes_id'])
        if c.get('parent_hermes_id'):
            ids.add(c['parent_hermes_id'])
    chats = HermesChat.get_by_session_ids(ids)
    for c in conversations:
        c['source_label'] = _SOURCE_LABELS.get(c.get('source'))
        chat = chats.get(c['hermes_id']) or chats.get(c.get('parent_hermes_id'))
        target = None
        if chat and chat['entity_type']:
            info = describe_target(chat['entity_type'], chat['entity_id'])
            if info is None:
                target = {'deleted': True, 'kind_label': None, 'label': None, 'url': None}
            else:
                endpoint, arg = _DETAIL_ENDPOINTS[chat['entity_type']]
                target = {'deleted': False, 'kind_label': info['kind_label'],
                          'label': info['label'],
                          'url': url_for(endpoint, **{arg: chat['entity_id']})}
        c['chat_target'] = target
    return conversations


@bp.route('/')
def list():
    """会話一覧"""
    keyword = request.args.get('keyword', '')
    conversations = Conversation.search(keyword) if keyword else Conversation.get_all()
    attach_origin(conversations)
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

    attach_origin([conversation])
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
