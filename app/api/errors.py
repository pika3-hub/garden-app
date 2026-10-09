"""API の共通レスポンス形式とエラーハンドラー"""
from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """API のエラー。エラーハンドラーが {"ok": false, "error": {...}} に変換する"""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def detail(field, reason, value=None):
    """エラー詳細1件。value は長い文字列なら切り詰める"""
    item = {'field': field, 'reason': reason}
    if value is not None:
        if isinstance(value, str) and len(value) > 100:
            value = value[:100] + '…'
        item['value'] = value
    return item


def validation_error(details):
    return ApiError(422, 'validation_error', f'入力内容に誤りがあります（{len(details)}件）', details)


def ok(data, status=200, meta=None):
    body = {'ok': True, 'data': data}
    if meta is not None:
        body['meta'] = meta
    return jsonify(body), status


def error_response(status, code, message, details=None):
    error = {'code': code, 'message': message}
    if details:
        error['details'] = details
    return jsonify({'ok': False, 'error': error}), status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(e):
        return error_response(e.status, e.code, e.message, e.details)

    @app.errorhandler(404)
    def _not_found(e):
        return error_response(404, 'not_found',
                              '指定された URL はありません。使えるリソースは GET /api/v1/meta で確認してください')

    @app.errorhandler(405)
    def _method_not_allowed(e):
        return error_response(405, 'method_not_allowed',
                              'この URL では使えないメソッドです（API からの削除はできません）')

    @app.errorhandler(413)
    def _too_large(e):
        return error_response(413, 'too_large', 'リクエストが大きすぎます（1回のリクエストは合計100MBまで）')

    @app.errorhandler(Exception)
    def _unexpected(e):
        if isinstance(e, HTTPException):
            code = 'bad_request' if e.code == 400 else 'http_error'
            return error_response(e.code or 500, code, e.description or e.name)
        current_app.logger.exception('API で想定外のエラー')
        return error_response(500, 'internal_error', 'サーバー内部でエラーが発生しました')
