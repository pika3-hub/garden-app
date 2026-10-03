import os
from app import create_app
from dotenv import load_dotenv

load_dotenv()

# 環境変数から設定を選択（デフォルトは開発環境）
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
