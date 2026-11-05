/**
 * Canvas Areas — 見取り図の重ね表示
 * ふだんは縁の中央に方角の札、ボタンで 3×3 の点線の格子とエリア名に切り替える。
 * 位置は割合、字の大きさは対象の幅（800px のエディター / 400px のプレビュー）から決める。
 * アイコンより下（z-index:0）、pointer-events:none なので操作の邪魔をしない。
 */
(function () {
    const EDGE_STYLE = {
        top: 'top:1.2%;left:50%;transform:translateX(-50%)',
        bottom: 'bottom:1.2%;left:50%;transform:translateX(-50%)',
        left: 'left:1.2%;top:50%;transform:translateY(-50%)',
        right: 'right:1.2%;top:50%;transform:translateY(-50%)'
    };

    function attach(areaEl, config) {
        if (areaEl._canvasAreas) {
            areaEl._canvasAreas.config = config;
            areaEl._canvasAreas.reattach();
            return areaEl._canvasAreas;
        }

        const controller = {
            config: config || { names: [], edges: null },
            showGrid: false,
            layer: null,

            _build() {
                const layer = document.createElement('div');
                layer.className = 'canvas-areas-layer';
                // 幅 800 → 約 14px、400 → 約 7px では読めないので下限を 11px にする
                const width = areaEl.clientWidth || 400;
                layer.style.fontSize = `${Math.max(11, Math.round(width * 0.018))}px`;

                if (this.showGrid) {
                    const grid = document.createElement('div');
                    grid.className = 'canvas-areas-grid';
                    (this.config.names || []).forEach(row => {
                        row.forEach(name => {
                            const cell = document.createElement('div');
                            const label = document.createElement('span');
                            label.textContent = name;
                            cell.appendChild(label);
                            grid.appendChild(cell);
                        });
                    });
                    layer.appendChild(grid);
                } else if (this.config.edges) {
                    Object.keys(EDGE_STYLE).forEach(side => {
                        const text = this.config.edges[side];
                        if (!text) return;
                        const badge = document.createElement('span');
                        badge.className = 'canvas-areas-compass';
                        badge.style.cssText = EDGE_STYLE[side];
                        badge.textContent = text;
                        layer.appendChild(badge);
                    });
                }
                return layer;
            },

            /** 重ね表示を作り直して areaEl の先頭に置く（アイコンより下） */
            reattach() {
                if (this.layer && this.layer.parentNode) this.layer.remove();
                this.layer = this._build();
                areaEl.insertBefore(this.layer, areaEl.firstChild);
            },

            toggle() {
                this.showGrid = !this.showGrid;
                this.reattach();
                return this.showGrid;
            }
        };

        areaEl._canvasAreas = controller;
        controller.reattach();
        return controller;
    }

    /** data-canvas-areas（JSON）を読む。無い・壊れていれば null */
    function readConfig(el) {
        if (!el || !el.dataset.canvasAreas) return null;
        try {
            return JSON.parse(el.dataset.canvasAreas);
        } catch {
            return null;
        }
    }

    window.CanvasAreas = { attach: attach, readConfig: readConfig };

    // 格子のボタン: 押した時点で対象を引く（読み込み順に依存しない）
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-canvas-grid-toggle]');
        if (!btn) return;
        const target = document.getElementById(btn.dataset.canvasGridToggle);
        if (!target) return;
        // プレビューのコンテナ（#history-canvas など）なら中の領域を対象にする
        const area = target.classList.contains('canvas-preview-container')
            ? target.querySelector('.canvas-preview-area')
            : target;
        if (!area || !area._canvasAreas) return;
        const on = area._canvasAreas.toggle();
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
})();
