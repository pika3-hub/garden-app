/**
 * 作物・品種フォームのメモ AI 下書き（_ai_notes_button.html + _ai_notes_modal.html）
 */
(function () {
    'use strict';

    document.querySelectorAll('[data-ai-notes-tooltip]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    var btn = document.getElementById('aiNotesBtn');
    var modalEl = document.getElementById('aiNotesModal');
    if (!btn || !modalEl || btn.disabled) return;

    var mode = modalEl.dataset.mode;
    var endpoint = modalEl.dataset.endpoint;
    var settingsUrl = modalEl.dataset.settingsUrl;

    var notesEl = document.getElementById('notes');
    var nameEl = document.getElementById('name');
    var cropTypeEl = document.getElementById('crop_type');
    var cropIdEl = document.getElementById('crop_id_hidden');
    var cropDisplayEl = document.getElementById('selected-crop-display');
    var cropErrorEl = document.getElementById('crop-select-error');

    var targetEl = document.getElementById('aiNotesTarget');
    var webSearchEl = document.getElementById('aiNotesWebSearch');
    var estimateEl = document.getElementById('aiNotesEstimate');
    var generateBtn = document.getElementById('aiNotesGenerateBtn');
    var progressEl = document.getElementById('aiNotesProgress');
    var elapsedEl = document.getElementById('aiNotesElapsed');
    var errorEl = document.getElementById('aiNotesError');
    var resultWrap = document.getElementById('aiNotesResultWrap');
    var resultEl = document.getElementById('aiNotesResult');
    var appendBtn = document.getElementById('aiNotesAppendBtn');
    var replaceBtn = document.getElementById('aiNotesReplaceBtn');

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    var controller = null;
    var timerId = null;

    function markInvalid(el) {
        el.classList.add('is-invalid');
        el.focus();
        el.addEventListener('input', function clear() {
            el.classList.remove('is-invalid');
            el.removeEventListener('input', clear);
        });
    }

    function validate() {
        if (mode === 'variety' && !cropIdEl.value) {
            cropErrorEl.style.display = '';
            cropDisplayEl.classList.add('border', 'border-danger');
            cropDisplayEl.scrollIntoView({ block: 'center' });
            return false;
        }
        if (!nameEl.value.trim()) {
            markInvalid(nameEl);
            return false;
        }
        return true;
    }

    function targetLabel() {
        var name = nameEl.value.trim();
        if (mode === 'variety') {
            return name + '（' + cropDisplayEl.textContent.trim() + '）';
        }
        return name;
    }

    function updateEstimate() {
        estimateEl.textContent = webSearchEl.checked
            ? estimateEl.dataset.estimateOn
            : estimateEl.dataset.estimateOff;
    }

    function setApplyEnabled(enabled) {
        appendBtn.disabled = !enabled;
        replaceBtn.disabled = !enabled;
        var notesEmpty = !notesEl.value.trim();
        replaceBtn.classList.toggle('btn-success', enabled && notesEmpty);
        replaceBtn.classList.toggle('btn-outline-success', !(enabled && notesEmpty));
    }

    function hideError() {
        errorEl.classList.add('d-none');
        errorEl.textContent = '';
    }

    function showError(message, needSettings) {
        errorEl.textContent = message;
        if (needSettings) {
            var link = document.createElement('a');
            link.href = settingsUrl;
            link.className = 'alert-link ms-1';
            link.textContent = '設定画面を開く';
            errorEl.appendChild(link);
        }
        errorEl.classList.remove('d-none');
    }

    function startProgress() {
        var started = Date.now();
        elapsedEl.textContent = '0';
        progressEl.classList.remove('d-none');
        generateBtn.disabled = true;
        webSearchEl.disabled = true;
        timerId = setInterval(function () {
            elapsedEl.textContent = String(Math.floor((Date.now() - started) / 1000));
        }, 1000);
    }

    function stopProgress() {
        clearInterval(timerId);
        timerId = null;
        progressEl.classList.add('d-none');
        generateBtn.disabled = false;
        webSearchEl.disabled = false;
    }

    function resetModal() {
        if (controller) controller.abort();
        stopProgress();
        hideError();
        resultEl.value = '';
        resultWrap.classList.add('d-none');
        setApplyEnabled(false);
        webSearchEl.checked = (mode === 'variety');
        updateEstimate();
        targetEl.textContent = targetLabel();
    }

    function buildPayload() {
        var payload = { mode: mode, use_web_search: webSearchEl.checked };
        if (mode === 'variety') {
            payload.crop_id = cropIdEl.value;
            payload.variety_name = nameEl.value.trim();
        } else {
            payload.crop_name = nameEl.value.trim();
            payload.crop_type = cropTypeEl ? cropTypeEl.value.trim() : '';
        }
        return payload;
    }

    function generate() {
        hideError();
        resultWrap.classList.add('d-none');
        setApplyEnabled(false);

        var current = new AbortController();
        controller = current;
        startProgress();

        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildPayload()),
            signal: current.signal
        })
            .then(function (res) {
                return res.json().catch(function () {
                    return { ok: false, error: 'サーバーから不正な応答がありました（HTTP ' + res.status + '）' };
                });
            })
            .then(function (data) {
                if (controller !== current) return;  // 中断・やり直し済みの古い応答は捨てる
                if (data.ok) {
                    resultEl.value = data.markdown;
                    resultWrap.classList.remove('d-none');
                    setApplyEnabled(true);
                } else {
                    showError(data.error || '生成に失敗しました', data.need_settings);
                }
            })
            .catch(function (err) {
                if (err.name === 'AbortError' || controller !== current) return;
                showError('通信エラーが発生しました。もう一度お試しください');
            })
            .finally(function () {
                if (controller === current) {
                    controller = null;
                    stopProgress();
                }
            });
    }

    function apply(how) {
        var draft = resultEl.value.trim();
        if (!draft) return;
        if (how === 'replace') {
            notesEl.value = draft;
        } else {
            var existing = notesEl.value.replace(/\s+$/, '');
            notesEl.value = existing ? existing + '\n\n' + draft : draft;
        }
        modal.hide();
        notesEl.focus();
    }

    btn.addEventListener('click', function () {
        if (!validate()) return;
        resetModal();
        modal.show();
    });
    webSearchEl.addEventListener('change', updateEstimate);
    generateBtn.addEventListener('click', generate);
    appendBtn.addEventListener('click', function () { apply('append'); });
    replaceBtn.addEventListener('click', function () { apply('replace'); });
    modalEl.addEventListener('hidden.bs.modal', function () {
        if (controller) {
            controller.abort();
            controller = null;
            stopProgress();
        }
    });
})();
