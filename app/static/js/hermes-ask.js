/* Hermes に聞くパネル。ブラウザはアプリの /hermes/ask だけに話す（Hermes にもキーにも触れない）。
   答えの html はサーバーで作ったものだけを innerHTML に入れ、途中の文字・承認のコマンドは textContent。 */
(function () {
  'use strict';

  var PREFIX = '/hermes/ask';

  // 要素の data 属性: data-history-url（無ければ履歴を読まず、すぐ送れる＝新しい会話）、
  // data-runs-url（送る先）、data-new-url（「新しく始める」。無ければボタンを探さない）、
  // data-autoload（あればすぐ履歴を読む。無ければ offcanvas を開いたとき）
  function setup(panel) {
    var historyUrl = panel.dataset.historyUrl || null;
    var runsUrl = panel.dataset.runsUrl;
    var newUrl = panel.dataset.newUrl || null;
    var box = panel.querySelector('[data-hermes-messages]');
    var contextEl = panel.querySelector('[data-hermes-context]');
    var errorEl = panel.querySelector('[data-hermes-error]');
    var input = panel.querySelector('[data-hermes-input]');
    var sendBtn = panel.querySelector('[data-hermes-send]');
    var newBtn = newUrl ? panel.querySelector('[data-hermes-new]') : null;

    var loaded = false;
    var loading = false;
    // 履歴を読み込み終わる（または読み込みに失敗する）まで送れない。先に送ると、
    // 後から届いた履歴が送った吹き出しを消してしまうため
    var ready = false;
    var busy = false;
    var source = null;
    // 承認のボタンの塊（request_id ごと）。Hermes はつなぎ直すと event を最初から流し直すので、
    // 同じ承認を二重に出さず、返事済みの知らせ（approval_done）でボタンを消すのに使う
    var approvals = {};
    sendBtn.disabled = true;

    function fire(name, detail) {
      panel.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: detail }));
    }

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
      sendBtn.disabled = b || !ready;
      sendBtn.textContent = b ? '送信中…' : '送る';
    }

    function setReady() {
      ready = true;
      setBusy(busy);
    }

    function lastDayLabel() {
      var days = box.querySelectorAll('.hermes-msg-day');
      return days.length ? days[days.length - 1].textContent : null;
    }

    function toDate(ts) {
      if (ts == null || ts === '') return null;
      var d = typeof ts === 'number' ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(ts);
      return isNaN(d.getTime()) ? null : d;
    }

    function dayLabel(ts) {
      var d = toDate(ts);
      if (!d) return null;
      if (d.toDateString() === new Date().toDateString()) return '今日';
      return (d.getMonth() + 1) + '/' + d.getDate();
    }

    // 吹き出しの下の時刻（HH:MM）。日付は「― 10/29 ―」の区切りで出す
    function timeLabel(d) {
      return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    }

    function addTime(role, d) {
      if (!d) return;
      box.appendChild(el('div', 'hermes-msg-time ' + (role === 'user' ? 'is-user' : 'is-bot'),
        timeLabel(d)));
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
          addTime('user', toDate(m.timestamp));
        } else {
          var bot = el('div', 'hermes-msg-bot');
          if (m.html) bot.innerHTML = m.html; else bot.textContent = m.text;
          box.appendChild(bot);
          addTime('bot', toDate(m.timestamp));
          if (m.links && m.links.length) box.appendChild(buildLinks(m.links));
        }
      });
      scrollDown();
    }

    function loadHistory() {
      if (loading) return;
      loading = true;
      fetch(historyUrl, { headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          loading = false;
          // 履歴を読めなくても、エラーを出したうえで送れるようにする
          if (!data.ok) { showError(data.error); setReady(); return; }
          loaded = true;
          showError('');
          if (contextEl) {
            // 対象が消えたパネルの会話は kind_label が null（label は「（削除済み）」）
            contextEl.textContent = !data.target ? ''
              : data.target.kind_label ? 'この' + data.target.kind_label + ': ' + data.target.label
                : data.target.label;
          }
          renderHistory(data.messages);
          if (data.running_run_id) {
            setBusy(true);
            followRun(data.running_run_id);
          }
          setReady();
        })
        .catch(function () {
          loading = false;
          showError('Hermes に届きません');
          setReady();
        });
    }

    function followRun(runId) {
      if (source) source.close();
      approvals = {};  // 承認は run ごと
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
        fire('hermes:run-finished');
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
        } else if (d.type === 'approval_done') {
          markApprovalDone(d);
        } else if (d.type === 'done') {
          var b = ensureBot();
          b.classList.remove('streaming');
          b.innerHTML = d.html;
          dropTool();
          if (d.links && d.links.length) b.after(buildLinks(d.links));
          // 届いた答えはブラウザの今の時刻（リンクより前、吹き出しのすぐ下）
          b.after(el('div', 'hermes-msg-time is-bot', timeLabel(new Date())));
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
      wrap.appendChild(el('div', null, 'Hermes が作った・変えた・見たデータ'));
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

    function approvalKey(requestId) {
      return requestId ? 'id:' + requestId : 'noid';
    }

    // 返事済みの承認（この画面で返事したもの・前に返事したものの流し直し）はボタンを消す
    function markApprovalDone(d) {
      Object.keys(approvals).forEach(function (key) {
        var a = approvals[key];
        if (d.request_id && key !== approvalKey(d.request_id)) return;
        if (a.answered) return;
        a.answered = true;
        var label = d.choice === 'deny' ? '（返事済み: 許可しませんでした）'
          : d.choice ? '（返事済み: 許可しました）' : '（返事済み）';
        a.wrap.textContent = '';
        a.wrap.appendChild(el('code', null, a.command));
        a.wrap.appendChild(el('div', 'text-muted small', label));
      });
    }

    function showApproval(runId, d) {
      var key = approvalKey(d.request_id);
      if (approvals[key]) return;  // 流し直しで同じ承認がもう一度来た
      var wrap = el('div', 'hermes-approval');
      var state = { wrap: wrap, command: d.command || '', answered: false };
      approvals[key] = state;
      if (d.request_id) wrap.dataset.requestId = d.request_id;
      wrap.appendChild(el('div', null, 'Hermes が次のコマンドを実行してよいか聞いています'));
      wrap.appendChild(el('code', null, d.command || ''));
      var allow = el('button', 'btn btn-success btn-sm me-2', '許可する');
      var deny = el('button', 'btn btn-outline-secondary btn-sm', 'しない');
      allow.type = 'button';
      deny.type = 'button';
      function answer(choice) {
        if (state.answered) return;
        state.answered = true;
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
      if (busy || !ready || !text) return;
      showError('');
      setBusy(true);
      fetch(runsUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ text: text, request_key: crypto.randomUUID() })
      }).then(function (r) {
        return r.json().catch(function () { return { ok: false, error: 'Hermes に届きません' }; });
      }).then(function (data) {
        if (!data.ok) { showError(data.error); setBusy(false); return; }
        input.value = '';
        if (data.chat_id) {
          // 新しい会話ができた: 以後は同じ会話に送り、URL もその会話のものにする
          runsUrl = PREFIX + '/chats/' + encodeURIComponent(data.chat_id) + '/runs';
          if (data.chat_url) history.replaceState(null, '', data.chat_url);
          fire('hermes:chat-created', { chat_id: data.chat_id, chat_url: data.chat_url, title: data.title });
        }
        // 履歴を読めずに送った場合も、あとで履歴を読み直してこの吹き出しを消さない
        loaded = true;
        if (lastDayLabel() !== '― 今日 ―') box.appendChild(el('div', 'hermes-msg-day', '― 今日 ―'));
        box.appendChild(el('div', 'hermes-msg-user', text));
        addTime('user', new Date());
        scrollDown();
        followRun(data.run_id);
      }).catch(function () { showError('Hermes に届きません'); setBusy(false); });
    }

    // 作業中なら、サーバーが Hermes の run を止めてから会話を切り替える。止められなければ
    // 切り替わらないので、受信も吹き出しもそのまま残す
    function startNew() {
      if (busy && !window.confirm('Hermes が作業中です。止めて新しく始めますか？')) return;
      newBtn.disabled = true;
      fetch(newUrl, { method: 'POST', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          newBtn.disabled = false;
          if (!data.ok) { showError(data.error); return; }
          if (source) { source.close(); source = null; }
          approvals = {};
          setBusy(false);
          box.textContent = '';
          showError('');
        })
        .catch(function () { newBtn.disabled = false; showError('Hermes に届きません'); });
    }

    sendBtn.addEventListener('click', send);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); }
    });
    if (newBtn) newBtn.addEventListener('click', startNew);
    if (!historyUrl) {
      setReady();
    } else if ('autoload' in panel.dataset) {
      loadHistory();
    } else {
      panel.addEventListener('show.bs.offcanvas', function () {
        if (!loaded) loadHistory();
      });
    }
  }

  function init() {
    document.querySelectorAll('[data-hermes-ask]').forEach(setup);
  }

  // Bootstrap の JS は body の最後で読まれるので、読み込み完了を待つ
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
