"""Hermes の curl から作った・変えた・見たデータを取り出す処理のテスト"""
import json

from app.utils.conversation_links import extract_links

TOKEN_HDR = '-H "Authorization: Bearer $GARDEN_API_TOKEN"'


def call(mid, command, call_id='call_1'):
    return {'hermes_message_id': mid, 'role': 'assistant', 'content': '', 'tool_call_id': None,
            'tool_calls': json.dumps([{'id': call_id, 'call_id': call_id,
                'function': {'name': 'terminal', 'arguments': json.dumps({'command': command, 'timeout': 30})}}])}


def result(mid, body, call_id='call_1'):
    return {'hermes_message_id': mid, 'role': 'tool', 'content': body, 'tool_calls': None, 'tool_call_id': call_id}


def link(t, i, k, mid):
    return {'entity_type': t, 'entity_id': i, 'kind': k, 'hermes_message_id': mid}


def test_get_with_id_is_viewed():
    msgs = [call(1, f'curl -sS {TOKEN_HDR} "$GARDEN_API_URL/plantings/45"')]
    assert extract_links(msgs) == [link('planting', 45, 'viewed', 1)]


def test_image_download_is_viewed():
    msgs = [call(1, f'curl -sS {TOKEN_HDR} -o /tmp/x.jpg "$GARDEN_API_URL/planting_records/312/image?size=thumb"')]
    assert extract_links(msgs) == [link('planting_record', 312, 'viewed', 1)]


def test_list_search_and_lookup_are_ignored():
    msgs = [
        call(1, f"curl -sS -G {TOKEN_HDR} \"$GARDEN_API_URL/plantings\" --data-urlencode 'crop_id=1'", 'a'),
        call(2, f"curl -sS -G {TOKEN_HDR} \"$GARDEN_API_URL/lookup\" --data-urlencode 'q=ジャガイモ'", 'b'),
        call(3, f'curl -sS {TOKEN_HDR} "$GARDEN_API_URL/meta"', 'c'),
    ]
    assert extract_links(msgs) == []


def test_post_created_from_matching_result():
    msgs = [
        call(1, f'curl -sS -X POST {TOKEN_HDR} "$GARDEN_API_URL/planting_records" -F data=\'{{"memo":"芽が出た"}}\''),
        result(2, '{"ok": true, "data": {"id": 312, "memo": "x"}}'),
    ]
    assert extract_links(msgs) == [link('planting_record', 312, 'created', 1)]


def test_post_photos_list_creates_each():
    msgs = [
        call(1, f'curl -sS -X POST {TOKEN_HDR} -F "files=@/tmp/a.jpg" "$GARDEN_API_URL/photos"'),
        result(2, '{"ok": true, "data": [{"id": 7}, {"id": 8}]}'),
    ]
    assert extract_links(msgs) == [link('photo_pool', 7, 'created', 1), link('photo_pool', 8, 'created', 1)]


def test_patch_end_images_are_updated():
    msgs = [
        call(1, f'curl -sS -X PATCH {TOKEN_HDR} "$GARDEN_API_URL/plantings/45" -d \'{{"memo":"a"}}\'', 'a'),
        call(2, f'curl -sS -X POST {TOKEN_HDR} "$GARDEN_API_URL/plantings/45/end"', 'b'),
        call(3, f'curl -sS -X POST {TOKEN_HDR} -F "images=@/tmp/a.jpg" "$GARDEN_API_URL/crops/3/images"', 'c'),
    ]
    # 同じデータの updated は重複させず、最初の発言に結び付ける
    assert extract_links(msgs) == [link('planting', 45, 'updated', 1), link('crop', 3, 'updated', 3)]


def test_form_without_x_is_post_and_g_is_get():
    msgs = [
        call(1, f'curl -sS {TOKEN_HDR} -F data=\'{{"a":1}}\' "$GARDEN_API_URL/harvests"', 'a'),
        result(2, '{"data": {"id": 5}}', 'a'),
        call(3, f"curl -sS -G {TOKEN_HDR} -d 'q=a' \"$GARDEN_API_URL/harvests/9\"", 'b'),
    ]
    assert extract_links(msgs) == [link('harvest', 5, 'created', 1), link('harvest', 9, 'viewed', 3)]


def test_two_posts_in_one_command_skip_created():
    cmd = (f'curl -sS -X POST {TOKEN_HDR} "$GARDEN_API_URL/crops" -d \'{{}}\' && '
           f'curl -sS -X POST {TOKEN_HDR} "$GARDEN_API_URL/varieties" -d \'{{}}\'')
    msgs = [call(1, cmd), result(2, '{"data": {"id": 1}}')]
    assert extract_links(msgs) == []


def test_literal_url_and_braced_var():
    cmd = 'curl -sS http://127.0.0.1:5001/api/v1/tasks/4; curl -sS "${GARDEN_API_URL}/tasks/5"'
    assert extract_links([call(1, cmd)]) == [link('task', 4, 'viewed', 1), link('task', 5, 'viewed', 1)]


def test_broken_json_is_ignored():
    bad_args = {'hermes_message_id': 1, 'role': 'assistant', 'content': '', 'tool_call_id': None,
                'tool_calls': json.dumps([{'id': 'x', 'function': {'name': 'terminal', 'arguments': 'not json'}}])}
    bad_calls = {'hermes_message_id': 2, 'role': 'assistant', 'content': '', 'tool_call_id': None,
                 'tool_calls': 'not json'}
    msgs = [bad_args, bad_calls,
            call(3, f'curl -sS -X POST {TOKEN_HDR} "$GARDEN_API_URL/crops"', 'z'),
            result(4, 'not json', 'z'),
            call(5, 'curl -sS "unterminated $GARDEN_API_URL/crops/1', 'q')]
    assert extract_links(msgs) == [link('crop', 1, 'viewed', 5)]


def test_pipe_and_heredoc_and_japanese():
    cmd = f'curl -sS {TOKEN_HDR} "$GARDEN_API_URL/crops/2" | python3 -c "import sys,json\nprint(json.load(sys.stdin))"'
    assert extract_links([call(1, cmd)]) == [link('crop', 2, 'viewed', 1)]


def test_non_ascii_digit_ids_are_ignored():
    msgs = [call(1, 'curl -sS "$GARDEN_API_URL/crops/²"', 'a'),
            call(2, 'curl -sS "$GARDEN_API_URL/crops/٣"', 'b')]
    assert extract_links(msgs) == []


def test_out_of_range_ids_are_ignored():
    msgs = [call(1, 'curl -sS "$GARDEN_API_URL/crops/99999999999999999999999"', 'a'),
            call(2, 'curl -sS "$GARDEN_API_URL/crops/0"', 'b'),
            call(3, f'curl -sS -X POST {TOKEN_HDR} "$GARDEN_API_URL/photos"', 'c'),
            result(4, '{"data": [{"id": 99999999999999999999999}, {"id": true}, {"id": 0}, {"id": "5"}, {"id": 9}]}', 'c')]
    assert extract_links(msgs) == [link('photo_pool', 9, 'created', 3)]
