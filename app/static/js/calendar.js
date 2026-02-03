// カレンダービュー用JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap Tooltipの初期化
    initTooltips();

    // キーボードナビゲーションの設定
    initKeyboardNavigation();
});

/**
 * Bootstrap Tooltipを初期化
 */
function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * キーボードナビゲーションを初期化
 * ← キーで前月、→ キーで次月に移動
 */
function initKeyboardNavigation() {
    document.addEventListener('keydown', function(e) {
        // 入力フィールドにフォーカスがある場合は無視
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        var prevLink = document.getElementById('prevMonthLink');
        var nextLink = document.getElementById('nextMonthLink');

        if (e.key === 'ArrowLeft' && prevLink) {
            // ← キーで前月
            window.location.href = prevLink.href;
        } else if (e.key === 'ArrowRight' && nextLink) {
            // → キーで次月
            window.location.href = nextLink.href;
        }
    });
}
