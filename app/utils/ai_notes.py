"""作物・品種メモの AI 下書き生成（Claude API）

Flask に依存しない。APIキーは環境変数 ANTHROPIC_API_KEY、
モデルは ANTHROPIC_MODEL（許可リストのみ）で指定する。
"""
import logging
import os
import re
import time
from urllib.parse import unquote, urlsplit

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'claude-opus-5-5'

# 許可するモデルと、モーダルに表示する目安（1ドル=150円で概算）。
# fallbacks: サーバー側フォールバック（拒否時に別モデルで再実行）に対応しているか
# web_search: 使う Web 検索ツールの版（20260209 は Opus / Sonnet のみ公式対応）
MODEL_INFO = {
    'claude-opus-5-5': {
        'label': 'Claude Opus 5.5',
        'estimate_off': '10〜30秒・約10円',
        'estimate_on': '30〜90秒・約35〜40円',
        'fallbacks': True,
        'web_search': 'web_search_20260209',
    },
    'claude-sonnet-5-5': {
        'label': 'Claude Sonnet 5.5',
        'estimate_off': '10〜20秒・約5円',
        'estimate_on': '30〜60秒・約20円',
        'fallbacks': True,
        'web_search': 'web_search_20260209',
    },
    'claude-haiku-5-5': {
        'label': 'Claude Haiku 5.5',
        'estimate_off': '5〜15秒・1円未満',
        'estimate_on': '10〜30秒・約2〜5円',
        'fallbacks': False,
        'web_search': 'web_search_20250305',
    },
}

MAX_TOKENS = 16000
REQUEST_TIMEOUT_SECONDS = 180.0
MAX_PAUSE_CONTINUATIONS = 3
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
WEB_SEARCH_TOOL = {
    'name': 'web_search',
    'max_uses': 5,
    'user_location': {'type': 'approximate', 'country': 'JP'},
}

NO_API_KEY_MESSAGE = 'AI機能を使うには .env に ANTHROPIC_API_KEY を設定してください'
_MSG_INCOMPLETE = '生成が途中で終わりました。もう一度お試しください'
_MSG_TIMEOUT = '時間内に生成が終わりませんでした。もう一度お試しください'

# 見出し構成を変えたら docs/api/hermes-skill/SKILL.md の「作物・品種のメモの書き方」も合わせる
SYSTEM_PROMPT = """あなたは日本の家庭菜園に詳しいアドバイザーです。
ユーザーが指定した作物（または品種）について、家庭菜園の栽培メモの下書きを作成します。

# 出力ルール
- 次の見出し構成の Markdown だけを出力する。前置き・後書き・挨拶は書かない。
- 時期はユーザーの地域・栽培環境を基準に書く。種まきと苗の植え付けを区別する。
- 品種が指定された場合、親作物の一般論ではなく、その品種固有の特徴（味・サイズ・耐病性・草勢など）を優先して書く。
- 確かでない情報は推測で書かず「情報なし」と書く。
- 本文中にURLや出典は書かない。

# Web検索を使う場合
- 家庭菜園の話題だと分かるよう、作物名に「栽培」「育て方」「野菜」などの語を付けて検索する（同じ名前の別の物のページを避ける）。
- 最後に「## 参考URL」の見出しを足し、本文を書くのに実際に参考にしたページだけを `- [ページのタイトル](URL)` の形で並べる。URLは検索結果に出てきたものをそのまま書き、推測で作らない。

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


def _build_user_message(crop_name, crop_type, variety_name, region, use_web_search):
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
    if use_web_search:
        # 実API確認で、Sonnet が Web 検索を使わずに書いたことがあったため明示する
        lines.append('Web検索で調べてから書いてください。')
    return '\n'.join(lines)


def _build_request_params(model, user_message, use_web_search):
    info = MODEL_INFO[model]
    params = {
        'model': model,
        'max_tokens': MAX_TOKENS,
        'system': SYSTEM_PROMPT,
        'output_config': {'effort': 'medium'},
        'messages': [{'role': 'user', 'content': user_message}],
    }
    if info['fallbacks']:
        params['betas'] = [FALLBACK_BETA]
        params['fallbacks'] = 'default'
    if use_web_search:
        params['tools'] = [{'type': info['web_search'], **WEB_SEARCH_TOOL}]
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
    """web_search_tool_result の検索結果から (title, url) を重複なしで集める"""
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


_SOURCES_HEADING_RE = re.compile(r'^## 参考URL[^\n]*$', re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r'^## ', re.MULTILINE)
# URL 中の括弧（例: カブ_(植物)）を残すため、閉じ括弧の後が空白か行末のものを終わりとみなす
_MD_LINK_URL_RE = re.compile(r'\]\((https?://\S+?)\)(?=\s|$)')
_BARE_URL_RE = re.compile(r'https?://\S+')


def _split_sources_section(text):
    """本文から「## 参考URL」の節を取り除き、(本文, 節に書かれた URL のリスト) を返す"""
    urls = []
    while (heading := _SOURCES_HEADING_RE.search(text)):
        next_heading = _NEXT_HEADING_RE.search(text, heading.end())
        end = next_heading.start() if next_heading else len(text)
        for line in text[heading.end():end].splitlines():
            urls.extend(_MD_LINK_URL_RE.findall(line) or _BARE_URL_RE.findall(line))
        text = text[:heading.start()] + text[end:]
    return text.strip(), urls


def _normalize_url(url):
    """照合用のキー。http/https・ホストの大小・末尾の /・%エンコードの有無は無視し、クエリは区別する"""
    parts = urlsplit(unquote(url.strip()))
    return parts.netloc.lower(), parts.path.rstrip('/'), parts.query


def _verify_sources(urls, known_sources):
    """AI が書いた URL のうち、検索結果・citations に実在するものだけを (title, url) で返す。

    web_search_20260209 は動的フィルタリングのため citations が付かないことが多く、
    参考にしたページは AI に書かせている。架空の URL を消すために照合し、
    タイトルと URL の表記は検索結果側のものを使う。
    """
    known = {}
    for title, url in known_sources:
        known.setdefault(_normalize_url(url), (title, url))
    sources = []
    seen = set()
    for url in urls:
        key = _normalize_url(url)
        if key in known and key not in seen:
            seen.add(key)
            sources.append(known[key])
    return sources


def _format_sources(sources):
    lines = ['## 参考URL']
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
        model, _build_user_message(crop_name, crop_type, variety_name, region, use_web_search),
        use_web_search)

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

    text, cited = _extract_text_and_sources(blocks)
    text, written_urls = _split_sources_section(text)
    if not text:
        raise AiNotesError('生成結果が空でした。もう一度お試しください')
    # AI が参考URLを書かなかったときは、実際に引用された citations を使う
    sources = _verify_sources(written_urls, _extract_search_result_sources(blocks) + cited) or cited
    if sources:
        return f'{text}\n\n{_format_sources(sources)}'
    return text
