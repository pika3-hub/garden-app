import os
from dotenv import load_dotenv

# app/config.py は import 時に環境変数を読むため、app より先に .env を読み込む
load_dotenv()

from app import create_app  # noqa: E402

# 環境変数から設定を選択（デフォルトは開発環境）
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    # 既定はこのPCのみ。debug=True のデバッガは任意のコードを実行できるため、
    # LAN 内の端末から使う場合だけ .env に HOST=0.0.0.0 を書く
    host = os.environ.get('HOST', '127.0.0.1')
    app.run(host=host, port=5000, debug=True)
