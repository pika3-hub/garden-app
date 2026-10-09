import logging
import os

from dotenv import load_dotenv
from waitress import serve

# app/config.py は import 時に環境変数を読むため、app より先に .env を読み込む
load_dotenv()

from app import create_app, create_api_app  # noqa: E402
from app.port_dispatch import PortDispatcher  # noqa: E402

config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)


def build_api_app():
    """API_TOKEN が正しく設定されていれば API アプリを返す。無ければ None（Web 画面のみで起動）"""
    try:
        return create_api_app(config_name)
    except RuntimeError as e:
        logging.getLogger(__name__).warning('%s（Web 画面のみ起動します）', e)
        return None


if __name__ == "__main__":
    # 既定はこのPCのみ。スマホ等 LAN 内の端末から使う場合は .env に HOST=0.0.0.0 を書く
    host = os.environ.get('HOST', '127.0.0.1')
    api_app = build_api_app()
    if api_app is None:
        serve(app, host=host, port=5000, threads=10)
    else:
        # API は別ポート。Ubuntu 移設後は API_HOST=127.0.0.1（同じPCのエージェントだけが使う）
        api_host = os.environ.get('API_HOST', '127.0.0.1')
        api_port = int(os.environ.get('API_PORT', '5001'))
        serve(PortDispatcher(app, {api_port: api_app}),
              listen=f'{host}:5000 {api_host}:{api_port}', threads=10)
