import os

from dotenv import load_dotenv
from waitress import serve

# app/config.py は import 時に環境変数を読むため、app より先に .env を読み込む
load_dotenv()

from app import create_app  # noqa: E402

config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == "__main__":
    # 既定はこのPCのみ。スマホ等 LAN 内の端末から使う場合は .env に HOST=0.0.0.0 を書く
    host = os.environ.get('HOST', '127.0.0.1')
    serve(app, host=host, port=5000, threads=10)