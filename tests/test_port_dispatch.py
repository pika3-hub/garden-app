import threading
import urllib.request

from waitress import create_server

from app.port_dispatch import PortDispatcher


def _app(body):
    def wsgi(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [body]
    return wsgi


def test_dispatches_by_server_port():
    d = PortDispatcher(_app(b'web'), {5001: _app(b'api')})
    calls = []
    sr = lambda status, headers: calls.append(status)  # noqa: E731
    assert d({'SERVER_PORT': '5001'}, sr) == [b'api']
    assert d({'SERVER_PORT': '5000'}, sr) == [b'web']
    assert d({}, sr) == [b'web']


def test_waitress_listening_port_selects_app():
    """実際の waitress で、待受ポートごとに別アプリが応答することを確かめる（安全性の要）"""
    holder = {}
    server = create_server(lambda e, s: holder['app'](e, s),
                           listen='127.0.0.1:0 127.0.0.1:0', threads=2)
    (_, web_port), (_, api_port) = server.effective_listen
    holder['app'] = PortDispatcher(_app(b'web'), {api_port: _app(b'api')})
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        assert urllib.request.urlopen(f'http://127.0.0.1:{api_port}/', timeout=5).read() == b'api'
        assert urllib.request.urlopen(f'http://127.0.0.1:{web_port}/', timeout=5).read() == b'web'
    finally:
        server.close()
