from app.utils.crop_icons import list_crop_icons


def test_meta_crop_icons_uses_new_order(api):
    data = api.get('/api/v1/meta').get_json()['data']
    assert data['crop_icons'] == list_crop_icons()
