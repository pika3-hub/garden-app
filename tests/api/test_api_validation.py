import pytest

from app.api.validation import (
    REF_CROP, Field, check_ref_id, check_value, validate_payload,
)


@pytest.mark.parametrize('field, value, expected', [
    (Field('str', max_len=5), 'トマト', 'トマト'),
    (Field('int'), 3, 3),
    (Field('int'), '3', 3),            # 文字列の数字も受け付ける
    (Field('int'), 3.0, 3),
    (Field('decimal'), '300', 300.0),
    (Field('decimal'), 1.5, 1.5),
    (Field('date'), '2026-10-09', '2026-10-09'),
    (Field('enum', choices=['a', 'b']), 'b', 'b'),
    (Field('color'), '#4caf50', '#4caf50'),
    (Field('str'), '', None),          # 空文字は「値を消す」
    (Field('str'), None, None),
])
def test_check_value_accepts(field, value, expected):
    assert check_value(field, value) == (expected, None)


@pytest.mark.parametrize('field, value, reason_part', [
    (Field('str', max_len=3), 'ミニトマト', '3文字以内'),
    (Field('str'), 123, '文字列'),
    (Field('int'), True, '整数'),
    (Field('int'), '3株', '整数'),
    (Field('int'), 10**30, '大きすぎ'),
    (Field('decimal'), '300g', '数値'),        # 単位付きは不可
    (Field('decimal'), float('nan'), '数値'),
    (Field('decimal', min_value=0), -1, '0 以上'),
    (Field('date'), '2026/10/09', 'YYYY-MM-DD'),
    (Field('date'), '2026-02-30', 'YYYY-MM-DD'),  # 実在しない日付
    (Field('enum', choices=['active', 'harvested']), 'done', 'active, harvested'),
    (Field('enum', choices=[f'icon_{i}.png' for i in range(30)]), 'x.png', 'GET /api/v1/meta'),
    (Field('color'), 'green', '#RRGGBB'),
    (Field('str', required=True), None, '必須'),
    (Field('str', required=True), '  ', '必須'),
])
def test_check_value_rejects(field, value, reason_part):
    converted, reason = check_value(field, value)
    assert converted is None
    assert reason_part in reason


def test_check_ref_id(api_app, sql):
    crop_id = sql("INSERT INTO crops (name, crop_type) VALUES ('トマト', 'ナス科')")
    with api_app.app_context():
        assert check_ref_id(REF_CROP, crop_id) == (crop_id, None)
        assert check_ref_id(REF_CROP, str(crop_id)) == (crop_id, None)
        _, reason = check_ref_id(REF_CROP, 999)
        assert 'ID 999 の作物は存在しません' in reason
        assert '/api/v1/lookup' in reason
        _, reason = check_ref_id(REF_CROP, 99999999999999999999)  # 桁あふれでも 500 にしない
        assert '存在しません' in reason
        _, reason = check_ref_id(REF_CROP, 'トマト')
        assert '整数の ID' in reason


FIELDS = {
    'name': Field('str', required=True, max_len=100),
    'notes': Field('str'),
}


def test_validate_payload_create_reports_all_errors():
    cleaned, errors = validate_payload(FIELDS, {'notes': 1, 'nmae': 'x', 'id': 3},
                                       creating=True, reserved=('photo_pool_id',),
                                       read_only=('id',))
    by_field = {e['field']: e['reason'] for e in errors}
    assert '文字列' in by_field['notes']
    assert '未知の項目' in by_field['nmae']
    assert 'name, notes, photo_pool_id' in by_field['nmae']
    assert '読み取り専用' in by_field['id']
    assert by_field['name'] == '必須項目です'
    assert cleaned == {}


def test_validate_payload_patch_only_checks_sent_fields():
    cleaned, errors = validate_payload(FIELDS, {'notes': '花が咲いた'}, creating=False)
    assert errors == []
    assert cleaned == {'notes': '花が咲いた'}


def test_validate_payload_skips_reserved_keys():
    cleaned, errors = validate_payload(FIELDS, {'name': 'a', 'relations': {}},
                                       creating=True, reserved=('relations',))
    assert errors == []
    assert cleaned == {'name': 'a'}


def test_validate_payload_includes_bad_value():
    _, errors = validate_payload({'d': Field('date')}, {'d': '10/9'}, creating=False)
    assert errors == [{'field': 'd', 'reason': errors[0]['reason'], 'value': '10/9'}]
