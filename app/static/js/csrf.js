/**
 * CSRF トークンを POST に自動で付ける（base.html で他のアプリの JS より前に読み込む）
 *
 * - トークンは <meta name="csrf-token" content="..."> から読む
 * - method="post" のフォームに hidden の csrf_token を入れる（読み込み時と、送信の直前）
 * - 同じオリジン宛ての GET/HEAD 以外の fetch に X-CSRFToken ヘッダーを足す
 */
(function () {
    'use strict';

    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute('content') : '';
    if (!token) return;

    function isPostForm(form) {
        return form && form.tagName === 'FORM' &&
            (form.getAttribute('method') || '').toLowerCase() === 'post';
    }

    function addTokenInput(form) {
        if (!isPostForm(form)) return;
        var input = form.querySelector('input[name="csrf_token"]');
        if (!input) {
            input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrf_token';
            form.appendChild(input);
        }
        input.value = token;
    }

    function addToAllForms() {
        Array.prototype.forEach.call(document.querySelectorAll('form'), addTokenInput);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addToAllForms);
    } else {
        addToAllForms();
    }

    // 後から作られたフォーム用（キャプチャで、各ページの submit 処理より先に入れる）
    document.addEventListener('submit', function (e) {
        addTokenInput(e.target);
    }, true);

    function isSameOrigin(url) {
        try {
            return new URL(url, window.location.href).origin === window.location.origin;
        } catch (err) {
            return false;
        }
    }

    var originalFetch = window.fetch;
    if (typeof originalFetch !== 'function') return;

    window.fetch = function (input, init) {
        var isRequest = typeof Request !== 'undefined' && input instanceof Request;
        var url = isRequest ? input.url : String(input);
        var method = ((init && init.method) || (isRequest ? input.method : 'GET')).toUpperCase();

        if (method === 'GET' || method === 'HEAD' || !isSameOrigin(url)) {
            return originalFetch.call(this, input, init);
        }

        var newInit = Object.assign({}, init || {});
        var headers = new Headers((init && init.headers) || (isRequest ? input.headers : undefined));
        if (!headers.has('X-CSRFToken')) {
            headers.set('X-CSRFToken', token);
        }
        newInit.headers = headers;
        return originalFetch.call(this, input, newInit);
    };
})();
