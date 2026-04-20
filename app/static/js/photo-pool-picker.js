(function() {
  document.addEventListener('DOMContentLoaded', function() {
    const modalEl = document.getElementById('photoPoolPickerModal');
    if (!modalEl) return;

    let activeContainer = null;

    function toggleFileUI(container, showFile) {
      const input = container.querySelector('.photo-pool-file-input');
      const hint = container.querySelector('.photo-pool-file-hint');
      const trigger = container.querySelector('.photo-pool-trigger-wrap');
      if (input) input.style.display = showFile ? '' : 'none';
      if (hint) hint.style.display = showFile ? '' : 'none';
      if (trigger) trigger.style.display = showFile ? '' : 'none';
    }

    function clearSelection(container) {
      if (!container) return;
      const hidden = container.querySelector('.photo-pool-id-input');
      const area = container.querySelector('.photo-pool-selected-area');
      if (hidden) hidden.value = '';
      if (area) { area.classList.add('d-none'); area.classList.remove('d-flex'); }
      toggleFileUI(container, true);
    }

    function applySelection(container, data) {
      const hidden = container.querySelector('.photo-pool-id-input');
      const area = container.querySelector('.photo-pool-selected-area');
      const thumb = container.querySelector('.photo-pool-selected-thumb');
      const notes = container.querySelector('.photo-pool-selected-notes');
      if (hidden) hidden.value = data.id;
      if (thumb) thumb.src = data.thumb;
      if (notes) notes.textContent = data.notes || '';
      if (area) { area.classList.remove('d-none'); area.classList.add('d-flex'); }
      const input = container.querySelector('.photo-pool-file-input');
      if (input) input.value = '';
      toggleFileUI(container, false);
    }

    // Trigger ボタン: 対象 container を記録
    document.querySelectorAll('.photo-pool-trigger').forEach(function(btn) {
      btn.addEventListener('click', function() {
        activeContainer = btn.closest('[data-photo-pool-container]');
      });
    });

    // クリアボタン
    document.querySelectorAll('.photo-pool-clear-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        clearSelection(btn.closest('[data-photo-pool-container]'));
      });
    });

    // ファイル選択時: プール選択解除
    document.querySelectorAll('[data-photo-pool-container] .photo-pool-file-input').forEach(function(input) {
      input.addEventListener('change', function() {
        if (input.files && input.files.length > 0) {
          const container = input.closest('[data-photo-pool-container]');
          const hidden = container.querySelector('.photo-pool-id-input');
          const area = container.querySelector('.photo-pool-selected-area');
          if (hidden) hidden.value = '';
          if (area) { area.classList.add('d-none'); area.classList.remove('d-flex'); }
        }
      });
    });

    // 初期状態: preselected あり → ファイル入力非表示
    document.querySelectorAll('[data-photo-pool-container]').forEach(function(c) {
      const hidden = c.querySelector('.photo-pool-id-input');
      if (hidden && hidden.value) {
        toggleFileUI(c, false);
      }
    });

    // モーダルカードクリック
    modalEl.querySelectorAll('.photo-pool-picker-card').forEach(function(card) {
      card.addEventListener('click', function() {
        if (!activeContainer) return;
        applySelection(activeContainer, {
          id: card.dataset.photoId,
          thumb: card.dataset.thumbUrl,
          notes: card.dataset.notes
        });
        const inst = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        inst.hide();
      });
    });

    // 使用状況フィルター
    const filterBadges = modalEl.querySelectorAll('#photo-pool-picker-usage-filter .badge-filter');
    const items = modalEl.querySelectorAll('.photo-pool-picker-item');
    filterBadges.forEach(function(badge) {
      badge.addEventListener('click', function() {
        filterBadges.forEach(function(b) {
          b.classList.remove('badge-filter-active');
          b.classList.add('badge-filter-inactive');
        });
        badge.classList.remove('badge-filter-inactive');
        badge.classList.add('badge-filter-active');
        const usage = badge.dataset.usage;
        items.forEach(function(item) {
          const count = parseInt(item.dataset.usageCount || '0', 10);
          let show = true;
          if (usage === 'unused') show = count === 0;
          if (usage === 'used') show = count > 0;
          item.style.display = show ? '' : 'none';
        });
      });
    });
  });
})();
