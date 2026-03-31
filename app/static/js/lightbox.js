// ライトボックス（フルスクリーン画像ビューア）
document.addEventListener('DOMContentLoaded', function () {
    // オーバーレイ要素を生成
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML = '<button class="lightbox-close" aria-label="閉じる">&times;</button><img src="" alt="">';
    document.body.appendChild(overlay);

    const overlayImg = overlay.querySelector('img');
    const closeBtn = overlay.querySelector('.lightbox-close');
    let zoomed = false;

    function open(src, alt) {
        overlayImg.src = src;
        overlayImg.alt = alt || '';
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        zoomed = false;
        overlay.classList.remove('active', 'zoomed');
        overlay.scrollTop = 0;
        overlay.scrollLeft = 0;
        document.body.style.overflow = '';
    }

    function toggleZoom() {
        zoomed = !zoomed;
        if (zoomed) {
            overlay.classList.add('zoomed');
        } else {
            overlay.classList.remove('zoomed');
            overlay.scrollTop = 0;
            overlay.scrollLeft = 0;
        }
    }

    // イベント委譲: img.lightbox-target のクリック
    document.addEventListener('click', function (e) {
        const target = e.target.closest('img.lightbox-target');
        if (target) {
            open(target.src, target.alt);
        }
    });

    // 画像クリックでズームトグル
    overlayImg.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleZoom();
    });

    // 閉じる: ×ボタン
    closeBtn.addEventListener('click', close);

    // 閉じる: オーバーレイ背景クリック（画像自体は除外、ズーム中は無効）
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay && !zoomed) {
            close();
        }
    });

    // Escapeキー: ズーム中→ズーム解除、通常→閉じる
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.classList.contains('active')) {
            if (zoomed) {
                toggleZoom();
            } else {
                close();
            }
        }
    });
});
