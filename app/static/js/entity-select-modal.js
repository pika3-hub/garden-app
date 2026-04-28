/**
 * entity-select-modal.js — 複数選択モーダルの共通JS
 *
 * 日記・タスクの関連付けフォームで使用する。
 * カード型モーダルで複数エンティティを選択し、hidden inputs + バッジチップとして反映する。
 *
 * 使い方:
 *   new MultiSelectModal({
 *       modalId: 'cropMultiSelectModal',
 *       cardSelector: '.crop-ms-card',
 *       idAttribute: 'cropId',               // card.dataset.cropId
 *       inputContainerId: 'crop-hidden-inputs',
 *       inputName: 'crop_ids',
 *       displayContainerId: 'selected-crops-display',
 *       badgeRenderer: function(card) { return 'HTML string'; },
 *       filterMode: 'legacy' | 'multi',       // default: 'legacy'
 *       filterScope: 'crop-multi',            // for legacy mode
 *       filterCardAttr: 'data-crop-ms-card',  // for legacy mode
 *   });
 */
(function () {
    'use strict';

    function MultiSelectModal(opts) {
        this.modalEl = document.getElementById(opts.modalId);
        if (!this.modalEl) return;

        this.cardSelector = opts.cardSelector;
        this.idAttribute = opts.idAttribute;
        this.inputContainer = document.getElementById(opts.inputContainerId);
        this.inputName = opts.inputName;
        this.displayContainer = document.getElementById(opts.displayContainerId);
        this.badgeRenderer = opts.badgeRenderer;
        this.filterMode = opts.filterMode || 'legacy';
        this.filterScope = opts.filterScope || '';
        this.filterCardAttr = opts.filterCardAttr || '';

        this.selectedIds = new Set();

        this._init();
    }

    MultiSelectModal.prototype._init = function () {
        var self = this;

        // Read pre-selected from existing hidden inputs
        if (this.inputContainer) {
            var existing = this.inputContainer.querySelectorAll('input[name="' + this.inputName + '"]');
            existing.forEach(function (inp) {
                if (inp.value) self.selectedIds.add(inp.value);
            });
        }

        // Mark pre-selected cards
        this._syncCardStates();

        // Render initial badges
        this._renderBadges();

        // Update count in footer
        this._updateCount();

        // Card click handler
        var cards = this.modalEl.querySelectorAll(this.cardSelector);
        cards.forEach(function (card) {
            card.addEventListener('click', function () {
                var id = card.dataset[self.idAttribute];
                if (!id) return;
                if (self.selectedIds.has(id)) {
                    self.selectedIds.delete(id);
                    card.classList.remove('ms-card-selected');
                } else {
                    self.selectedIds.add(id);
                    card.classList.add('ms-card-selected');
                }
                self._updateCount();
            });
        });

        // Confirm button
        var confirmBtn = this.modalEl.querySelector('.ms-confirm-btn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', function () {
                self._syncInputs();
                self._renderBadges();
                var inst = bootstrap.Modal.getInstance(self.modalEl) || new bootstrap.Modal(self.modalEl);
                inst.hide();
            });
        }

        // Init scoped filter
        if (this.filterMode === 'legacy') {
            this._initLegacyFilter();
        } else if (this.filterMode === 'multi') {
            this._initMultiGroupFilter();
        }
    };

    MultiSelectModal.prototype._syncCardStates = function () {
        var self = this;
        var cards = this.modalEl.querySelectorAll(this.cardSelector);
        cards.forEach(function (card) {
            var id = card.dataset[self.idAttribute];
            if (id && self.selectedIds.has(id)) {
                card.classList.add('ms-card-selected');
            } else {
                card.classList.remove('ms-card-selected');
            }
        });
    };

    MultiSelectModal.prototype._syncInputs = function () {
        if (!this.inputContainer) return;
        this.inputContainer.innerHTML = '';
        var self = this;
        this.selectedIds.forEach(function (id) {
            var inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = self.inputName;
            inp.value = id;
            self.inputContainer.appendChild(inp);
        });
    };

    MultiSelectModal.prototype._renderBadges = function () {
        if (!this.displayContainer) return;
        var self = this;
        this.displayContainer.innerHTML = '';

        if (this.selectedIds.size === 0) return;

        var cards = this.modalEl.querySelectorAll(this.cardSelector);
        var cardMap = {};
        cards.forEach(function (card) {
            var id = card.dataset[self.idAttribute];
            if (id) cardMap[id] = card;
        });

        this.selectedIds.forEach(function (id) {
            var card = cardMap[id];
            if (!card) return;

            var chip = document.createElement('span');
            chip.className = 'selected-item-chip';
            chip.dataset.chipId = id;
            chip.innerHTML = self.badgeRenderer(card) +
                ' <button type="button" class="chip-remove" aria-label="削除">&times;</button>';

            chip.querySelector('.chip-remove').addEventListener('click', function () {
                self.selectedIds.delete(id);
                chip.remove();
                self._syncInputs();
                // Update card state if modal is open
                if (cardMap[id]) cardMap[id].classList.remove('ms-card-selected');
                self._updateCount();
            });

            self.displayContainer.appendChild(chip);
        });
    };

    MultiSelectModal.prototype._updateCount = function () {
        var countEl = this.modalEl.querySelector('.ms-selected-count');
        if (countEl) {
            var n = this.selectedIds.size;
            countEl.textContent = n > 0 ? n + '件選択中' : '未選択';
        }
    };

    /** Legacy single-group filter (scoped to modal) */
    MultiSelectModal.prototype._initLegacyFilter = function () {
        if (!this.filterScope) return;
        var modalEl = this.modalEl;
        var container = modalEl.querySelector('.badge-filter-container[data-scope="' + this.filterScope + '"]');
        if (!container) return;

        var badges = container.querySelectorAll('.badge-filter');
        var cardAttr = this.filterCardAttr;
        var items = modalEl.querySelectorAll('[' + cardAttr + ']');
        var selected = new Set();

        badges.forEach(function (badge) {
            badge.addEventListener('click', function () {
                var type = this.dataset.type;
                if (selected.has(type)) {
                    selected.delete(type);
                    this.classList.remove('badge-filter-active');
                    this.classList.add('badge-filter-inactive');
                } else {
                    selected.add(type);
                    this.classList.add('badge-filter-active');
                    this.classList.remove('badge-filter-inactive');
                }
                items.forEach(function (item) {
                    var types = item.dataset.filterType ? item.dataset.filterType.split(',') : [];
                    var show = selected.size === 0 || types.some(function (t) { return selected.has(t); });
                    item.style.display = show ? '' : 'none';
                });
                modalEl.querySelectorAll('.date-group').forEach(function (group) {
                    var visible = false;
                    group.querySelectorAll('[' + cardAttr + ']').forEach(function (item) {
                        if (item.style.display !== 'none') visible = true;
                    });
                    group.style.display = visible ? '' : 'none';
                });
            });
        });
    };

    /** Multi-group filter (scoped to modal, AND between groups, OR within) */
    MultiSelectModal.prototype._initMultiGroupFilter = function () {
        var modalEl = this.modalEl;
        var groups = modalEl.querySelectorAll('.badge-filter-group[data-filter-key]');
        if (groups.length === 0) return;

        var items = modalEl.querySelectorAll('[data-ms-filter-card]');
        var countEl = modalEl.querySelector('.ms-filter-count');
        var suffix = countEl ? (countEl.dataset.suffix || '') : '';
        var emptyMsg = modalEl.querySelector('.ms-filter-empty-msg');

        var selectedByGroup = {};
        var datasetAttrMap = {};

        groups.forEach(function (group) {
            var key = group.dataset.filterKey;
            selectedByGroup[key] = new Set();
            datasetAttrMap[key] = 'msFilterGroup' + key.charAt(0).toUpperCase() + key.slice(1);

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
                    applyFilter();
                });
            });
        });

        function applyFilter() {
            var visibleCount = 0;
            items.forEach(function (item) {
                var show = true;
                for (var key in selectedByGroup) {
                    var sel = selectedByGroup[key];
                    if (sel.size === 0) continue;
                    var value = item.dataset[datasetAttrMap[key]] || '';
                    if (!sel.has(value)) {
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
            modalEl.querySelectorAll('.date-group').forEach(function (group) {
                var visible = false;
                group.querySelectorAll('[data-ms-filter-card]').forEach(function (item) {
                    if (item.style.display !== 'none') visible = true;
                });
                group.style.display = visible ? '' : 'none';
            });
        }
    };

    window.MultiSelectModal = MultiSelectModal;
})();
