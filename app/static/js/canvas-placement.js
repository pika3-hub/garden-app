/**
 * Canvas Placement - Wrapper for canvas-editor.js used on the planting placement page.
 * Highlights the new crop and redirects to planting detail after save.
 */
document.addEventListener('DOMContentLoaded', function() {
    const detailUrl = document.getElementById('detail-url').value;

    // Wait a tick to ensure canvas-editor.js DOMContentLoaded has run
    setTimeout(function() {
        const editor = window._canvasEditor;
        if (!editor) return;

        // Override save button: redirect to detail page after save
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            // Remove existing click listeners by replacing the button
            const newSaveBtn = saveBtn.cloneNode(true);
            saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);

            newSaveBtn.addEventListener('click', async function() {
                const locationId = editor.locationId;
                const data = editor.buildSaveData();
                const indicator = document.getElementById('save-indicator');

                try {
                    const resp = await fetch(`/locations/${locationId}/canvas/save`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    if (resp.ok) {
                        if (indicator) {
                            indicator.textContent = '保存しました！リダイレクト中...';
                            indicator.style.color = '#198754';
                        }
                        setTimeout(function() {
                            window.location.href = detailUrl;
                        }, 500);
                    } else {
                        if (indicator) {
                            indicator.textContent = '保存に失敗しました';
                            indicator.style.color = '#dc3545';
                        }
                    }
                } catch (e) {
                    if (indicator) {
                        indicator.textContent = '通信エラー';
                        indicator.style.color = '#dc3545';
                    }
                }
            });
        }

        // Scroll the new crop item into view
        const newItem = document.querySelector('.crop-item-new');
        if (newItem) {
            newItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 0);
});
