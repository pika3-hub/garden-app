// スライドショー（栽培記録画像ビューア）
document.addEventListener('DOMContentLoaded', function () {
    const targets = document.querySelectorAll('img.slideshow-target');
    if (targets.length === 0) return;

    // DOMから画像データを収集
    const slides = Array.from(targets).map(function (img) {
        return {
            src: img.src,
            date: img.dataset.slideshowDate || '',
            days: img.dataset.slideshowDays || '',
            caption: img.dataset.slideshowCaption || ''
        };
    });

    var currentIndex = 0;

    // オーバーレイ要素を生成
    var overlay = document.createElement('div');
    overlay.className = 'slideshow-overlay';
    overlay.innerHTML =
        '<button class="slideshow-close" aria-label="閉じる">&times;</button>' +
        '<button class="slideshow-nav prev" aria-label="前へ">&#10094;</button>' +
        '<img class="slideshow-main-img" src="" alt="栽培記録画像">' +
        '<button class="slideshow-nav next" aria-label="次へ">&#10095;</button>' +
        '<div class="slideshow-meta">' +
            '<div class="slideshow-info">' +
                '<span class="slideshow-date"></span>' +
                '<span class="slideshow-days"></span>' +
                '<span class="slideshow-caption"></span>' +
            '</div>' +
            '<span class="slideshow-counter"></span>' +
        '</div>';
    document.body.appendChild(overlay);

    var mainImg = overlay.querySelector('.slideshow-main-img');
    var closeBtn = overlay.querySelector('.slideshow-close');
    var prevBtn = overlay.querySelector('.slideshow-nav.prev');
    var nextBtn = overlay.querySelector('.slideshow-nav.next');
    var dateEl = overlay.querySelector('.slideshow-date');
    var daysEl = overlay.querySelector('.slideshow-days');
    var captionEl = overlay.querySelector('.slideshow-caption');
    var counterEl = overlay.querySelector('.slideshow-counter');

    function showImage(index) {
        currentIndex = index;
        var slide = slides[index];
        mainImg.src = slide.src;
        dateEl.textContent = slide.date ? slide.date : '';
        daysEl.textContent = slide.days ? '植え付けから ' + slide.days + '日目' : '';
        captionEl.textContent = slide.caption;
        counterEl.textContent = (index + 1) + ' / ' + slides.length;

        // 1枚しかないときはナビボタンを非表示
        prevBtn.style.display = slides.length <= 1 ? 'none' : '';
        nextBtn.style.display = slides.length <= 1 ? 'none' : '';
    }

    function open(index) {
        showImage(index);
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    function prev() {
        showImage((currentIndex - 1 + slides.length) % slides.length);
    }

    function next() {
        showImage((currentIndex + 1) % slides.length);
    }

    // 各画像クリックでスライドショーを開く
    targets.forEach(function (img, i) {
        img.addEventListener('click', function () {
            open(i);
        });
    });

    // スライドショーボタン
    var slideshowBtn = document.getElementById('slideshow-btn');
    if (slideshowBtn) {
        slideshowBtn.addEventListener('click', function () {
            open(0);
        });
    }

    // ナビボタン
    prevBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        prev();
    });
    nextBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        next();
    });

    // 閉じる
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) {
            close();
        }
    });

    // キーボード操作
    document.addEventListener('keydown', function (e) {
        if (!overlay.classList.contains('active')) return;
        if (e.key === 'Escape') close();
        else if (e.key === 'ArrowLeft') prev();
        else if (e.key === 'ArrowRight') next();
    });
});
