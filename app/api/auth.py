"""Bearer トークン認証"""
import hmac

from flask import current_app, request

from app.api.errors import ApiError

MIN_TOKEN_LENGTH = 32


def token_is_valid(token):
    return bool(token) and len(token) >= MIN_TOKEN_LENGTH


def require_token():
    """before_request: Authorization: Bearer <API_TOKEN> を必須にする"""
    expected = current_app.config.get('API_TOKEN') or ''
    scheme, _, given = request.headers.get('Authorization', '').partition(' ')
    given = given.strip()
    if (scheme.lower() != 'bearer' or not given or not expected
            or not hmac.compare_digest(given.encode(), expected.encode())):
        raise ApiError(401, 'unauthorized', '認証に失敗しました。Authorization: Bearer <トークン> を付けてください')
