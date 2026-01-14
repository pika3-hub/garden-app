/**
 * Canvas Editor - Fabric.js based canvas drawing tool
 */

class CanvasEditor {
    constructor(canvasElementId, locationId) {
        this.canvas = new fabric.Canvas(canvasElementId, {
            width: 800,
            height: 600,
            backgroundColor: '#ffffff'
        });
        this.locationId = locationId;
        this.currentTool = 'select';
        this.autoSaveTimer = null;
        this.isDrawing = false;
        this.drawingObject = null;

        // Undo/Redo用の履歴管理
        this.history = [];
        this.historyIndex = -1;
        this.maxHistory = 20;
        this.isLoadingState = false;

        // 色設定
        this.strokeColor = '#4caf50';
        this.fillColor = '#e8f5e9';
        this.fillEnabled = false;

        //グリッド設定
        this.gridEnabled = false;
        this.gridSize = 20;
        this.snapEnabled = false;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        this.setupZoom();
        this.setupSnap();
        this.setupMultiSelection();
        this.loadCanvasData();
        this.saveState(); // 初期状態を履歴に保存
    }

    setupEventListeners() {
        // ツールボタンクリック
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                this.currentTool = e.currentTarget.dataset.tool;
                this.updateCanvasMode();
            });
        });

        // 保存ボタンクリック
        document.getElementById('save-btn').addEventListener('click', () => {
            this.saveCanvasData();
        });

        // Undo/Redoボタン
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');
        if (undoBtn) undoBtn.addEventListener('click', () => this.undo());
        if (redoBtn) redoBtn.addEventListener('click', () => this.redo());

        // グリッドトグルボタン
        const gridBtn = document.getElementById('grid-btn');
        if (gridBtn) {
            gridBtn.addEventListener('click', () => {
                this.gridEnabled = !this.gridEnabled;
                this.toggleGrid();
                gridBtn.classList.toggle('active', this.gridEnabled);
            });
        }

        // スナップトグルボタン
        const snapBtn = document.getElementById('snap-btn');
        if (snapBtn) {
            snapBtn.addEventListener('click', () => {
                this.snapEnabled = !this.snapEnabled;
                snapBtn.classList.toggle('active', this.snapEnabled);
            });
        }

        // 色選択
        const strokeColorInput = document.getElementById('stroke-color');
        const fillColorInput = document.getElementById('fill-color');
        const fillEnabledCheckbox = document.getElementById('fill-enabled');

        if (strokeColorInput) {
            strokeColorInput.addEventListener('change', (e) => {
                this.strokeColor = e.target.value;
            });
        }

        if (fillColorInput) {
            fillColorInput.addEventListener('change', (e) => {
                this.fillColor = e.target.value;
            });
        }

        if (fillEnabledCheckbox) {
            fillEnabledCheckbox.addEventListener('change', (e) => {
                this.fillEnabled = e.target.checked;
                if (this.fillEnabled) {
                    fillColorInput.disabled = false;
                } else {
                    fillColorInput.disabled = true;
                }
            });
        }

        // キャンバスイベント
        this.canvas.on('object:modified', () => {
            this.saveState();
            this.scheduleAutoSave();
        });
        this.canvas.on('object:added', () => {
            if (!this.isLoadingState) {
                this.saveState();
                this.scheduleAutoSave();
            }
        });
        this.canvas.on('object:removed', () => {
            if (!this.isLoadingState) {
                this.saveState();
                this.scheduleAutoSave();
            }
        });

        // テキスト編集終了時に選択ツールに戻る
        this.canvas.on('text:editing:exited', () => {
            if (this.currentTool === 'text') {
                this.switchToSelectTool();
            }
        });

        // グリッド線が選択されないようにする
        this.canvas.on('selection:created', (e) => {
            if (e.selected) {
                const filtered = e.selected.filter(obj => !obj.isGridLine);
                if (filtered.length !== e.selected.length) {
                    this.canvas.discardActiveObject();
                    if (filtered.length > 0) {
                        this.canvas.setActiveObject(filtered.length === 1 ? filtered[0] : new fabric.ActiveSelection(filtered, { canvas: this.canvas }));
                    }
                }
            }
        });

        this.canvas.on('selection:updated', (e) => {
            if (e.selected) {
                const filtered = e.selected.filter(obj => !obj.isGridLine);
                if (filtered.length !== e.selected.length) {
                    this.canvas.discardActiveObject();
                    if (filtered.length > 0) {
                        this.canvas.setActiveObject(filtered.length === 1 ? filtered[0] : new fabric.ActiveSelection(filtered, { canvas: this.canvas }));
                    }
                }
            }
        });

        // 図形描画イベント
        this.canvas.on('mouse:down', (options) => this.onMouseDown(options));
        this.canvas.on('mouse:move', (options) => this.onMouseMove(options));
        this.canvas.on('mouse:up', (options) => this.onMouseUp(options));

        // 作物ドラッグ&ドロップ
        this.setupCropDragDrop();
    }

    switchToSelectTool() {
        this.currentTool = 'select';
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tool === 'select') {
                btn.classList.add('active');
            }
        });
        this.updateCanvasMode();
    }

    updateCanvasMode() {
        if (this.currentTool === 'select') {
            this.canvas.isDrawingMode = false;
            this.canvas.selection = true;
            this.canvas.forEachObject(obj => {
                obj.selectable = true;
            });
        } else if (this.currentTool === 'delete') {
            this.canvas.isDrawingMode = false;
            this.canvas.selection = true;
        } else {
            this.canvas.isDrawingMode = false;
            this.canvas.selection = false;
            this.canvas.forEachObject(obj => {
                obj.selectable = false;
            });
        }
    }

    onMouseDown(options) {
        if (this.currentTool === 'select' || this.currentTool === 'delete') return;

        this.isDrawing = true;
        const pointer = this.canvas.getPointer(options.e);
        const startX = pointer.x;
        const startY = pointer.y;

        if (this.currentTool === 'rect') {
            this.drawingObject = new fabric.Rect({
                left: startX,
                top: startY,
                width: 0,
                height: 0,
                fill: this.fillEnabled ? this.fillColor : 'transparent',
                stroke: this.strokeColor,
                strokeWidth: 2
            });
            this.canvas.add(this.drawingObject);
        } else if (this.currentTool === 'circle') {
            this.drawingObject = new fabric.Circle({
                left: startX,
                top: startY,
                radius: 0,
                fill: this.fillEnabled ? this.fillColor : 'transparent',
                stroke: this.strokeColor,
                strokeWidth: 2
            });
            this.canvas.add(this.drawingObject);
        } else if (this.currentTool === 'line') {
            this.drawingObject = new fabric.Line([startX, startY, startX, startY], {
                stroke: this.strokeColor,
                strokeWidth: 2
            });
            this.canvas.add(this.drawingObject);
        } else if (this.currentTool === 'text') {
            const text = new fabric.IText('テキスト', {
                left: startX,
                top: startY,
                fontSize: 20,
                fill: '#333'
            });
            this.canvas.add(text);
            this.canvas.setActiveObject(text);
            text.enterEditing();
            this.isDrawing = false;
        }
    }

    onMouseMove(options) {
        if (!this.isDrawing || !this.drawingObject) return;

        const pointer = this.canvas.getPointer(options.e);

        if (this.currentTool === 'rect') {
            const width = pointer.x - this.drawingObject.left;
            const height = pointer.y - this.drawingObject.top;
            this.drawingObject.set({ width: Math.abs(width), height: Math.abs(height) });
            if (width < 0) this.drawingObject.set({ left: pointer.x });
            if (height < 0) this.drawingObject.set({ top: pointer.y });
        } else if (this.currentTool === 'circle') {
            const radius = Math.sqrt(
                Math.pow(pointer.x - this.drawingObject.left, 2) +
                Math.pow(pointer.y - this.drawingObject.top, 2)
            );
            this.drawingObject.set({ radius: radius });
        } else if (this.currentTool === 'line') {
            this.drawingObject.set({ x2: pointer.x, y2: pointer.y });
        }

        this.canvas.renderAll();
    }

    onMouseUp(options) {
        if (this.currentTool === 'delete' && options.target) {
            this.canvas.remove(options.target);
            return;
        }

        // 図形描画完了後、選択ツールに戻る
        if (this.isDrawing && this.drawingObject) {
            this.switchToSelectTool();
        }

        this.isDrawing = false;
        this.drawingObject = null;
    }

    deleteSelected() {
        const activeObjects = this.canvas.getActiveObjects();
        if (activeObjects.length > 0) {
            activeObjects.forEach(obj => this.canvas.remove(obj));
            this.canvas.discardActiveObject();
            this.canvas.renderAll();
        }
    }

    duplicateSelected() {
        const activeObjects = this.canvas.getActiveObjects();
        if (activeObjects.length === 0) return;

        // グリッド線を除外
        const objectsToClone = activeObjects.filter(obj => !obj.isGridLine);
        if (objectsToClone.length === 0) return;

        const clonedObjects = [];
        objectsToClone.forEach((obj) => {
            obj.clone((cloned) => {
                cloned.set({
                    left: cloned.left + 10,
                    top: cloned.top + 10,
                });
                this.canvas.add(cloned);
                clonedObjects.push(cloned);

                // 最後のオブジェクトの複製が完了したら選択
                if (clonedObjects.length === objectsToClone.length) {
                    this.canvas.discardActiveObject();
                    if (clonedObjects.length === 1) {
                        this.canvas.setActiveObject(clonedObjects[0]);
                    } else {
                        const selection = new fabric.ActiveSelection(clonedObjects, {
                            canvas: this.canvas
                        });
                        this.canvas.setActiveObject(selection);
                    }
                    this.canvas.renderAll();
                }
            }, ['cropId', 'locationCropId', 'cropName', 'plantedDate']);
        });
    }

    setupCropDragDrop() {
        const cropItems = document.querySelectorAll('.crop-item');

        cropItems.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('cropId', item.dataset.cropId);
                e.dataTransfer.setData('locationCropId', item.dataset.locationCropId);
                e.dataTransfer.setData('cropName', item.dataset.cropName);
                e.dataTransfer.setData('plantedDate', item.dataset.plantedDate || '');
            });
        });

        const canvasContainer = document.querySelector('.canvas-container');

        canvasContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
        });

        canvasContainer.addEventListener('drop', (e) => {
            e.preventDefault();

            const cropId = e.dataTransfer.getData('cropId');
            const locationCropId = e.dataTransfer.getData('locationCropId');
            const cropName = e.dataTransfer.getData('cropName');
            const plantedDate = e.dataTransfer.getData('plantedDate');

            // 作物データがない場合はスキップ（キャンバス上のオブジェクト移動時）
            if (!cropId || !locationCropId || !cropName) {
                return;
            }

            const canvasEl = document.getElementById('canvas');
            const rect = canvasEl.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            this.addCropIcon(cropId, locationCropId, cropName, plantedDate, x, y);
        });
    }

    addCropIcon(cropId, locationCropId, cropName, plantedDate, x, y) {
        // 角丸四角形のアイコン
        const rect = new fabric.Rect({
            width: 80,
            height: 60,
            fill: '#4caf50',
            rx: 8,
            ry: 8,
            originX: 'center',
            originY: 'center'
        });

        // 作物名テキスト
        const nameText = new fabric.Text(cropName, {
            fontSize: 12,
            fill: '#ffffff',
            originX: 'center',
            originY: 'center',
            top: -10
        });

        // 植え付け日テキスト
        const dateText = new fabric.Text(plantedDate || '', {
            fontSize: 9,
            fill: '#e8f5e9',
            originX: 'center',
            originY: 'center',
            top: 8
        });

        // グループ化
        const elements = plantedDate ? [rect, nameText, dateText] : [rect, nameText];
        const group = new fabric.Group(elements, {
            left: x,
            top: y,
            cropId: cropId,
            locationCropId: locationCropId,
            cropName: cropName,
            plantedDate: plantedDate
        });

        this.canvas.add(group);
        this.canvas.setActiveObject(group);

        // 位置をDBに保存
        this.updateCropPosition(locationCropId, x, y);

        this.canvas.renderAll();
    }

    async updateCropPosition(locationCropId, x, y) {
        try {
            const response = await fetch(`/locations/${this.locationId}/crops/${locationCropId}/position`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ x, y })
            });

            if (!response.ok) {
                console.error('Failed to update crop position');
            }
        } catch (error) {
            console.error('Error updating crop position:', error);
        }
    }

    async loadCanvasData() {
        try {
            const response = await fetch(`/locations/${this.locationId}/canvas/data`);
            const data = await response.json();

            if (data.objects && data.objects.length > 0) {
                this.isLoadingState = true;
                this.canvas.loadFromJSON(data, () => {
                    this.canvas.renderAll();
                    this.isLoadingState = false;
                });
            }
        } catch (error) {
            console.error('Error loading canvas data:', error);
        }
    }

    getCanvasDataWithoutGridLines() {
        // グリッド線を除外したキャンバスデータを取得
        const canvasData = this.canvas.toJSON(['cropId', 'locationCropId', 'cropName', 'plantedDate', 'isGridLine']);
        canvasData.objects = canvasData.objects.filter(obj => !obj.isGridLine);
        return canvasData;
    }

    async saveCanvasData() {
        const indicator = document.getElementById('save-indicator');
        indicator.textContent = '保存中...';
        indicator.className = 'ms-2 text-warning';

        try {
            const canvasData = this.getCanvasDataWithoutGridLines();

            const response = await fetch(`/locations/${this.locationId}/canvas/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(canvasData)
            });

            if (response.ok) {
                indicator.textContent = '保存完了';
                indicator.className = 'ms-2 text-success';
                setTimeout(() => {
                    indicator.textContent = '';
                }, 2000);
            } else {
                throw new Error('Save failed');
            }
        } catch (error) {
            console.error('Error saving canvas data:', error);
            indicator.textContent = '保存失敗';
            indicator.className = 'ms-2 text-danger';
        }
    }

    scheduleAutoSave() {
        if (this.autoSaveTimer) {
            clearTimeout(this.autoSaveTimer);
        }

        this.autoSaveTimer = setTimeout(() => {
            this.saveCanvasData();
        }, 3000);
    }

    // Undo/Redo機能
    saveState() {
        if (this.isLoadingState) return;

        const state = JSON.stringify(this.getCanvasDataWithoutGridLines());
        this.history = this.history.slice(0, this.historyIndex + 1);
        this.history.push(state);

        if (this.history.length > this.maxHistory) {
            this.history.shift();
        } else {
            this.historyIndex++;
        }

        this.updateUndoRedoButtons();
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.loadState(this.history[this.historyIndex]);
            this.updateUndoRedoButtons();
        }
    }

    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            this.loadState(this.history[this.historyIndex]);
            this.updateUndoRedoButtons();
        }
    }

    loadState(state) {
        this.isLoadingState = true;
        this.canvas.loadFromJSON(state, () => {
            // グリッドが有効な場合は再表示
            if (this.gridEnabled) {
                this.showGrid();
            }
            this.canvas.renderAll();
            this.isLoadingState = false;
        });
    }

    updateUndoRedoButtons() {
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');

        if (undoBtn) {
            undoBtn.disabled = this.historyIndex <= 0;
        }

        if (redoBtn) {
            redoBtn.disabled = this.historyIndex >= this.history.length - 1;
        }
    }

    // キーボードショートカット
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            const activeObject = this.canvas.getActiveObject();

            // テキスト編集中はショートカットをスキップ
            if (activeObject && activeObject.isEditing) {
                // テキスト編集中のDelete/Backspaceは文字削除
                return;
            }

            // Ctrl+S: 保存
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveCanvasData();
                return;
            }

            // Ctrl+Z: Undo
            if (e.ctrlKey && !e.shiftKey && e.key === 'z') {
                e.preventDefault();
                this.undo();
                return;
            }

            // Ctrl+Shift+Z または Ctrl+Y: Redo
            if ((e.ctrlKey && e.shiftKey && e.key === 'z') || (e.ctrlKey && e.key === 'y')) {
                e.preventDefault();
                this.redo();
                return;
            }

            // Ctrl+D: 複製
            if (e.ctrlKey && e.key === 'd') {
                e.preventDefault();
                this.duplicateSelected();
                return;
            }

            // Delete/Backspace: 削除
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (activeObject) {
                    e.preventDefault();
                    this.deleteSelected();
                }
                return;
            }

            // ツール切り替え（Ctrl押下時以外）
            if (!e.ctrlKey && !e.altKey && !e.shiftKey) {
                const key = e.key.toLowerCase();
                let tool = null;

                switch(key) {
                    case 's': tool = 'select'; break;
                    case 'r': tool = 'rect'; break;
                    case 'c': tool = 'circle'; break;
                    case 'l': tool = 'line'; break;
                    case 't': tool = 'text'; break;
                    case 'd': tool = 'delete'; break;
                }

                if (tool) {
                    e.preventDefault();
                    this.switchTool(tool);
                }
            }
        });
    }

    switchTool(toolName) {
        this.currentTool = toolName;
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tool === toolName) {
                btn.classList.add('active');
            }
        });
        this.updateCanvasMode();
    }

    // グリッド機能
    toggleGrid() {
        if (this.gridEnabled) {
            this.showGrid();
        } else {
            this.hideGrid();
        }
    }

    showGrid() {
        const gridSize = this.gridSize;
        const canvas = this.canvas;

        // 既存のグリッド線を削除
        this.hideGrid();

        // グリッド線を描画
        this.gridLines = [];

        // 縦線
        for (let i = 0; i <= canvas.width / gridSize; i++) {
            const line = new fabric.Line([i * gridSize, 0, i * gridSize, canvas.height], {
                stroke: '#ddd',
                selectable: false,
                evented: false,
                strokeWidth: 1,
                isGridLine: true
            });
            this.gridLines.push(line);
            canvas.add(line);
            canvas.sendToBack(line);
        }

        // 横線
        for (let i = 0; i <= canvas.height / gridSize; i++) {
            const line = new fabric.Line([0, i * gridSize, canvas.width, i * gridSize], {
                stroke: '#ddd',
                selectable: false,
                evented: false,
                strokeWidth: 1,
                isGridLine: true
            });
            this.gridLines.push(line);
            canvas.add(line);
            canvas.sendToBack(line);
        }

        canvas.renderAll();
    }

    hideGrid() {
        if (this.gridLines) {
            this.gridLines.forEach(line => this.canvas.remove(line));
            this.gridLines = [];
        }
        this.canvas.renderAll();
    }

    setupSnap() {
        const gridSize = this.gridSize;

        this.canvas.on('object:moving', (e) => {
            const obj = e.target;
            // グリッド線は無視
            if (obj.isGridLine) return;

            if (this.snapEnabled && this.gridEnabled) {
                obj.set({
                    left: Math.round(obj.left / gridSize) * gridSize,
                    top: Math.round(obj.top / gridSize) * gridSize
                });
            }
        });
    }

    // ズーム機能
    setupZoom() {
        const canvas = this.canvas;

        canvas.on('mouse:wheel', (opt) => {
            const delta = opt.e.deltaY;
            let zoom = canvas.getZoom();
            zoom *= 0.999 ** delta;

            // ズーム範囲制限（50% ~ 200%）
            if (zoom > 2) zoom = 2;
            if (zoom < 0.5) zoom = 0.5;

            canvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
            opt.e.preventDefault();
            opt.e.stopPropagation();

            // ズーム倍率表示更新
            this.updateZoomIndicator(Math.round(zoom * 100));
        });
    }

    updateZoomIndicator(zoomPercent) {
        const zoomIndicator = document.getElementById('zoom-indicator');
        if (zoomIndicator) {
            zoomIndicator.textContent = `${zoomPercent}%`;
        }
    }

    // マルチセレクション機能
    setupMultiSelection() {
        // Fabric.jsの既存のマルチセレクション機能を有効化
        // ドラッグで範囲選択が可能
        this.canvas.selection = true;

        // Shift+クリックでの追加選択を実装
        let isShiftSelecting = false;

        this.canvas.on('mouse:down', (options) => {
            // selectツール以外の場合はスキップ
            if (this.currentTool !== 'select') return;

            // Shiftキーが押されていない場合はスキップ
            if (!options.e.shiftKey) return;

            // クリックされたオブジェクトがない場合はスキップ
            if (!options.target) return;

            // グリッド線の場合はスキップ
            if (options.target.isGridLine) return;

            isShiftSelecting = true;
        });

        this.canvas.on('mouse:up', (options) => {
            if (!isShiftSelecting) return;
            isShiftSelecting = false;

            // selectツール以外の場合はスキップ
            if (this.currentTool !== 'select') return;

            // Shiftキーが押されていない場合はスキップ
            if (!options.e || !options.e.shiftKey) return;

            // クリックされたオブジェクトがない場合はスキップ
            if (!options.target) return;

            // グリッド線の場合はスキップ
            if (options.target.isGridLine) return;

            const activeObject = this.canvas.getActiveObject();
            const clickedObject = options.target;

            // 現在の選択を取得
            let currentSelection = [];
            if (activeObject) {
                if (activeObject.type === 'activeSelection') {
                    currentSelection = activeObject.getObjects();
                } else {
                    currentSelection = [activeObject];
                }
            }

            // クリックされたオブジェクトが既に選択されているか確認
            const isAlreadySelected = currentSelection.includes(clickedObject);

            let newSelection;
            if (isAlreadySelected) {
                // 選択から除外
                newSelection = currentSelection.filter(obj => obj !== clickedObject);
            } else {
                // 選択に追加
                newSelection = [...currentSelection, clickedObject];
            }

            // グリッド線を除外
            newSelection = newSelection.filter(obj => !obj.isGridLine);

            // 新しい選択を設定
            this.canvas.discardActiveObject();
            if (newSelection.length > 0) {
                if (newSelection.length === 1) {
                    this.canvas.setActiveObject(newSelection[0]);
                } else {
                    const selection = new fabric.ActiveSelection(newSelection, {
                        canvas: this.canvas
                    });
                    this.canvas.setActiveObject(selection);
                }
            }

            this.canvas.requestRenderAll();
        });
    }
}

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    const locationId = document.getElementById('location-id').value;
    const editor = new CanvasEditor('canvas', locationId);
});
