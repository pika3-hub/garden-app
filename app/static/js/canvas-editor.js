/**
 * Canvas Editor - DOM-based simple crop placement tool
 */

class CanvasEditor {
    constructor(locationId) {
        this.locationId = locationId;
        this.canvasArea = document.getElementById('canvas-area');
        this.placements = []; // { id, locationCropId, cropId, x, y, iconPath, imageColor, cropName, variety, element }
        this.selectedId = null;
        this.nextId = 1;

        // Drag state
        this.dragState = null; // { id, offsetX, offsetY }

        this.init();
    }

    init() {
        this.setupBackground();
        this.setupSidebarDragDrop();
        this.setupCanvasEvents();
        this.setupSaveButton();
        this.setupDeleteButton();
        this.loadData();
    }

    setupBackground() {
        const bgImage = document.getElementById('bg-image').value;
        this.canvasArea.style.backgroundImage = `url('/static/images/location_bg_images/${bgImage}')`;
    }

    setupSidebarDragDrop() {
        document.querySelectorAll('.crop-item').forEach(item => {
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({
                    cropId: parseInt(item.dataset.cropId),
                    locationCropId: parseInt(item.dataset.locationCropId),
                    cropName: item.dataset.cropName,
                    variety: item.dataset.variety || '',
                    plantedDate: item.dataset.plantedDate || '',
                    iconPath: item.dataset.iconPath || '',
                    imageColor: item.dataset.imageColor || '#4CAF50'
                }));
            });
        });

        this.canvasArea.addEventListener('dragover', (e) => {
            e.preventDefault();
        });

        this.canvasArea.addEventListener('drop', (e) => {
            e.preventDefault();
            let data;
            try {
                data = JSON.parse(e.dataTransfer.getData('application/json'));
            } catch {
                return;
            }
            if (!data || !data.cropId) return;

            const rect = this.canvasArea.getBoundingClientRect();
            const x = Math.max(0, Math.min(e.clientX - rect.left - 25, 750));
            const y = Math.max(0, Math.min(e.clientY - rect.top - 25, 750));

            this.addPlacement({
                locationCropId: data.locationCropId,
                cropId: data.cropId,
                x: Math.round(x),
                y: Math.round(y),
                iconPath: data.iconPath,
                imageColor: data.imageColor,
                cropName: data.cropName,
                variety: data.variety
            });
        });
    }

    setupCanvasEvents() {
        // Click on canvas background to deselect
        this.canvasArea.addEventListener('pointerdown', (e) => {
            if (e.target === this.canvasArea) {
                this.deselectAll();
            }
        });
    }

    setupSaveButton() {
        document.getElementById('save-btn').addEventListener('click', () => this.save());
    }

    setupDeleteButton() {
        document.getElementById('delete-placement-btn').addEventListener('click', () => {
            if (this.selectedId !== null) {
                this.removePlacement(this.selectedId);
            }
        });
    }

    addPlacement(data) {
        const id = this.nextId++;
        const el = this.createPlacementElement(id, data);
        this.canvasArea.appendChild(el);

        const placement = { id, ...data, element: el };
        this.placements.push(placement);

        this.selectPlacement(id);
        return id;
    }

    createPlacementElement(id, data) {
        const el = document.createElement('div');
        el.className = 'placed-crop';
        el.dataset.placementId = id;
        el.style.left = data.x + 'px';
        el.style.top = data.y + 'px';

        // Icon
        const color = data.imageColor || '#4CAF50';
        if (data.iconPath) {
            const img = document.createElement('img');
            img.src = `/static/images/crop_icons/${data.iconPath}`;
            img.alt = data.cropName;
            img.draggable = false;
            img.style.borderColor = color;
            el.appendChild(img);
        } else {
            const iconDiv = document.createElement('div');
            iconDiv.className = 'placed-crop-fallback';
            iconDiv.style.background = color;
            iconDiv.style.borderColor = color;
            iconDiv.innerHTML = '<i class="bi bi-flower1"></i>';
            el.appendChild(iconDiv);
        }

        // Label
        const label = document.createElement('div');
        label.className = 'placed-crop-label';
        label.textContent = data.cropName;
        el.appendChild(label);

        // Events
        el.addEventListener('pointerdown', (e) => {
            e.stopPropagation();
            this.selectPlacement(id);
            this.startDrag(id, e);
        });

        return el;
    }

    selectPlacement(id) {
        this.deselectAll();
        this.selectedId = id;
        const p = this.placements.find(p => p.id === id);
        if (!p) return;

        p.element.classList.add('selected');

        // Show info panel
        const panel = document.getElementById('info-panel');
        document.getElementById('info-crop-name').textContent = p.cropName;
        document.getElementById('info-variety').textContent = p.variety || '';
        document.getElementById('info-planted-date').textContent = p.plantedDate ? `植え付け日: ${p.plantedDate}` : '';
        panel.style.display = 'block';
    }

    deselectAll() {
        this.selectedId = null;
        document.querySelectorAll('.placed-crop.selected').forEach(el => el.classList.remove('selected'));
        document.getElementById('info-panel').style.display = 'none';
    }

    startDrag(id, e) {
        const p = this.placements.find(p => p.id === id);
        if (!p) return;

        const rect = p.element.getBoundingClientRect();
        this.dragState = {
            id,
            offsetX: e.clientX - rect.left,
            offsetY: e.clientY - rect.top
        };

        const onMove = (e) => {
            if (!this.dragState) return;
            const areaRect = this.canvasArea.getBoundingClientRect();
            let x = e.clientX - areaRect.left - this.dragState.offsetX;
            let y = e.clientY - areaRect.top - this.dragState.offsetY;

            // Clamp to canvas area
            x = Math.max(0, Math.min(x, 750));
            y = Math.max(0, Math.min(y, 750));

            p.element.style.left = x + 'px';
            p.element.style.top = y + 'px';
            p.x = Math.round(x);
            p.y = Math.round(y);
        };

        const onUp = () => {
            this.dragState = null;
            document.removeEventListener('pointermove', onMove);
            document.removeEventListener('pointerup', onUp);
        };

        document.addEventListener('pointermove', onMove);
        document.addEventListener('pointerup', onUp);
    }

    removePlacement(id) {
        const idx = this.placements.findIndex(p => p.id === id);
        if (idx === -1) return;
        this.placements[idx].element.remove();
        this.placements.splice(idx, 1);
        this.deselectAll();
    }

    async save() {
        const indicator = document.getElementById('save-indicator');
        indicator.textContent = '保存中...';
        indicator.className = 'ms-2 text-warning';

        const data = {
            version: '2.0',
            placements: this.placements.map(p => ({
                locationCropId: p.locationCropId,
                cropId: p.cropId,
                x: p.x,
                y: p.y,
                iconPath: p.iconPath,
                imageColor: p.imageColor,
                cropName: p.cropName,
                variety: p.variety || ''
            }))
        };

        try {
            const response = await fetch(`/locations/${this.locationId}/canvas/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                indicator.textContent = '保存完了';
                indicator.className = 'ms-2 text-success';
                setTimeout(() => { indicator.textContent = ''; }, 2000);
            } else {
                throw new Error('Save failed');
            }
        } catch (error) {
            console.error('Error saving:', error);
            indicator.textContent = '保存失敗';
            indicator.className = 'ms-2 text-danger';
        }
    }

    async loadData() {
        try {
            const response = await fetch(`/locations/${this.locationId}/canvas/data`);
            const data = await response.json();

            // Only load version 2.0 data; ignore old Fabric.js format
            if (data.version === '2.0' && data.placements) {
                data.placements.forEach(p => {
                    this.addPlacement(p);
                });
                this.deselectAll();
            }
        } catch (error) {
            console.error('Error loading canvas data:', error);
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const locationId = document.getElementById('location-id').value;
    new CanvasEditor(locationId);
});
