// 詳細画面の「Hermes のアドバイス」欄の絞り込み。
// 入力した文字を、見出し・相談・アドバイスの本文に含まない項目を隠す。
(function () {
    const input = document.getElementById('advice-filter');
    if (!input) return;
    const items = document.querySelectorAll('#advice-accordion .advice-item');
    const noMatch = document.getElementById('advice-no-match');

    input.addEventListener('input', function () {
        const keyword = input.value.trim().toLowerCase();
        let shown = 0;
        items.forEach(function (item) {
            const hit = !keyword || item.textContent.toLowerCase().includes(keyword);
            item.classList.toggle('d-none', !hit);
            if (hit) shown++;
        });
        if (noMatch) noMatch.classList.toggle('d-none', shown > 0);
    });
})();
