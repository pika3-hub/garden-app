/**
 * パスキー（WebAuthn）でのログインと登録
 *
 * - data-passkey-action="login" / "register" のボタンに付く
 * - サーバーの options（py_webauthn の options_to_json）の base64url を ArrayBuffer にして
 *   navigator.credentials.get / create を呼び、結果を base64url の JSON で送り返す
 * - メッセージは同じカード内の [data-passkey-message]（Bootstrap の alert）に出す
 * - X-CSRFToken は csrf.js が fetch に自動で付ける
 */
(function () {
    'use strict';

    var LOGIN_OPTIONS_URL = '/auth/login/options';
    var LOGIN_VERIFY_URL = '/auth/login/verify';
    var REGISTER_OPTIONS_URL = '/auth/passkeys/register/options';
    var REGISTER_VERIFY_URL = '/auth/passkeys/register/verify';

    function b64urlToBuffer(value) {
        var b64 = value.replace(/-/g, '+').replace(/_/g, '/');
        while (b64.length % 4) b64 += '=';
        var bin = atob(b64);
        var bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return bytes;
    }

    function bufferToB64url(buffer) {
        if (!buffer) return null;
        var bytes = new Uint8Array(buffer);
        var bin = '';
        for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
        return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    function findMessage(button) {
        var scope = button.closest('.card-body') || document;
        return scope.querySelector('[data-passkey-message]');
    }

    function showMessage(button, kind, text) {
        var el = findMessage(button);
        if (!el) return;
        el.className = 'alert alert-' + kind;
        el.textContent = text;
    }

    function clearMessage(button) {
        var el = findMessage(button);
        if (el) {
            el.className = 'alert d-none';
            el.textContent = '';
        }
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(body || {})
        }).then(function (resp) {
            return resp.json().catch(function () { return {}; }).then(function (data) {
                if (!resp.ok || data.ok === false) {
                    throw new Error(data.error || ('通信に失敗しました（' + resp.status + '）'));
                }
                return data;
            });
        });
    }

    function describeError(err) {
        if (err && err.name === 'NotAllowedError') {
            return 'キャンセルされたか、時間切れになりました。もう一度お試しください';
        }
        if (err && err.name === 'InvalidStateError') {
            return 'この端末のパスキーはすでに登録されています';
        }
        return (err && err.message) || 'エラーが発生しました';
    }

    function login(button) {
        return postJson(LOGIN_OPTIONS_URL).then(function (options) {
            options.challenge = b64urlToBuffer(options.challenge);
            (options.allowCredentials || []).forEach(function (c) { c.id = b64urlToBuffer(c.id); });
            return navigator.credentials.get({ publicKey: options });
        }).then(function (cred) {
            return postJson(LOGIN_VERIFY_URL, {
                credential: {
                    id: cred.id,
                    rawId: bufferToB64url(cred.rawId),
                    type: cred.type,
                    response: {
                        clientDataJSON: bufferToB64url(cred.response.clientDataJSON),
                        authenticatorData: bufferToB64url(cred.response.authenticatorData),
                        signature: bufferToB64url(cred.response.signature),
                        userHandle: bufferToB64url(cred.response.userHandle)
                    },
                    clientExtensionResults: cred.getClientExtensionResults(),
                    authenticatorAttachment: cred.authenticatorAttachment
                },
                next: button.getAttribute('data-next') || '/'
            });
        });
    }

    function register(button) {
        var scope = button.closest('.card-body') || document;
        var nameInput = scope.querySelector('[data-passkey-name]');
        var name = nameInput ? nameInput.value.trim() : '';
        return postJson(REGISTER_OPTIONS_URL).then(function (options) {
            options.challenge = b64urlToBuffer(options.challenge);
            options.user.id = b64urlToBuffer(options.user.id);
            (options.excludeCredentials || []).forEach(function (c) { c.id = b64urlToBuffer(c.id); });
            return navigator.credentials.create({ publicKey: options });
        }).then(function (cred) {
            var transports = typeof cred.response.getTransports === 'function'
                ? cred.response.getTransports() : [];
            return postJson(REGISTER_VERIFY_URL, {
                credential: {
                    id: cred.id,
                    rawId: bufferToB64url(cred.rawId),
                    type: cred.type,
                    response: {
                        clientDataJSON: bufferToB64url(cred.response.clientDataJSON),
                        attestationObject: bufferToB64url(cred.response.attestationObject),
                        transports: transports
                    },
                    clientExtensionResults: cred.getClientExtensionResults(),
                    authenticatorAttachment: cred.authenticatorAttachment
                },
                name: name
            });
        });
    }

    function init() {
        var buttons = document.querySelectorAll('[data-passkey-action]');
        if (!buttons.length) return;

        var reason = null;
        if (!window.isSecureContext) {
            reason = 'この画面は HTTPS ではないため、パスキーを使えません。編集用の URL（https://）で開いてください';
        } else if (!window.PublicKeyCredential || !navigator.credentials) {
            reason = 'このブラウザはパスキーに対応していません';
        }

        Array.prototype.forEach.call(buttons, function (button) {
            if (reason) {
                button.disabled = true;
                showMessage(button, 'warning', reason);
                return;
            }
            button.addEventListener('click', function () {
                var action = button.getAttribute('data-passkey-action');
                var run = action === 'login' ? login : register;
                button.disabled = true;
                clearMessage(button);
                run(button).then(function (data) {
                    showMessage(button, 'success',
                        action === 'login' ? 'ログインしました' : 'パスキーを登録しました');
                    window.location.href = data.redirect || '/';
                }).catch(function (err) {
                    showMessage(button, 'danger', describeError(err));
                    button.disabled = false;
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
