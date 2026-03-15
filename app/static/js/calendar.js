// カレンダービュー用JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap Tooltipの初期化
    initTooltips();

    // キーボードナビゲーションの設定
    initKeyboardNavigation();

    // アイコンクリックでモーダル表示
    initCalendarIconClick();
});

/**
 * Bootstrap Tooltipを初期化
 */
function initTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('.calendar-icon-btn[title]'));
    tooltipTriggerList.forEach(function(el) {
        new bootstrap.Tooltip(el, { trigger: 'hover focus' });
    });
}

/**
 * アイコンボタンクリックでモーダルを表示
 */
function initCalendarIconClick() {
    var modalEl = document.getElementById('calendarModal');
    if (!modalEl) return;

    // <main class="page-with-sky"> の z-index:0 がスタッキングコンテキストを
    // 生成し、backdrop(body直下)の背面にモーダルが隠れるため、body直下に移動
    document.body.appendChild(modalEl);

    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.calendar-icon-btn');
        if (!btn) return;
        e.preventDefault();

        var typeLabel = btn.dataset.typeLabel;
        var dateStr = btn.dataset.date;
        var items = JSON.parse(btn.dataset.items);

        // モーダルタイトル: "2026年3月15日 ― 作物"
        var parts = dateStr.split('-');
        var y = parseInt(parts[0], 10);
        var m = parseInt(parts[1], 10);
        var d = parseInt(parts[2], 10);
        document.getElementById('calendarModalTitle').textContent =
            y + '年' + m + '月' + d + '日 ― ' + typeLabel;

        // モーダルボディ: アイテムリスト
        var body = document.getElementById('calendarModalBody');
        body.innerHTML = items.map(function(item) {
            return '<a href="' + item.url + '" class="list-group-item list-group-item-action">' +
                   escapeHtml(item.label) + '</a>';
        }).join('');

        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    });
}

/**
 * HTML特殊文字をエスケープ
 */
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
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
