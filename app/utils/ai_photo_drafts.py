"""写真プールの振り分け画面の AI 下書き（Claude API、写真を見て入力欄の一部を書く）

Flask に依存しない。呼び出し・エラー処理・モデルの選び方は ai_notes と共有する。
"""
import base64
import json

from app.utils.ai_notes import (
    FALLBACK_BETA, MODEL_INFO, AiNotesError, current_model, new_client, request,
)

MAX_TOKENS = 4000

# 種類ごとに AI が書く項目（JSON のキー）
DRAFT_FIELDS = {
    'location': ['notes'],
    'planting': ['notes'],
    'planting_record': ['notes'],
    'harvest': ['notes'],
    'cooking': ['title', 'category', 'notes'],
    'diary': ['title', 'content'],
}

PHOTO_SYSTEM_PROMPT = """あなたは日本の家庭菜園の記録係です。
ユーザーが撮った写真1枚を見て、記録の入力欄の下書きを日本語で書きます。

# 書き方
- 写真に写っている様子だけを書く。アドバイス・作業の提案・病気などの推測は書かない。
- 写真から分からないこと（収穫した数・重さ、味、品種名など）は書かない。
- 短く、だ・である調で書く。メモは2〜4文程度。Markdown の見出しは使わない。
- 栽培記録・収穫で前回の記録のメモが渡されたら、前回からの変化を1〜2文添える。
- 植え付けが複数渡されたら、全体で1つのメモにまとめる。
- 料理のカテゴリは候補から選ぶ。合うものが無ければ短い新しい名前にする。
"""

_KIND_TEXT = {
    'location': '場所の写真です。場所のメモ（写真に写った場所の様子）を書いてください。',
    'planting': '植え付けたときの写真です。最初の栽培記録のメモ（植え付け時の様子）を書いてください。',
    'planting_record': '栽培記録の写真です。栽培記録のメモ（生育の様子）を書いてください。',
    'harvest': '収穫の写真です。収穫記録のメモ（収穫物の様子）を書いてください。',
    'cooking': '料理の写真です。料理のタイトル・カテゴリ・メモを書いてください。',
    'diary': '日記に付ける写真です。日記のタイトルと本文を書いてください。',
}


def _build_user_text(kind, context):
    lines = []
    if context.get('date'):
        lines.append(f'日付: {context["date"]}')
    if context.get('name'):
        lines.append(f'名前: {context["name"]}')
    for p in context.get('plantings') or []:
        lines.append(f'植え付け: {p["label"]}')
        lines.append(f'  前回の記録のメモ: {p.get("previous_notes") or "（なし）"}')
    if context.get('categories'):
        lines.append('カテゴリの候補: ' + '、'.join(context['categories']))
    if context.get('related'):
        lines.append('関連する作物など: ' + '、'.join(context['related']))
    lines.append('')
    lines.append(_KIND_TEXT[kind])
    return '\n'.join(lines)


def _schema(fields):
    return {
        'type': 'object',
        'properties': {f: {'type': 'string'} for f in fields},
        'required': list(fields),
        'additionalProperties': False,
    }


def _parse(blocks, fields):
    text = ''.join(b.text for b in blocks if getattr(b, 'type', None) == 'text')
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if not isinstance(data, dict) or not all(isinstance(data.get(f), str) for f in fields):
        raise AiNotesError('生成結果を読み取れませんでした。もう一度お試しください')
    return {f: data[f].strip() for f in fields}


def generate_photo_draft(kind, image_bytes, context, client=None, model=None):
    """写真（JPEG）から kind に応じた項目の下書きを {項目: 文字列} で返す。

    失敗時は AiNotesError、未対応の kind は ValueError を送出する。
    """
    if kind not in DRAFT_FIELDS:
        raise ValueError(f'unsupported kind: {kind}')
    fields = DRAFT_FIELDS[kind]
    model = model or current_model()
    if client is None:
        client = new_client()

    params = {
        'model': model,
        'max_tokens': MAX_TOKENS,
        'system': PHOTO_SYSTEM_PROMPT,
        'output_config': {'effort': 'low', 'format': {'type': 'json_schema', 'schema': _schema(fields)}},
        'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {
                'type': 'base64', 'media_type': 'image/jpeg',
                'data': base64.standard_b64encode(image_bytes).decode('ascii')}},
            {'type': 'text', 'text': _build_user_text(kind, context)},
        ]}],
    }
    if MODEL_INFO[model]['fallbacks']:
        params['betas'] = [FALLBACK_BETA]
        params['fallbacks'] = 'default'

    return _parse(request(client, params), fields)
