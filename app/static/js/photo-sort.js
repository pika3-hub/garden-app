/**
 * 写真プールの振り分け画面（photo_sort/index.html）
 * - アイコン選択（作物・品種）
 * - 関連付けモーダルの初期化（料理・日記。diary/form.html と同じ設定）
 * - 「✨ AIで下書き」: 写真と今の入力を送り、返った項目を data-ai-field の欄に入れる（「元に戻す」で直前の値へ）
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

    function selectedText(id) {
        var el = document.getElementById(id);
        return el && el.value ? el.selectedOptions[0].text : '';
    }

    function draftPayload(form) {
        var val = function (name) { var el = form.querySelector('[name="' + name + '"]'); return el ? el.value : ''; };
        var dateEl = form.querySelector('[data-ai-date]');
        var nameEl = form.querySelector('#name');
        return {
            photo_id: parseInt(val('photo_id'), 10),
            kind: val('kind'),
            date: dateEl ? dateEl.value : '',
            name: nameEl ? nameEl.value : '',
            location_crop_ids: Array.from(form.querySelectorAll('input[name="location_crop_id"]'))
                .map(function (el) { return parseInt(el.value, 10); }),
            related: Array.from(form.querySelectorAll('.selected-items-chips > *'))
                .map(function (el) { return el.textContent.replace(/[×✕]/g, '').trim(); })
                .filter(Boolean),
            planting_label: [selectedText('crop_variety'), selectedText('location_id')].filter(Boolean).join('／')
        };
    }

    function initAiDraft(btn) {
        var form = btn.closest('form');
        var wrap = btn.parentElement;
        var undoBtn = wrap.querySelector('[data-ai-draft-undo]');
        var statusEl = wrap.querySelector('[data-ai-draft-status]');
        var previous = null;

        btn.addEventListener('click', function () {
            var started = Date.now();
            btn.disabled = true;
            statusEl.classList.remove('text-danger');
            statusEl.textContent = '生成中… 0秒';
            var timer = setInterval(function () {
                statusEl.textContent = '生成中… ' + Math.round((Date.now() - started) / 1000) + '秒';
            }, 1000);

            fetch(btn.dataset.url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(draftPayload(form))
            }).then(function (res) {
                return res.json().catch(function () { return { ok: false, error: '応答を読み取れませんでした' }; });
            }).then(function (data) {
                if (!data.ok) throw new Error(data.error || '生成に失敗しました');
                previous = {};
                Object.keys(data.fields).forEach(function (key) {
                    var el = form.querySelector('[data-ai-field="' + key + '"]');
                    if (!el) return;
                    previous[key] = el.value;
                    el.value = data.fields[key];
                });
                undoBtn.classList.remove('d-none');
                statusEl.textContent = '下書きを入れました。確認・修正してから保存してください';
            }).catch(function (err) {
                statusEl.classList.add('text-danger');
                statusEl.textContent = err.message === 'Failed to fetch' ? '通信エラーです' : err.message;
            }).finally(function () {
                clearInterval(timer);
                btn.disabled = false;
            });
        });

        undoBtn.addEventListener('click', function () {
            if (!previous) return;
            Object.keys(previous).forEach(function (key) {
                var el = form.querySelector('[data-ai-field="' + key + '"]');
                if (el) el.value = previous[key];
            });
            previous = null;
            undoBtn.classList.add('d-none');
            statusEl.textContent = '元に戻しました';
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-icon-picker]').forEach(initIconPicker);
        document.querySelectorAll('[data-ai-draft-btn]').forEach(initAiDraft);

        if (typeof MultiSelectModal !== 'undefined') {
            RELATIONS.forEach(function (config) {
                var container = document.getElementById(config.inputContainerId);
                if (document.getElementById(config.modalId) && container) {
                    // 栽培記録・収穫の対象の植え付けは hidden 名が location_crop_id（data-input-name で指定）
                    var name = container.dataset.inputName || config.inputName;
                    new MultiSelectModal(Object.assign({}, config, { inputName: name }));
                }
            });
        }
    });
})();
