"""疎通確認・選択肢一覧・名前検索"""
from app.api import bp
from app.api.errors import ok


@bp.get('/health')
def health():
    return ok({'status': 'ok'})
