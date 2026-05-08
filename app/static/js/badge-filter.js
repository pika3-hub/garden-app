/**
 * badge-filter.js — 一覧画面の種類バッジフィルター（共通）
 *
 * ■ レガシーモード（作物一覧・場所一覧）:
 *   #badge-filter-container  … バッジ群の親
 *   .badge-filter            … 各バッジ（data-type="種類名"）
 *   [data-filter-type]       … フィルタ対象のカードラッパー
 *
 * ■ マルチグループモード（植え付け一覧・収穫一覧）:
 *   .badge-filter-group[data-filter-key]  … 各グループ（種類・場所等）
 *   .badge-filter            … 各バッジ（data-type="値"）
 *   [data-filter-card]       … フィルタ対象のカードラッパー
 *   data-filter-group-{key}  … カードの各グループ値
 *   グループ間AND・グループ内OR
 *
 * 共通:
 *   #filter-count            … 件数表示（data-suffix="件の作物" 等）
 *   #filter-empty-msg        … 0件時メッセージ（初期 display:none）
 */
document.addEventListener('DOMContentLoaded', function () {
    var groups = document.querySelectorAll('.badge-filter-group');

    if (groups.length > 0) {
        initMultiGroup(groups);
    } else {
        initLegacy();
    }

    /** レガシーモード（単一グループ） */
    function initLegacy() {
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

            // グループ見出し: 可視アイテムが0件のセクションを非表示
            var dateGroups = document.querySelectorAll('.date-group');
            dateGroups.forEach(function (group) {
                var visible = false;
                group.querySelectorAll('[data-filter-type]').forEach(function (item) {
                    if (item.style.display !== 'none') visible = true;
                });
                group.style.display = visible ? '' : 'none';
            });
        }
    }

    /** マルチグループモード（グループ間AND・グループ内OR） */
    function initMultiGroup(groups) {
        var items = document.querySelectorAll('[data-filter-card]');
        var countEl = document.getElementById('filter-count');
        var suffix = countEl ? countEl.dataset.suffix : '';
        var emptyMsg = document.getElementById('filter-empty-msg');

        // グループごとの選択状態: { key: Set }
        var selectedByGroup = {};
        // data-filter-key → dataset属性名のマッピング: { key: datasetAttrName }
        var datasetAttrMap = {};

        groups.forEach(function (group) {
            var key = group.dataset.filterKey;
            selectedByGroup[key] = new Set();
            // data-filter-group-crop-type → dataset.filterGroupCropType
            datasetAttrMap[key] = 'filterGroup' + key.charAt(0).toUpperCase() + key.slice(1);

            var badges = group.querySelectorAll('.badge-filter');
            badges.forEach(function (badge) {
                badge.addEventListener('click', function () {
                    var value = this.dataset.type;
                    if (selectedByGroup[key].has(value)) {
                        selectedByGroup[key].delete(value);
                        this.classList.remove('badge-filter-active');
                        this.classList.add('badge-filter-inactive');
                    } else {
                        selectedByGroup[key].add(value);
                        this.classList.add('badge-filter-active');
                        this.classList.remove('badge-filter-inactive');
                    }
                    applyMultiFilter();
                });
            });
        });

        function applyMultiFilter() {
            var visibleCount = 0;
            items.forEach(function (item) {
                var show = true;
                for (var key in selectedByGroup) {
                    var selected = selectedByGroup[key];
                    if (selected.size === 0) continue;
                    var rawValue = item.dataset[datasetAttrMap[key]] || '';
                    var values = rawValue ? rawValue.split(',') : [];
                    if (!values.some(function(v) { return selected.has(v); })) {
                        show = false;
                        break;
                    }
                }
                item.style.display = show ? '' : 'none';
                if (show) visibleCount++;
            });
            if (countEl) {
                countEl.textContent = visibleCount + suffix;
            }
            if (emptyMsg) {
                emptyMsg.style.display = visibleCount === 0 ? '' : 'none';
            }

            // グループ見出し: 可視アイテムが0件のセクションを非表示
            var dateGroups = document.querySelectorAll('.date-group');
            dateGroups.forEach(function (group) {
                var visible = false;
                group.querySelectorAll('[data-filter-card]').forEach(function (item) {
                    if (item.style.display !== 'none') visible = true;
                });
                group.style.display = visible ? '' : 'none';
            });
        }
    }
});
