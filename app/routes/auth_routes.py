"""持ち主のログイン（パスキー）・パスキーの登録と管理・非常口の登録画面

WebAuthn のやり取りは JSON（passkey.js）。ブラウザは ArrayBuffer を base64url にして送り、
サーバーはその dict をそのまま py_webauthn の verify_* に渡す（試作で PC・iPhone・iPad で確認済みの方式）。
ログイン・登録の POST は既定で拒否の例外（app.auth.ANONYMOUS_POST_ENDPOINTS）なので、
登録はここで「ログイン中か、非常口のトークンが有効か」を確かめる。
"""
from urllib.parse import urlsplit

from flask import (Blueprint, Response, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from webauthn import (generate_authentication_options, generate_registration_options,
                      options_to_json, verify_authentication_response,
                      verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AttestationConveyancePreference,
                                      AuthenticatorSelectionCriteria,
                                      PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement,
                                      UserVerificationRequirement)

from app.auth import current_passkey, is_owner, login_owner, logout_owner
from app.models.passkey import Passkey

bp = Blueprint('auth', __name__, url_prefix='/auth')

RP_NAME = '家庭菜園'
USER_ID = b'garden-owner'
USER_NAME = 'owner'
USER_DISPLAY_NAME = '家庭菜園の持ち主'
NAME_MAX_LENGTH = 50

SESSION_LOGIN_CHALLENGE = 'webauthn_challenge'
SESSION_REGISTER_CHALLENGE = 'webauthn_registration_challenge'
SESSION_REGISTRATION_TOKEN = 'registration_token'

LOGIN_FAILED_MESSAGE = 'ログインできませんでした。もう一度お試しください'
REGISTER_FAILED_MESSAGE = 'パスキーを登録できませんでした。もう一度お試しください'
REGISTRATION_EXPIRED_MESSAGE = '登録用の URL の期限が切れたか、すでに使われています。サーバーで URL を出し直してください'


def _rp_id():
    return current_app.config['PASSKEY_RP_ID']


def _origin():
    return current_app.config['PASSKEY_ORIGIN']


def _safe_next(value):
    """同じサイトの中のパス（/ で始まり // で始まらない）だけを受ける

    ブラウザは URL の中のタブ・改行を取り除くので（"/\\t/evil" → "//evil"）、制御文字は拒否する
    """
    if not isinstance(value, str) or not value.startswith('/'):
        return '/'
    if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value):
        return '/'
    if value.startswith('//') or '\\' in value:
        return '/'
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return '/'
    return value


def _on_owner_host():
    """今の画面が編集用の入口（OWNER_BASE_URL）のホストで開かれているか

    Caddy の後ろでは waitress から見たスキームは http のままなので（ProxyFix は使わない）、
    ホスト名とポートだけで比べる。パスキーの origin の照合は PASSKEY_ORIGIN で別に行う。
    """
    owner_host = urlsplit(current_app.config['OWNER_BASE_URL']).netloc.lower()
    return request.host.lower() == owner_host


def _json_error(message, status=400):
    return jsonify({'ok': False, 'error': message}), status


def _options_response(options):
    return Response(options_to_json(options), mimetype='application/json')


def _pop_challenge(key):
    value = session.pop(key, None)
    if not value:
        return None
    try:
        return base64url_to_bytes(value)
    except (ValueError, TypeError):
        return None


def _credential_from_body(body):
    credential = body.get('credential') if isinstance(body, dict) else None
    return credential if isinstance(credential, dict) else None


def _registration_token_valid():
    token = session.get(SESSION_REGISTRATION_TOKEN)
    return bool(token) and Passkey.check_registration_token(token)


def _may_register():
    return is_owner() or _registration_token_valid()


# ---- ログイン・ログアウト ----

@bp.route('/login', methods=['GET'])
def login():
    next_url = _safe_next(request.args.get('next'))
    if is_owner():
        return redirect(next_url)
    return render_template('auth/login.html', next_url=next_url,
                           on_owner_host=_on_owner_host())


@bp.route('/login/options', methods=['POST'])
def login_options():
    options = generate_authentication_options(
        rp_id=_rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session[SESSION_LOGIN_CHALLENGE] = bytes_to_base64url(options.challenge)
    return _options_response(options)


@bp.route('/login/verify', methods=['POST'])
def login_verify():
    # チャレンジは成功・失敗にかかわらず1回で使い切る
    challenge = _pop_challenge(SESSION_LOGIN_CHALLENGE)
    body = request.get_json(silent=True)
    credential = _credential_from_body(body)
    if challenge is None or credential is None:
        return _json_error(LOGIN_FAILED_MESSAGE)

    credential_id = credential.get('id')
    if not isinstance(credential_id, str):
        return _json_error(LOGIN_FAILED_MESSAGE)
    passkey = Passkey.get_by_credential_id(credential_id)
    if passkey is None:
        return _json_error('このパスキーは登録されていません')

    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=base64url_to_bytes(passkey['public_key']),
            credential_current_sign_count=passkey['sign_count'],
            require_user_verification=True,
        )
    except Exception as e:  # py_webauthn は検証失敗を複数の例外型で知らせる
        current_app.logger.info('パスキーのログインの検証に失敗: %s', e)
        return _json_error(LOGIN_FAILED_MESSAGE)

    Passkey.record_use(passkey['id'], verified.new_sign_count)
    next_url = _safe_next(body.get('next'))
    login_owner(passkey['id'])
    return jsonify({'ok': True, 'redirect': next_url})


@bp.route('/logout', methods=['POST'])
def logout():
    logout_owner()
    flash('ログアウトしました', 'success')
    return redirect('/')


# ---- パスキーの登録（ログイン中、または非常口の URL） ----

@bp.route('/register/<token>', methods=['GET'])
def register_page(token):
    if not Passkey.check_registration_token(token):
        session.pop(SESSION_REGISTRATION_TOKEN, None)
        return render_template('auth/register.html', valid=False,
                               message=REGISTRATION_EXPIRED_MESSAGE), 404
    session[SESSION_REGISTRATION_TOKEN] = token
    return render_template('auth/register.html', valid=True)


@bp.route('/passkeys/register/options', methods=['POST'])
def register_options():
    if not _may_register():
        return _json_error('ログインが必要です', 401)

    exclude = []
    for pk in Passkey.get_all():
        try:
            exclude.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(pk['credential_id'])))
        except (ValueError, TypeError):
            continue  # 壊れた ID は除外リストに入れないだけ（登録は止めない）

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=RP_NAME,
        user_id=USER_ID,
        user_name=USER_NAME,
        user_display_name=USER_DISPLAY_NAME,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=exclude,
    )
    session[SESSION_REGISTER_CHALLENGE] = bytes_to_base64url(options.challenge)
    return _options_response(options)


@bp.route('/passkeys/register/verify', methods=['POST'])
def register_verify():
    owner = is_owner()
    token = session.get(SESSION_REGISTRATION_TOKEN)
    if not owner and not _registration_token_valid():
        return _json_error('ログインが必要です', 401)

    challenge = _pop_challenge(SESSION_REGISTER_CHALLENGE)
    body = request.get_json(silent=True)
    credential = _credential_from_body(body)
    if challenge is None or credential is None:
        return _json_error(REGISTER_FAILED_MESSAGE)

    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            require_user_verification=True,
        )
    except Exception as e:  # py_webauthn は検証失敗を複数の例外型で知らせる
        current_app.logger.info('パスキーの登録の検証に失敗: %s', e)
        return _json_error(REGISTER_FAILED_MESSAGE)

    credential_id = bytes_to_base64url(verified.credential_id)
    if Passkey.get_by_credential_id(credential_id) is not None:
        return _json_error('このパスキーはすでに登録されています')

    # 非常口: 登録の直前にトークンを使い切る。consume は DB の行を消せた1回だけ True なので、
    # 同時に2回送られても1回だけ通す
    if not owner and not Passkey.consume_registration_token(token):
        return _json_error(REGISTRATION_EXPIRED_MESSAGE, 401)
    if owner and token:
        # ログイン中でも、開いた非常口の URL は登録に使ったので使い切る（15分残さない）
        Passkey.consume_registration_token(token)
    session.pop(SESSION_REGISTRATION_TOKEN, None)

    name = (body.get('name') or '').strip()[:NAME_MAX_LENGTH] \
        if isinstance(body.get('name'), str) else ''
    if not name:
        name = f'パスキー {Passkey.count() + 1}'

    passkey_id = Passkey.create(credential_id,
                                bytes_to_base64url(verified.credential_public_key),
                                verified.sign_count, name)
    if not owner:
        login_owner(passkey_id)
    return jsonify({'ok': True, 'redirect': url_for('settings.index')})


# ---- パスキーの管理（設定画面のフォーム） ----

@bp.route('/passkeys/<int:passkey_id>/rename', methods=['POST'])
def rename_passkey(passkey_id):
    if Passkey.get_by_id(passkey_id) is None:
        flash('パスキーが見つかりません', 'danger')
        return redirect(url_for('settings.index'))
    name = (request.form.get('name') or '').strip()[:NAME_MAX_LENGTH]
    if not name:
        flash('名前を入力してください', 'danger')
        return redirect(url_for('settings.index'))
    Passkey.rename(passkey_id, name)
    flash('パスキーの名前を変更しました', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/passkeys/<int:passkey_id>/delete', methods=['POST'])
def delete_passkey(passkey_id):
    if Passkey.get_by_id(passkey_id) is None:
        flash('パスキーが見つかりません', 'danger')
        return redirect(url_for('settings.index'))
    own = current_passkey()
    Passkey.delete(passkey_id)
    if own is not None and own['id'] == passkey_id:
        logout_owner()
        flash('パスキーを削除しました。このパスキーでのログインは終わりました', 'success')
    else:
        flash('パスキーを削除しました', 'success')
    return redirect(url_for('settings.index'))
