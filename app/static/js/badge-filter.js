/**
 * badge-filter.js — 一覧画面の種類バッジフィルター（共通）
 *
 * 規約:
 *   #badge-filter-container  … バッジ群の親
 *   .badge-filter            … 各バッジ（data-type="種類名"）
 *   [data-filter-type]       … フィルタ対象のカードラッパー
 *   #filter-count            … 件数表示（data-suffix="件の作物" 等）
 *   #filter-empty-msg        … 0件時メッセージ（初期 display:none）
 */
document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('badge-filter-container');
    if (!container) return;

    var badges = container.querySelectorAll('.badge-filter');
    var items = document.querySelectorAll('[data-filter-type]');
    var countEl = document.getElementById('filter-count');
    var suffix = countEl ? countEl.dataset.suffix : '';
    var emptyMsg = document.getElementById('filter-empty-msg');
    var selectedTypes = new Set();

    badges.forEach(function (badge) {
        badge.addEventListener('click', function () {
            var type = this.dataset.type;
            if (selectedTypes.has(type)) {
                selectedTypes.delete(type);
                this.classList.remove('badge-filter-active');
                this.classList.add('badge-filter-inactive');
            } else {
                selectedTypes.add(type);
                this.classList.add('badge-filter-active');
                this.classList.remove('badge-filter-inactive');
            }
            applyFilter();
        });
    });

    function applyFilter() {
        var visibleCount = 0;
        items.forEach(function (item) {
            var types = item.dataset.filterType ? item.dataset.filterType.split(',') : [];
            var show = selectedTypes.size === 0 || types.some(function (t) { return selectedTypes.has(t); });
            item.style.display = show ? '' : 'none';
            if (show) visibleCount++;
        });
        if (countEl) {
            countEl.textContent = visibleCount + suffix;
        }
        if (emptyMsg) {
            emptyMsg.style.display = visibleCount === 0 ? '' : 'none';
        }
    }
});
