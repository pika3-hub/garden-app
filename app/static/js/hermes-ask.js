/* Hermes に聞くパネル。ブラウザはアプリの /hermes/ask だけに話す（Hermes にもキーにも触れない）。
   答えの html はサーバーで作ったものだけを innerHTML に入れ、途中の文字・承認のコマンドは textContent。 */
(function () {
  'use strict';

  var PREFIX = '/hermes/ask';

  function init() {
    var panel = document.getElementById('hermes-ask-panel');
    if (!panel) return;

    var type = panel.dataset.entityType;
    var id = panel.dataset.entityId;
    var base = PREFIX + '/' + type + '/' + id;
    var box = panel.querySelector('[data-hermes-messages]');
    var contextEl = panel.querySelector('[data-hermes-context]');
    var errorEl = panel.querySelector('[data-hermes-error]');
    var input = panel.querySelector('[data-hermes-input]');
    var sendBtn = panel.querySelector('[data-hermes-send]');
    var newBtn = panel.querySelector('[data-hermes-new]');

    var loaded = false;
    var busy = false;
    var source = null;

    function el(tag, cls, text) {
      var e = document.createElement(tag);
      if (cls) e.className = cls;
      if (text != null) e.textContent = text;
      return e;
    }

    function scrollDown() { box.scrollTop = box.scrollHeight; }

    function showError(msg) {
      errorEl.textContent = msg || '';
      errorEl.classList.toggle('d-none', !msg);
    }

    function setBusy(b) {
      busy = b;
      sendBtn.disabled = b;
      sendBtn.textContent = b ? '送信中…' : '送る';
    }

    function dayLabel(ts) {
      if (ts == null || ts === '') return null;
      var d = typeof ts === 'number' ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(ts);
      if (isNaN(d.getTime())) return null;
      if (d.toDateString() === new Date().toDateString()) return '今日';
      return (d.getMonth() + 1) + '/' + d.getDate();
    }

    function renderHistory(messages) {
      box.textContent = '';
      var lastDay = null;
      messages.forEach(function (m) {
        var day = dayLabel(m.timestamp);
        if (day && day !== lastDay) {
          box.appendChild(el('div', 'hermes-msg-day', '― ' + day + ' ―'));
          lastDay = day;
        }
        if (m.role === 'user') {
          box.appendChild(el('div', 'hermes-msg-user', m.text));
        } else {
          var bot = el('div', 'hermes-msg-bot');
          if (m.html) bot.innerHTML = m.html; else bot.textContent = m.text;
          box.appendChild(bot);
        }
      });
      scrollDown();
    }

    function loadHistory() {
      return fetch(base + '/history', { headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) { showError(data.error); return; }
          loaded = true;
          showError('');
          contextEl.textContent = 'この' + data.target.kind_label + ': ' + data.target.label;
          renderHistory(data.messages);
          if (data.running_run_id) {
            setBusy(true);
            followRun(data.running_run_id);
          }
        })
        .catch(function () { showError('Hermes に届きません'); });
    }

    function followRun(runId) {
      if (source) source.close();
      var bot = null;
      var toolLine = null;
      var finished = false;

      function ensureBot() {
        if (!bot) {
          bot = el('div', 'hermes-msg-bot streaming');
          box.appendChild(bot);
        }
        return bot;
      }

      function dropTool() {
        if (toolLine) { toolLine.remove(); toolLine = null; }
      }

      function finish() {
        finished = true;
        if (source) { source.close(); source = null; }
        setBusy(false);
      }

      source = new EventSource(PREFIX + '/runs/' + encodeURIComponent(runId) + '/events');
      source.onmessage = function (ev) {
        var d;
        try { d = JSON.parse(ev.data); } catch (e) { return; }
        if (d.type === 'tool') {
          // 最後の1行だけ残す（上書き）。答えの吹き出しより前に置く
          if (!toolLine) toolLine = el('div', 'hermes-tool');
          toolLine.textContent = '⚙ ' + d.label;
          if (bot) box.insertBefore(toolLine, bot); else box.appendChild(toolLine);
        } else if (d.type === 'delta') {
          ensureBot().textContent += d.text;
        } else if (d.type === 'approval') {
          showApproval(runId, d);
        } else if (d.type === 'done') {
          var b = ensureBot();
          b.classList.remove('streaming');
          b.innerHTML = d.html;
          dropTool();
          if (d.links && d.links.length) b.after(buildLinks(d.links));
          finish();
        } else if (d.type === 'failed') {
          dropTool();
          box.appendChild(el('div', 'hermes-failed', d.error));
          finish();
        }
        scrollDown();
      };
      source.onerror = function () {
        if (finished) return;
        dropTool();
        box.appendChild(el('div', 'hermes-failed', 'Hermes との接続が切れました'));
        finish();
        scrollDown();
      };
    }

    function buildLinks(links) {
      var wrap = el('div', 'hermes-links');
      wrap.appendChild(el('div', null, 'Hermes が作った・変えたデータ'));
      var ul = el('ul');
      links.forEach(function (l) {
        var li = el('li');
        var a = el('a', null, (l.kind_label ? l.kind_label + ': ' : '') + l.label);
        a.href = l.url;
        li.appendChild(a);
        ul.appendChild(li);
      });
      wrap.appendChild(ul);
      return wrap;
    }

    function showApproval(runId, d) {
      var wrap = el('div', 'hermes-approval');
      wrap.appendChild(el('div', null, 'Hermes が次のコマンドを実行してよいか聞いています'));
      wrap.appendChild(el('code', null, d.command || ''));
      var allow = el('button', 'btn btn-success btn-sm me-2', '許可する');
      var deny = el('button', 'btn btn-outline-secondary btn-sm', 'しない');
      allow.type = 'button';
      deny.type = 'button';
      function answer(choice) {
        allow.disabled = true;
        deny.disabled = true;
        fetch(PREFIX + '/runs/' + encodeURIComponent(runId) + '/approval', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ choice: choice, request_id: d.request_id })
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) {
            wrap.textContent = choice === 'once' ? '許可しました' : '許可しませんでした';
          } else {
            wrap.textContent = data.error || '答えを送れませんでした';
          }
        }).catch(function () { wrap.textContent = 'Hermes に届きません'; });
      }
      allow.addEventListener('click', function () { answer('once'); });
      deny.addEventListener('click', function () { answer('deny'); });
      wrap.appendChild(allow);
      wrap.appendChild(deny);
      box.appendChild(wrap);
      scrollDown();
    }

    function send() {
      var text = input.value.trim();
      if (busy || !text) return;
      showError('');
      setBusy(true);
      fetch(base + '/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ text: text, request_key: crypto.randomUUID() })
      }).then(function (r) {
        return r.json().catch(function () { return { ok: false, error: 'Hermes に届きません' }; });
      }).then(function (data) {
        if (!data.ok) { showError(data.error); setBusy(false); return; }
        input.value = '';
        box.appendChild(el('div', 'hermes-msg-day', '― 今日 ―'));
        box.appendChild(el('div', 'hermes-msg-user', text));
        scrollDown();
        followRun(data.run_id);
      }).catch(function () { showError('Hermes に届きません'); setBusy(false); });
    }

    function startNew() {
      if (source) { source.close(); source = null; }
      setBusy(false);
      fetch(base + '/new', { method: 'POST', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) { box.textContent = ''; showError(''); } else { showError(data.error); }
        })
        .catch(function () { showError('Hermes に届きません'); });
    }

    sendBtn.addEventListener('click', send);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); }
    });
    newBtn.addEventListener('click', startNew);
    panel.addEventListener('show.bs.offcanvas', function () {
      if (!loaded) loadHistory();
    });
  }

  // Bootstrap の JS は body の最後で読まれるので、読み込み完了を待つ
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
