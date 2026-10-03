import os

from waitress import serve
from app import create_app
from dotenv import load_dotenv

load_dotenv()

config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000, threads=10)