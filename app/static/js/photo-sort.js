/**
 * 写真プールの振り分け画面（photo_sort/index.html）
 * - アイコン選択（作物・品種）
 * - 関連付けモーダルの初期化（料理・日記。diary/form.html と同じ設定）
 */
(function () {
    'use strict';

    var script = document.currentScript;
    var cropIconBase = script ? script.dataset.cropIconBase : '';

    function iconHtml(card) {
        if (!card.dataset.iconPath) return '';
        return '<img src="' + cropIconBase + card.dataset.iconPath + '" alt="" class="crop-icon-inline" style="border-color:' +
            (card.dataset.imageColor || '#4CAF50') + ';"> ';
    }

    function cropLabel(name, variety) {
        return variety ? variety + '(' + name + ')' : name;
    }

    function initIconPicker(root) {
        var input = root.querySelector('[data-icon-input]');
        var preview = root.querySelector('[data-icon-preview]');
        var base = root.dataset.iconBase;

        function render() {
            preview.innerHTML = input.value
                ? '<img src="' + base + input.value + '" class="sort-icon-preview" alt="">'
                : '<div class="sort-icon-placeholder"><i class="bi bi-image text-muted"></i></div>';
        }

        root.addEventListener('click', function (e) {
            var item = e.target.closest('.sort-icon-item');
            if (item) {
                root.querySelectorAll('.sort-icon-item.selected').forEach(function (i) { i.classList.remove('selected'); });
                item.classList.add('selected');
                input.value = item.dataset.icon;
                render();
            } else if (e.target.closest('[data-icon-clear]')) {
                root.querySelectorAll('.sort-icon-item.selected').forEach(function (i) { i.classList.remove('selected'); });
                input.value = '';
                render();
            }
        });
        render();
    }

    var RELATIONS = [
        {
            modalId: 'cropMultiSelectModal', cardSelector: '.crop-ms-card', idAttribute: 'cropId',
            inputContainerId: 'crop-hidden-inputs', inputName: 'crop_ids', displayContainerId: 'selected-crops-display',
            badgeRenderer: function (c) { return iconHtml(c) + cropLabel(c.dataset.cropName, c.dataset.variety); },
            filterMode: 'legacy', filterScope: 'crop-multi', filterCardAttr: 'data-crop-ms-card'
        },
        {
            modalId: 'varietyMultiSelectModal', cardSelector: '.variety-ms-card', idAttribute: 'varietyId',
            inputContainerId: 'variety-hidden-inputs', inputName: 'variety_ids', displayContainerId: 'selected-varieties-display',
            badgeRenderer: function (c) { return iconHtml(c) + c.dataset.varietyName + '(' + c.dataset.cropName + ')'; },
            filterMode: 'legacy', filterScope: 'variety-multi', filterCardAttr: 'data-variety-ms-card'
        },
        {
            modalId: 'locationMultiSelectModal', cardSelector: '.location-ms-card', idAttribute: 'locationId',
            inputContainerId: 'location-hidden-inputs', inputName: 'location_ids', displayContainerId: 'selected-locations-display',
            badgeRenderer: function (c) {
                var type = c.dataset.locationType;
                return '<i class="bi bi-geo-alt"></i> ' + c.dataset.locationName + (type ? ' (' + type + ')' : '');
            },
            filterMode: 'legacy', filterScope: 'location-multi', filterCardAttr: 'data-location-ms-card'
        },
        {
            modalId: 'plantingMultiSelectModal', cardSelector: '.planting-ms-card', idAttribute: 'plantingId',
            inputContainerId: 'planting-hidden-inputs', inputName: 'location_crop_ids', displayContainerId: 'selected-plantings-display',
            badgeRenderer: function (c) {
                return iconHtml(c) + cropLabel(c.dataset.cropName, c.dataset.variety) + ' <small>@ ' + c.dataset.locationName + '</small>';
            },
            filterMode: 'multi'
        },
        {
            modalId: 'harvestMultiSelectModal', cardSelector: '.harvest-ms-card', idAttribute: 'harvestId',
            inputContainerId: 'harvest-hidden-inputs', inputName: 'harvest_ids', displayContainerId: 'selected-harvests-display',
            badgeRenderer: function (c) {
                var extra = c.dataset.harvestDate || '';
                if (c.dataset.quantity) extra += ' ' + c.dataset.quantity + (c.dataset.unit || '');
                return iconHtml(c) + cropLabel(c.dataset.cropName, c.dataset.variety) + (extra ? ' <small>' + extra + '</small>' : '');
            },
            filterMode: 'multi'
        }
    ];

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-icon-picker]').forEach(initIconPicker);

        if (typeof MultiSelectModal !== 'undefined') {
            RELATIONS.forEach(function (config) {
                if (document.getElementById(config.modalId) && document.getElementById(config.inputContainerId)) {
                    new MultiSelectModal(config);
                }
            });
        }
    });
})();
