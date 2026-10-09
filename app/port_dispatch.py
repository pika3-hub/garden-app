"""1つの waitress で複数ポートを待ち受け、ポートごとに WSGI アプリを振り分ける

waitress は environ['SERVER_PORT'] に「接続を受けた待受ソケットのポート」を入れる
（Host ヘッダーではない）ため、クライアントが偽装できない。
"""


class PortDispatcher:
    def __init__(self, default_app, port_apps):
        self.default_app = default_app
        self.port_apps = {str(port): app for port, app in port_apps.items()}

    def __call__(self, environ, start_response):
        app = self.port_apps.get(str(environ.get('SERVER_PORT')), self.default_app)
        return app(environ, start_response)
