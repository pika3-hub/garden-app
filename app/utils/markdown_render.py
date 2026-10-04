"""メモ欄の Markdown を HTML に変換する（Jinja フィルター `markdown`）"""
from markdown_it import MarkdownIt
from markupsafe import Markup

# html=False: 生の HTML はエスケープされる（javascript: などの危険な URL も既定でリンク化されない）
# breaks=True: 単独の改行も <br> にし、既存のプレーンテキストのメモの見た目を保つ
_md = (
    MarkdownIt('commonmark', {'html': False, 'breaks': True})
    .enable('table')
    .enable('strikethrough')
)


def _render_link_open(renderer, tokens, idx, options, env):
    """リンクは別タブで開く"""
    tokens[idx].attrSet('target', '_blank')
    tokens[idx].attrSet('rel', 'noopener noreferrer')
    return renderer.renderToken(tokens, idx, options, env)


_md.add_render_rule('link_open', _render_link_open)


def render_markdown(text):
    """Markdown テキストを安全な HTML（Markup）に変換する。空なら空文字を返す"""
    if not text:
        return Markup('')
    return Markup(_md.render(text))
