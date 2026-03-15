/**
 * Canvas Preview — read-only display of garden layout
 */

class CanvasPreview {
    constructor(container) {
        this.container = container;
        this.locationId = container.dataset.locationId;
        this.bgImage = container.dataset.bgImage;
        this.highlightId = container.dataset.highlightId ? parseInt(container.dataset.highlightId) : null;
        this.area = container.querySelector('.canvas-preview-area');

        this._init();
    }

    async _init() {
        // Set background image
        if (this.bgImage) {
            this.area.style.backgroundImage = `url('/static/images/location_bg_images/${this.bgImage}')`;
        }

        // インライン JSON がある場合はそちらを優先
        const inlineJson = this.container.dataset.canvasJson;
        if (inlineJson) {
            try {
                const data = JSON.parse(inlineJson);
                if (data.version === '2.0' && data.placements?.length > 0) {
                    this._render(data.placements);
                } else {
                    this._showEmpty();
                }
            } catch {
                this._showEmpty();
            }
            return;
        }

        try {
            const res = await fetch(`/locations/${this.locationId}/canvas/data`);
            const data = await res.json();

            if (data.version !== '2.0' || !data.placements || data.placements.length === 0) {
                this._showEmpty();
                return;
            }

            this._render(data.placements);
        } catch (e) {
            this._showEmpty();
        }
    }

    _render(placements) {
        const SCALE = 0.5; // 800px → 400px

        placements.forEach(p => {
            const el = document.createElement('div');
            el.className = 'placed-crop-preview';
            el.style.left = `${Math.round(p.x * SCALE)}px`;
            el.style.top = `${Math.round(p.y * SCALE)}px`;

            const color = p.imageColor || '#4CAF50';

            if (p.iconPath) {
                const img = document.createElement('img');
                img.src = `/static/images/crop_icons/${p.iconPath}`;
                img.alt = p.cropName || '';
                img.style.borderColor = color;
                img.onerror = () => {
                    img.replaceWith(this._makeFallback(color));
                };
                el.appendChild(img);
            } else {
                el.appendChild(this._makeFallback(color));
            }

            const label = document.createElement('span');
            label.className = 'placed-crop-label';
            label.textContent = p.variety ? `${p.variety}（${p.cropName}）` : (p.cropName || '');
            el.appendChild(label);

            if (this.highlightId !== null) {
                if (p.locationCropId === this.highlightId) {
                    el.classList.add('highlight');
                    el.style.setProperty('--highlight-color', color);
                } else {
                    el.classList.add('dimmed');
                }
            }

            this.area.appendChild(el);
        });
    }

    _makeFallback(color) {
        const div = document.createElement('div');
        div.className = 'placed-crop-preview-fallback';
        div.style.backgroundColor = color;
        div.style.borderColor = color;
        div.innerHTML = '<i class="bi bi-flower1"></i>';
        return div;
    }

    _showEmpty() {
        const msg = document.createElement('div');
        msg.className = 'canvas-preview-empty';
        msg.innerHTML = '<i class="bi bi-map"></i> 見取り図が設定されていません';
        this.area.appendChild(msg);
    }

    updateData(data) {
        this.area.innerHTML = '';
        if (data && data.version === '2.0' && data.placements && data.placements.length > 0) {
            this._render(data.placements);
        } else {
            this._showEmpty();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.canvas-preview-container').forEach(el => {
        if (el.dataset.manualInit) return;
        new CanvasPreview(el);
    });
});
