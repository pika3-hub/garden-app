/* Hermes とのチャット画面（hermes_chat/index.html）。送る・履歴は hermes-ask.js に任せ、
   ここは新しい会話ができたとき（hermes:chat-created）に左の一覧・見出し・題名変更と削除を整えるだけ。
   題名はユーザーの入力から作られるので、必ず textContent で入れる。 */
(function () {
  'use strict';

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function nowLabel() {
    var d = new Date();
    return pad(d.getMonth() + 1) + '/' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function span(cls, text) {
    var e = document.createElement('span');
    e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  document.addEventListener('hermes:chat-created', function (ev) {
    var d = ev.detail || {};
    var title = d.title || '（題名なし）';
    var list = document.querySelector('[data-hermes-chat-list]');
    if (list) {
      var empty = list.querySelector('[data-hermes-chat-empty]');
      if (empty) empty.remove();
      list.querySelectorAll('.hermes-chat-row.active').forEach(function (row) {
        row.classList.remove('active');
        row.removeAttribute('aria-current');
      });
      var a = document.createElement('a');
      a.className = 'list-group-item list-group-item-action hermes-chat-row active';
      a.setAttribute('aria-current', 'true');
      if (d.chat_url) a.href = d.chat_url;
      a.appendChild(span('hermes-chat-row-title', title));
      var meta = span('hermes-chat-row-meta');
      meta.appendChild(span('hermes-chat-row-time', nowLabel()));
      a.appendChild(meta);
      list.insertBefore(a, list.firstChild);
    }

    var heading = document.querySelector('[data-hermes-chat-title]');
    if (heading) heading.textContent = title;

    // 題名変更・削除の送り先をこの会話にして出す（chat_url は /hermes/chat/<id>）
    if (d.chat_url) {
      var rename = document.querySelector('[data-hermes-chat-rename]');
      var del = document.querySelector('[data-hermes-chat-delete]');
      var input = document.querySelector('[data-hermes-chat-rename-input]');
      if (rename) rename.action = d.chat_url + '/rename';
      if (del) del.action = d.chat_url + '/delete';
      if (input) input.value = title;
      var actions = document.querySelector('[data-hermes-chat-actions]');
      if (actions) actions.classList.remove('d-none');
    }
  });

  // 答えが届いたら、選んでいる行の時刻を今にして一覧の先頭へ（一覧は最後に使った順）
  document.addEventListener('hermes:run-finished', function () {
    var list = document.querySelector('[data-hermes-chat-list]');
    var row = list && list.querySelector('.hermes-chat-row.active');
    if (!row) return;
    var time = row.querySelector('.hermes-chat-row-time');
    if (time) time.textContent = nowLabel();
    list.insertBefore(row, list.firstChild);
  });
})();
