// 共通JavaScript機能

// 削除確認ダイアログ
function confirmDelete(itemName) {
    return confirm(`「${itemName}」を削除してもよろしいですか？\nこの操作は取り消せません。`);
}

// フォームバリデーション
document.addEventListener('DOMContentLoaded', function() {
    // Bootstrap form validation
    const forms = document.querySelectorAll('.needs-validation');

    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // 削除ボタンの確認ダイアログ
    const deleteButtons = document.querySelectorAll('[data-confirm-delete]');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const itemName = this.dataset.itemName || 'この項目';
            if (!confirmDelete(itemName)) {
                e.preventDefault();
            }
        });
    });

    // アラートの自動非表示
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// 日付フォーマット（YYYY-MM-DD形式）
function formatDate(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// 今日の日付を取得
function getToday() {
    return formatDate(new Date());
}
