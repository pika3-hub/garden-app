/**
 * Canvas History — slider-based historical garden layout viewer
 * Integrated into the main 見取り図 card.
 * Slides only to dates where the layout changes (planted_date / end_date),
 * with today's date always at the right end.
 */
document.addEventListener('DOMContentLoaded', async () => {
    const sliderArea = document.getElementById('history-slider-area');
    const slider = document.getElementById('history-slider');
    const dateDisplay = document.getElementById('history-date-display');
    const dateMin = document.getElementById('history-date-min');
    const dateMax = document.getElementById('history-date-max');
    const container = document.getElementById('history-canvas');

    if (!container) return;

    const locationId = container.dataset.locationId;

    // Initialize preview (manual init — always show current canvas first)
    const preview = new CanvasPreview(container);

    // Load current canvas_data as initial display
    try {
        const res = await fetch(`/locations/${locationId}/canvas/data`);
        const data = await res.json();
        preview.updateData(data);
    } catch {
        preview.updateData(null);
    }

    // Fetch change dates for slider
    if (!sliderArea || !slider) return;

    let dates;
    try {
        const res = await fetch(`/locations/${locationId}/canvas/history/range`);
        const data = await res.json();
        dates = data.dates;
    } catch {
        return;
    }

    if (!dates || dates.length === 0) return;

    // Show the slider area
    sliderArea.style.display = '';

    dateMin.textContent = dates[0];
    dateMax.textContent = dates[dates.length - 1];
    slider.min = 0;
    slider.max = dates.length - 1;
    slider.value = dates.length - 1;
    dateDisplay.textContent = dates[dates.length - 1];

    // The last date is always today — use current canvas_data for it
    const todayDate = dates[dates.length - 1];

    // Load data for a given date
    let debounceTimer = null;
    async function loadDate(dateStr) {
        dateDisplay.textContent = dateStr;
        try {
            const url = (dateStr === todayDate)
                ? `/locations/${locationId}/canvas/data`
                : `/locations/${locationId}/canvas/history?date=${dateStr}`;
            const res = await fetch(url);
            const data = await res.json();
            preview.updateData(data);
        } catch {
            preview.updateData(null);
        }
    }

    // Slider event with debounce
    slider.addEventListener('input', () => {
        const dateStr = dates[parseInt(slider.value)];
        dateDisplay.textContent = dateStr;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => loadDate(dateStr), 200);
    });
});
