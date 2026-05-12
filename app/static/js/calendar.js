// カレンダービュー用JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap Tooltipの初期化
    initTooltips();

    // キーボードナビゲーションの設定
    initKeyboardNavigation();

    // スワイプナビゲーション（モバイル）
    initSwipeNavigation();

    // アイコンクリックでモーダル表示
    initCalendarIconClick();

    // エンティティタイプフィルター
    initEntityFilter();
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
            var iconHtml = '';
            if (item.icon_path) {
                iconHtml = '<img src="/static/images/crop_icons/' + escapeHtml(item.icon_path) + '"' +
                    ' alt="" class="crop-icon-inline"' +
                    ' style="border-color: ' + escapeHtml(item.image_color || '#4CAF50') + ';">';
            }
            return '<a href="' + item.url + '" class="list-group-item list-group-item-action">' +
                   iconHtml + escapeHtml(item.label) + '</a>';
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
 * エンティティタイプフィルター
 * バッジをクリックして特定エンティティのデータをチップ表示に切替
 */
function initEntityFilter() {
    var filterBtns = document.querySelectorAll('.calendar-entity-filter');
    var calendarTable = document.querySelector('.calendar-table');
    if (!filterBtns.length) return;

    var activeEntityType = null;

    filterBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var entityType = this.dataset.entityType;
            if (activeEntityType === entityType) {
                clearFilter();
                activeEntityType = null;
            } else {
                clearFilter();
                activeEntityType = entityType;
                applyFilter(entityType);
            }
        });
    });

    function applyFilter(entityType) {
        if (calendarTable) calendarTable.classList.add('filter-active');

        filterBtns.forEach(function(btn) {
            var isActive = btn.dataset.entityType === entityType;
            btn.classList.toggle('calendar-entity-filter-active', isActive);
            btn.classList.toggle('calendar-entity-filter-inactive', !isActive);
        });

        document.querySelectorAll('.calendar-icon-btn').forEach(function(btn) {
            if (btn.dataset.entityType === entityType) {
                renderChips(btn);
            }
            btn.style.display = 'none';
        });
    }

    function clearFilter() {
        if (calendarTable) calendarTable.classList.remove('filter-active');

        document.querySelectorAll('.calendar-icon-btn').forEach(function(btn) {
            btn.style.display = '';
        });
        document.querySelectorAll('.day-chips').forEach(function(c) {
            c.innerHTML = '';
        });
        filterBtns.forEach(function(btn) {
            btn.classList.remove('calendar-entity-filter-active',
                                 'calendar-entity-filter-inactive');
        });
    }

    function renderChips(iconBtn) {
        var items;
        try { items = JSON.parse(iconBtn.dataset.items); } catch(e) { return; }

        // デスクトップ(.calendar-cell)・モバイル(td.mobile-day-data)両方に対応するため
        // 親の .day-icons の次の兄弟要素 .day-chips を探す
        var dayIconsEl = iconBtn.closest('.day-icons');
        if (!dayIconsEl) return;
        var container = dayIconsEl.nextElementSibling;
        if (!container) return;

        items.forEach(function(item) {
            var a = document.createElement('a');
            a.href = item.url;
            a.className = 'cal-chip';

            if (item.icon_path) {
                var img = document.createElement('img');
                img.src = '/static/images/crop_icons/' + escapeHtml(item.icon_path);
                img.alt = '';
                img.className = 'cal-chip-icon';
                img.style.borderColor = item.image_color || '#4CAF50';
                a.appendChild(img);
            }

            var label = document.createElement('span');
            label.className = 'cal-chip-label';
            label.textContent = item.label;
            a.appendChild(label);

            container.appendChild(a);
        });
    }
}

/**
 * スワイプナビゲーションを初期化（モバイル用）
 * 右スワイプで前月、左スワイプで次月に移動
 */
function initSwipeNavigation() {
    var startX = 0;
    var startY = 0;
    var THRESHOLD = 50;

    document.addEventListener('touchstart', function(e) {
        startX = e.changedTouches[0].clientX;
        startY = e.changedTouches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', function(e) {
        var deltaX = e.changedTouches[0].clientX - startX;
        var deltaY = e.changedTouches[0].clientY - startY;

        // 縦スクロールより横移動が大きい場合のみ発動
        if (Math.abs(deltaX) < THRESHOLD || Math.abs(deltaX) < Math.abs(deltaY)) return;

        var prevLink = document.getElementById('prevMonthLink');
        var nextLink = document.getElementById('nextMonthLink');

        if (deltaX > 0 && prevLink) {
            window.location.href = prevLink.href;
        } else if (deltaX < 0 && nextLink) {
            window.location.href = nextLink.href;
        }
    }, { passive: true });
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
