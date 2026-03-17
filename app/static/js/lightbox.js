// ライトボックス（フルスクリーン画像ビューア）
document.addEventListener('DOMContentLoaded', function () {
    // オーバーレイ要素を生成
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML = '<button class="lightbox-close" aria-label="閉じる">&times;</button><img src="" alt="">';
    document.body.appendChild(overlay);

    const overlayImg = overlay.querySelector('img');
    const closeBtn = overlay.querySelector('.lightbox-close');

    function open(src, alt) {
        overlayImg.src = src;
        overlayImg.alt = alt || '';
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    // イベント委譲: img.lightbox-target のクリック
    document.addEventListener('click', function (e) {
        const target = e.target.closest('img.lightbox-target');
        if (target) {
            open(target.src, target.alt);
        }
    });

    // 閉じる: ×ボタン
    closeBtn.addEventListener('click', close);

    // 閉じる: オーバーレイ背景クリック（画像自体は除外）
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) {
            close();
        }
    });

    // 閉じる: Escapeキー
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.classList.contains('active')) {
            close();
        }
    });
});
