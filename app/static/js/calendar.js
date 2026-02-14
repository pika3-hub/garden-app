// カレンダービュー用JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap Tooltipの初期化
    initTooltips();

    // キーボードナビゲーションの設定
    initKeyboardNavigation();

    // モバイル用日付詳細モーダルの設定
    initMobileDayModal();
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
 * モバイル用日付詳細モーダルを初期化
 * スマートフォン幅でセルをタップするとモーダルでアイコンを表示
 */
function initMobileDayModal() {
    var cells = document.querySelectorAll('.calendar-cell.has-data');
    var modalEl = document.getElementById('dayDetailModal');
    if (!modalEl) return;

    // <main class="page-with-sky"> の z-index:0 がスタッキングコンテキストを
    // 生成し、backdrop(body直下)の背面にモーダルが隠れるため、body直下に移動
    document.body.appendChild(modalEl);

    var modal = new bootstrap.Modal(modalEl);
    var titleEl = document.getElementById('dayDetailModalLabel');
    var iconsContainer = document.getElementById('dayDetailIcons');

    cells.forEach(function(cell) {
        cell.addEventListener('click', function(e) {
            // デスクトップ幅では無効
            if (window.innerWidth > 575.98) return;

            e.preventDefault();

            // 日付を取得してフォーマット
            var dateStr = cell.getAttribute('data-date');
            if (!dateStr) return;
            var parts = dateStr.split('-');
            var year = parseInt(parts[0], 10);
            var month = parseInt(parts[1], 10);
            var day = parseInt(parts[2], 10);
            titleEl.textContent = year + '年' + month + '月' + day + '日';

            // セル内のアイコンをクローンしてモーダルに挿入
            iconsContainer.innerHTML = '';
            var dayIcons = cell.querySelector('.day-icons');
            if (dayIcons) {
                var clone = dayIcons.cloneNode(true);
                iconsContainer.appendChild(clone);
            }

            modal.show();
        });
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
