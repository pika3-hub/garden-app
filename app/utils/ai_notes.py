"""作物・品種メモの AI 下書き生成（Claude API）

Flask に依存しない。APIキーは環境変数 ANTHROPIC_API_KEY、
モデルは ANTHROPIC_MODEL（許可リストのみ）で指定する。
"""
import logging
import os
import time

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'claude-opus-5-5'

# 許可するモデルと、モーダルに表示する目安（1ドル=150円で概算）
MODEL_INFO = {
    'claude-opus-5-5': {
        'label': 'Claude Opus 5.5',
        'estimate_off': '10〜30秒・約10円',
        'estimate_on': '30〜90秒・約35〜40円',
    },
    'claude-sonnet-5-5': {
        'label': 'Claude Sonnet 5.5',
        'estimate_off': '10〜20秒・約5円',
        'estimate_on': '30〜60秒・約20円',
    },
}

MAX_TOKENS = 16000
REQUEST_TIMEOUT_SECONDS = 180.0
MAX_PAUSE_CONTINUATIONS = 3
MAX_SEARCH_RESULT_SOURCES = 5
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
WEB_SEARCH_TOOL = {
    'type': 'web_search_20260209',
    'name': 'web_search',
    'max_uses': 5,
    'user_location': {'type': 'approximate', 'country': 'JP'},
}

NO_API_KEY_MESSAGE = 'AI機能を使うには .env に ANTHROPIC_API_KEY を設定してください'
_MSG_INCOMPLETE = '生成が途中で終わりました。もう一度お試しください'
_MSG_TIMEOUT = '時間内に生成が終わりませんでした。もう一度お試しください'

SYSTEM_PROMPT = """あなたは日本の家庭菜園に詳しいアドバイザーです。
ユーザーが指定した作物（または品種）について、家庭菜園の栽培メモの下書きを作成します。

# 出力ルール
- 次の見出し構成の Markdown だけを出力する。前置き・後書き・挨拶は書かない。
- 時期はユーザーの地域・栽培環境を基準に書く。種まきと苗の植え付けを区別する。
- 品種が指定された場合、親作物の一般論ではなく、その品種固有の特徴（味・サイズ・耐病性・草勢など）を優先して書く。
- 確かでない情報は推測で書かず「情報なし」と書く。
- 参考URLや出典リストは本文に書かない。

# 見出し構成
## 植え付け時期
## 収穫時期
## 特性
## 栽培のコツ
- 株間:
- 水やり:
- 肥料:
- 病害虫:
- コンパニオンプランツ:
"""


class AiNotesError(Exception):
    """利用者向けの日本語メッセージを持つ例外"""


_warned_models = set()


def resolve_model(env_value):
    """ANTHROPIC_MODEL の値を許可リストで検証してモデルIDを返す"""
    value = (env_value or '').strip()
    if not value:
        return DEFAULT_MODEL
    if value in MODEL_INFO:
        return value
    if value not in _warned_models:
        _warned_models.add(value)
        logger.warning('ANTHROPIC_MODEL=%s は未対応のため %s を使用します', value, DEFAULT_MODEL)
    return DEFAULT_MODEL


def current_model():
    """環境変数から現在のモデルIDを返す"""
    return resolve_model(os.environ.get('ANTHROPIC_MODEL'))


def is_available():
    """APIキーが設定されているか（空白のみは未設定扱い）"""
    return bool((os.environ.get('ANTHROPIC_API_KEY') or '').strip())


def _build_user_message(crop_name, crop_type, variety_name, region):
    lines = [f'作物名: {crop_name}']
    if crop_type:
        lines.append(f'作物種類: {crop_type}')
    if variety_name:
        lines.append(f'品種名: {variety_name}')
    lines.append(f'地域・栽培環境: {region}')
    lines.append('')
    if variety_name:
        lines.append(f'「{crop_name}」の品種「{variety_name}」の栽培メモを作成してください。'
                     '品種固有の特徴を優先してください。')
    else:
        lines.append(f'「{crop_name}」の栽培メモを作成してください。')
    return '\n'.join(lines)


def _build_request_params(model, user_message, use_web_search):
    params = {
        'model': model,
        'max_tokens': MAX_TOKENS,
        'system': SYSTEM_PROMPT,
        'output_config': {'effort': 'medium'},
        'betas': [FALLBACK_BETA],
        'fallbacks': 'default',
        'messages': [{'role': 'user', 'content': user_message}],
    }
    if use_web_search:
        params['tools'] = [WEB_SEARCH_TOOL]
    return params


def _extract_text_and_sources(blocks):
    """text ブロックを連結し、citations から (title, url) を重複なしで集める"""
    texts = []
    sources = []
    seen = set()
    for block in blocks:
        if getattr(block, 'type', None) != 'text':
            continue
        texts.append(block.text)
        for cite in getattr(block, 'citations', None) or []:
            url = getattr(cite, 'url', None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append((getattr(cite, 'title', None) or url, url))
    return ''.join(texts).strip(), sources


def _extract_search_result_sources(blocks):
    """web_search_tool_result の検索結果から (title, url) を重複なしで集める。

    web_search_20260209 は動的フィルタリング（コード実行経由で結果を読む）のため
    本文に citations が付かないことがあり、その場合の補完に使う。
    """
    sources = []
    seen = set()
    for block in blocks:
        if getattr(block, 'type', None) != 'web_search_tool_result':
            continue
        results = getattr(block, 'content', None)
        if not isinstance(results, list):  # エラー時は list ではなくエラーオブジェクト
            continue
        for result in results:
            url = getattr(result, 'url', None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append((getattr(result, 'title', None) or url, url))
    return sources


def _format_sources(sources, heading='## 参考URL'):
    lines = [heading]
    for title, url in sources:
        safe_title = title.replace('[', '［').replace(']', '］')
        lines.append(f'- [{safe_title}]({url})')
    return '\n'.join(lines)


def _call_api(client, params):
    """pause_turn を継続しながら呼び出し、(全 content ブロック, 最終 stop_reason) を返す"""
    user_turn = params['messages'][0]
    blocks = []
    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AiNotesError(_MSG_TIMEOUT)
        response = client.beta.messages.create(**params, timeout=remaining)
        logger.info('AI notes request_id=%s stop_reason=%s',
                    getattr(response, '_request_id', None), response.stop_reason)
        blocks.extend(response.content)
        if response.stop_reason != 'pause_turn':
            return blocks, response.stop_reason
        params = {**params, 'messages': [user_turn, {'role': 'assistant', 'content': list(blocks)}]}
    raise AiNotesError(_MSG_INCOMPLETE)


def generate_notes(crop_name, crop_type, variety_name, region, use_web_search,
                   client=None, model=None):
    """メモの Markdown 下書きを返す。失敗時は AiNotesError を送出する。"""
    model = model or current_model()
    if client is None:
        if not is_available():
            raise AiNotesError(NO_API_KEY_MESSAGE)
        # SDK の自動再試行は待ち時間と課金を倍増させるため無効化（全体の期限は _call_api で管理）
        client = anthropic.Anthropic(timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)

    params = _build_request_params(
        model, _build_user_message(crop_name, crop_type, variety_name, region), use_web_search)

    try:
        blocks, stop_reason = _call_api(client, params)
    except anthropic.APITimeoutError:
        raise AiNotesError(_MSG_TIMEOUT)
    except anthropic.APIConnectionError:
        raise AiNotesError('通信エラーです。ネットワーク接続を確認してください')
    except anthropic.AuthenticationError:
        raise AiNotesError('APIキーが無効です。.env を確認してください')
    except anthropic.PermissionDeniedError:
        raise AiNotesError('APIキーに権限がありません')
    except anthropic.RateLimitError:
        raise AiNotesError('混み合っています。しばらく待ってから再度お試しください')
    except anthropic.APIStatusError as e:
        logger.error('AI notes API error status=%s request_id=%s message=%s',
                     e.status_code, getattr(e, 'request_id', None), e.message)
        if e.status_code >= 500:
            raise AiNotesError('AIサービス側でエラーが発生しました。時間をおいてお試しください')
        raise AiNotesError(f'生成に失敗しました（詳細: {e.message}）')

    if stop_reason == 'refusal':
        raise AiNotesError('この内容は生成できませんでした')
    if stop_reason == 'max_tokens':
        raise AiNotesError(_MSG_INCOMPLETE)

    text, sources = _extract_text_and_sources(blocks)
    if not text:
        raise AiNotesError('生成結果が空でした。もう一度お試しください')
    if not use_web_search:
        return text
    if sources:
        return f'{text}\n\n{_format_sources(sources)}'
    search_sources = _extract_search_result_sources(blocks)[:MAX_SEARCH_RESULT_SOURCES]
    if search_sources:
        return f'{text}\n\n{_format_sources(search_sources, "## 参考URL（検索で見つかったページ）")}'
    return text
