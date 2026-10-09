"""外部API（エージェント連携用）。create_api_app() からのみ登録する

既存の Web 画面（認証なし）とは別アプリ・別ポートで動かし、
エージェントからは /api/v1/* にしか到達できないようにする。
"""
import logging

from flask import Blueprint, g, request

bp = Blueprint('api', __name__, url_prefix='/api/v1')
audit_logger = logging.getLogger('app.api')


def init_app(app):
    from app.api import auth, errors
    # 各モジュールは import 時に bp へルートを登録する（Blueprint 登録より前に読み込む）
    from app.api import (  # noqa: F401
        meta, crops, varieties, locations, plantings, planting_records, harvests,
    )

    errors.register_error_handlers(app)
    app.before_request(auth.require_token)
    app.after_request(_audit_log)
    app.register_blueprint(bp)


def _audit_log(response):
    """書き込み系リクエストを記録する（トークン・本文は出さない）"""
    if request.method in ('POST', 'PATCH'):
        audit_logger.info('%s %s %s -> %s id=%s', request.remote_addr, request.method,
                          request.path, response.status_code, g.get('api_target_id', '-'))
    return response
