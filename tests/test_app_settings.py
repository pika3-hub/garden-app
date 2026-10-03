from app.models.app_settings import AppSettings


def test_get_returns_default_when_missing(app):
    with app.app_context():
        assert AppSettings.get('region') is None
        assert AppSettings.get('region', '') == ''


def test_set_then_get(app):
    with app.app_context():
        AppSettings.set('region', '神奈川県（温暖地）')
        assert AppSettings.get('region') == '神奈川県（温暖地）'


def test_set_overwrites_existing_value(app):
    from app.database import get_db
    with app.app_context():
        AppSettings.set('region', '北海道')
        AppSettings.set('region', '沖縄県')
        assert AppSettings.get('region') == '沖縄県'
        rows = get_db().execute(
            'SELECT COUNT(*) AS n FROM app_settings WHERE key = ?', ('region',)
        ).fetchone()
        assert rows['n'] == 1
