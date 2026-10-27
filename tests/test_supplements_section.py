from app.database import get_db


def test_add_tabs_default_to_image_and_text_is_last(app, client):
    """補足情報の追加タブは使われる順（画像・URL・YouTube・テキスト）で、画像が最初に開く"""
    with app.app_context():
        db = get_db()
        crop_id = db.execute("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'トマト')").lastrowid
        db.commit()
    body = client.get(f'/crops/{crop_id}').get_data(as_text=True)
    order = [body.index(f'id="tab-{t}"') for t in ('image', 'url', 'youtube', 'text')]
    assert order == sorted(order)
    assert 'class="nav-link active" id="tab-image"' in body
    assert 'class="tab-pane fade show active" id="pane-image"' in body
    assert 'class="nav-link" id="tab-text"' in body
