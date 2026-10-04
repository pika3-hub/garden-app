from markupsafe import Markup

from app.utils.markdown_render import render_markdown


def test_heading_and_list():
    html = render_markdown('## 栽培のコツ\n\n- 水やり\n- 追肥')
    assert '<h2>栽培のコツ</h2>' in html
    assert '<li>水やり</li>' in html


def test_single_newline_becomes_br():
    """既存のプレーンテキストのメモも改行が保たれる"""
    html = render_markdown('1行目\n2行目')
    assert '1行目<br />' in html
    assert '2行目' in html


def test_raw_html_is_escaped():
    html = render_markdown('<script>alert(1)</script>')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_javascript_link_is_not_rendered():
    html = render_markdown('[x](javascript:alert(1))')
    assert 'href="javascript:' not in html


def test_link_opens_in_new_tab():
    html = render_markdown('[参考](https://example.com)')
    assert 'href="https://example.com"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html


def test_table_and_strikethrough():
    html = render_markdown('| a | b |\n|---|---|\n| 1 | 2 |\n\n~~取消~~')
    assert '<table>' in html
    assert '<s>取消</s>' in html


def test_empty_values():
    assert render_markdown(None) == ''
    assert render_markdown('') == ''


def test_returns_markup():
    assert isinstance(render_markdown('a'), Markup)


def test_filter_registered(app):
    assert app.jinja_env.filters['markdown'] is render_markdown


def test_crop_detail_renders_markdown(app, client):
    from app.models.crop import Crop
    with app.app_context():
        crop_id = Crop.create({'name': 'トマト', 'crop_type': '果菜類',
                               'notes': '## 植え付け時期\n\n- 5月上旬'})
    res = client.get(f'/crops/{crop_id}')
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert '<h2>植え付け時期</h2>' in body
    assert '<li>5月上旬</li>' in body
