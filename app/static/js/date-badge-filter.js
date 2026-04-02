/**
 * date-badge-filter.js — 日記・タスク一覧の日付バッジフィルター
 *
 * 規約:
 *   #date-badge-filter               … バッジ群の親コンテナ
 *   .badge-filter[data-year]         … 年バッジ
 *   .badge-filter[data-season]       … 季節バッジ（data-months="3,4,5" 等）
 *   .badge-filter[data-month]        … 月バッジ
 *   .badge-filter[data-status]       … ステータスバッジ（任意）
 *   [data-filter-year][data-filter-month] … フィルタ対象アイテム
 *   [data-filter-status]             … ステータスフィルタ対象（任意）
 *   #filter-count[data-suffix]       … 件数表示
 *   #filter-empty-msg                … 0件メッセージ（初期 display:none）
 */
document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('date-badge-filter');
    if (!container) return;

    var yearBadges = container.querySelectorAll('.badge-filter[data-year]');
    var seasonBadges = container.querySelectorAll('.badge-filter[data-season]');
    var monthBadges = container.querySelectorAll('.badge-filter[data-month]');
    var statusBadges = container.querySelectorAll('.badge-filter[data-status]');
    var items = document.querySelectorAll('[data-filter-year]');
    var countEl = document.getElementById('filter-count');
    var suffix = countEl ? countEl.dataset.suffix : '';
    var emptyMsg = document.getElementById('filter-empty-msg');

    var selectedYears = new Set();
    var selectedSeasons = new Set();
    var selectedMonths = new Set();
    var selectedStatuses = new Set();

    // 季節→月マッピング
    var SEASON_MONTHS = {
        '春': [3, 4, 5],
        '夏': [6, 7, 8],
        '秋': [9, 10, 11],
        '冬': [12, 1, 2]
    };

    // 年バッジクリック
    yearBadges.forEach(function (badge) {
        badge.addEventListener('click', function () {
            toggleSet(selectedYears, this.dataset.year, this);
            applyFilter();
        });
    });

    // 季節バッジクリック
    seasonBadges.forEach(function (badge) {
        badge.addEventListener('click', function () {
            toggleSet(selectedSeasons, this.dataset.season, this);
            syncMonthImplied();
            applyFilter();
        });
    });

    // 月バッジクリック
    monthBadges.forEach(function (badge) {
        badge.addEventListener('click', function () {
            var month = this.dataset.month;
            if (selectedMonths.has(month)) {
                selectedMonths.delete(month);
                // implied 状態に戻すか inactive にするか判定
                updateMonthBadgeState(this);
            } else {
                selectedMonths.add(month);
                this.classList.remove('badge-filter-inactive', 'badge-filter-implied');
                this.classList.add('badge-filter-active');
            }
            applyFilter();
        });
    });

    // ステータスバッジクリック
    statusBadges.forEach(function (badge) {
        badge.addEventListener('click', function () {
            toggleSet(selectedStatuses, this.dataset.status, this);
            applyFilter();
        });
    });

    function toggleSet(set, value, badge) {
        if (set.has(value)) {
            set.delete(value);
            badge.classList.remove('badge-filter-active');
            badge.classList.add('badge-filter-inactive');
        } else {
            set.add(value);
            badge.classList.add('badge-filter-active');
            badge.classList.remove('badge-filter-inactive');
        }
    }

    // 季節選択に応じて月バッジの implied 状態を更新
    function syncMonthImplied() {
        var impliedMonths = getImpliedMonths();
        monthBadges.forEach(function (badge) {
            var month = badge.dataset.month;
            if (selectedMonths.has(month)) {
                // 明示選択済み → active のまま
                return;
            }
            if (impliedMonths.has(month)) {
                badge.classList.remove('badge-filter-inactive', 'badge-filter-active');
                badge.classList.add('badge-filter-implied');
            } else {
                badge.classList.remove('badge-filter-implied', 'badge-filter-active');
                badge.classList.add('badge-filter-inactive');
            }
        });
    }

    // 月バッジの状態を判定して更新（明示選択解除時）
    function updateMonthBadgeState(badge) {
        var impliedMonths = getImpliedMonths();
        if (impliedMonths.has(badge.dataset.month)) {
            badge.classList.remove('badge-filter-active', 'badge-filter-inactive');
            badge.classList.add('badge-filter-implied');
        } else {
            badge.classList.remove('badge-filter-active', 'badge-filter-implied');
            badge.classList.add('badge-filter-inactive');
        }
    }

    // 季節から暗黙選択される月のセットを返す
    function getImpliedMonths() {
        var implied = new Set();
        selectedSeasons.forEach(function (season) {
            var months = SEASON_MONTHS[season];
            if (months) {
                months.forEach(function (m) { implied.add(String(m)); });
            }
        });
        return implied;
    }

    // 有効な月（明示選択 ∪ 季節展開）を返す
    function getEffectiveMonths() {
        var effective = new Set(selectedMonths);
        var implied = getImpliedMonths();
        implied.forEach(function (m) { effective.add(m); });
        return effective;
    }

    function applyFilter() {
        var hasYears = selectedYears.size > 0;
        var effectiveMonths = getEffectiveMonths();
        var hasMonths = effectiveMonths.size > 0;
        var hasStatuses = selectedStatuses.size > 0;
        var anyDateSelected = hasYears || hasMonths;
        var visibleCount = 0;

        items.forEach(function (item) {
            var year = item.dataset.filterYear;
            var month = item.dataset.filterMonth;
            var status = item.dataset.filterStatus;

            // 日付フィルタ判定
            var dateMatch;
            if (!anyDateSelected) {
                dateMatch = true;
            } else if (!year || !month) {
                // 日付なし（タスクの due_date が NULL）→ 非表示
                dateMatch = false;
            } else if (hasYears && !hasMonths) {
                dateMatch = selectedYears.has(year);
            } else if (!hasYears && hasMonths) {
                dateMatch = effectiveMonths.has(month);
            } else {
                dateMatch = selectedYears.has(year) && effectiveMonths.has(month);
            }

            // ステータスフィルタ判定（OR、未選択時は全件通過）
            var statusMatch = !hasStatuses || (status && selectedStatuses.has(status));

            // 日付 AND ステータス
            var show = dateMatch && statusMatch;
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
