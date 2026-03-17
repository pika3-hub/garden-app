/**
 * Canvas Fullscreen — full-screen overlay for garden layout preview
 * Opens a large-scale view of the CanvasPreview with optional date navigation.
 */
document.addEventListener('DOMContentLoaded', () => {
    // --- Build overlay DOM (once) ---
    const overlay = document.createElement('div');
    overlay.className = 'canvas-fullscreen-overlay';

    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'canvas-fullscreen-close';
    closeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
    closeBtn.title = '閉じる';
    overlay.appendChild(closeBtn);

    // Canvas wrapper
    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'canvas-fullscreen-canvas-wrap';
    overlay.appendChild(canvasWrap);

    // Preview container inside the wrapper
    const previewContainer = document.createElement('div');
    previewContainer.className = 'canvas-preview-container';
    previewContainer.dataset.manualInit = 'true';
    const previewArea = document.createElement('div');
    previewArea.className = 'canvas-preview-area';
    previewContainer.appendChild(previewArea);
    canvasWrap.appendChild(previewContainer);

    // Date navigation bar
    const datebar = document.createElement('div');
    datebar.className = 'canvas-fullscreen-datebar hidden';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'canvas-fullscreen-nav';
    prevBtn.innerHTML = '<i class="bi bi-chevron-left"></i>&nbsp;前へ';

    const dateInfo = document.createElement('div');
    dateInfo.style.textAlign = 'center';
    const dateLabel = document.createElement('div');
    dateLabel.className = 'canvas-fullscreen-date-label';
    const dateCounter = document.createElement('div');
    dateCounter.className = 'canvas-fullscreen-date-counter';
    dateInfo.appendChild(dateLabel);
    dateInfo.appendChild(dateCounter);

    const nextBtn = document.createElement('button');
    nextBtn.className = 'canvas-fullscreen-nav';
    nextBtn.innerHTML = '次へ&nbsp;<i class="bi bi-chevron-right"></i>';

    datebar.appendChild(prevBtn);
    datebar.appendChild(dateInfo);
    datebar.appendChild(nextBtn);
    overlay.appendChild(datebar);

    document.body.appendChild(overlay);

    // --- CanvasPreview instance for the overlay ---
    let preview = null;

    // --- State ---
    let currentConfig = null;
    let currentDateIndex = 0;

    // --- Scaling ---
    // Apply scale on canvasWrap (outer div), NOT on previewArea.
    // CanvasPreview's ResizeObserver controls previewArea's transform internally;
    // scaling the outer wrapper avoids conflicts.
    function applyFullscreenScale() {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const hasDatebar = !datebar.classList.contains('hidden');
        const datebarHeight = hasDatebar ? 60 : 0;
        const availW = vw * 0.92;
        const availH = (vh - datebarHeight) * (hasDatebar ? 0.85 : 0.92);
        const scale = Math.min(availW, availH) / 400;

        canvasWrap.style.transform = `scale(${scale})`;
        canvasWrap.style.transformOrigin = 'center center';
        canvasWrap.style.width = '400px';
        canvasWrap.style.height = '400px';
    }

    window.addEventListener('resize', () => {
        if (overlay.classList.contains('active')) {
            applyFullscreenScale();
        }
    });

    // --- Data loading ---
    async function loadCanvasData(locationId, date) {
        const url = date
            ? `/locations/${locationId}/canvas/history?date=${date}`
            : `/locations/${locationId}/canvas/data`;
        const res = await fetch(url);
        return await res.json();
    }

    // --- Date navigation ---
    function updateDateControls() {
        if (!currentConfig || !currentConfig.dates) return;
        const dates = currentConfig.dates;
        const idx = currentDateIndex;
        dateLabel.textContent = dates[idx];
        dateCounter.textContent = `(${idx + 1} / ${dates.length})`;
        prevBtn.disabled = (idx <= 0);
        nextBtn.disabled = (idx >= dates.length - 1);
    }

    async function navigateTo(idx) {
        if (!currentConfig || !currentConfig.dates) return;
        const dates = currentConfig.dates;
        if (idx < 0 || idx >= dates.length) return;
        currentDateIndex = idx;
        updateDateControls();

        const isLast = (idx === dates.length - 1);
        try {
            const data = await loadCanvasData(
                currentConfig.locationId,
                isLast ? null : dates[idx]
            );
            preview.updateData(data);
        } catch {
            preview.updateData(null);
        }
    }

    prevBtn.addEventListener('click', () => navigateTo(currentDateIndex - 1));
    nextBtn.addEventListener('click', () => navigateTo(currentDateIndex + 1));

    // --- Public API ---
    window.openCanvasFullscreen = async function(config) {
        currentConfig = config;

        // Initialize preview if first time
        if (!preview) {
            preview = new CanvasPreview(previewContainer);
        }

        // Set background image
        const bgImage = config.bgImage || 'bg_image_default.png';
        previewContainer.dataset.bgImage = bgImage;
        previewArea.style.backgroundImage = `url('/static/images/location_bg_images/${bgImage}')`;

        // Set highlight
        if (config.highlightId) {
            preview.highlightId = config.highlightId;
        } else {
            preview.highlightId = null;
        }

        // Show/hide datebar
        if (config.dates && config.dates.length > 0) {
            datebar.classList.remove('hidden');
            currentDateIndex = (config.currentDateIndex != null)
                ? config.currentDateIndex
                : config.dates.length - 1;
            updateDateControls();
        } else {
            datebar.classList.add('hidden');
        }

        // Load and display data
        if (config.canvasData) {
            preview.updateData(config.canvasData);
        } else if (config.dates && config.dates.length > 0) {
            // Load data for current date index
            const isLast = (currentDateIndex === config.dates.length - 1);
            try {
                const data = await loadCanvasData(
                    config.locationId,
                    isLast ? null : config.dates[currentDateIndex]
                );
                preview.updateData(data);
            } catch {
                preview.updateData(null);
            }
        } else {
            try {
                const data = await loadCanvasData(config.locationId, null);
                preview.updateData(data);
            } catch {
                preview.updateData(null);
            }
        }

        // Show overlay
        overlay.classList.add('active');
        applyFullscreenScale();
    };

    // --- Close ---
    function close() {
        overlay.classList.remove('active');

        // Dispatch event with current date index for syncing
        const detail = { currentDateIndex: currentDateIndex };
        document.dispatchEvent(new CustomEvent('canvas-fullscreen-close', { detail }));
    }

    closeBtn.addEventListener('click', close);

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) close();
    });

    document.addEventListener('keydown', (e) => {
        if (!overlay.classList.contains('active')) return;
        if (e.key === 'Escape') {
            close();
        } else if (e.key === 'ArrowLeft' && currentConfig && currentConfig.dates) {
            navigateTo(currentDateIndex - 1);
        } else if (e.key === 'ArrowRight' && currentConfig && currentConfig.dates) {
            navigateTo(currentDateIndex + 1);
        }
    });
});
