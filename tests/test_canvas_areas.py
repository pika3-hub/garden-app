import json
import math

import pytest

from app.utils.canvas_areas import (
    AreaError, area_grid, area_name, cell_of, choose_spot, crowded_warning, edge_labels,
    parse_area, placements_of, planting_cells, area_names,
)

VISUAL = [['左上', '上', '右上'], ['左', '中央', '右'], ['左下', '下', '右下']]


@pytest.mark.parametrize('top, grid', [
    (None, VISUAL),
    ('北', [['北西', '北', '北東'], ['西', '中央', '東'], ['南西', '南', '南東']]),
    ('東', [['北東', '東', '南東'], ['北', '中央', '南'], ['北西', '西', '南西']]),
    ('南', [['南東', '南', '南西'], ['東', '中央', '西'], ['北東', '北', '北西']]),
    ('西', [['南西', '西', '北西'], ['南', '中央', '北'], ['南東', '東', '北東']]),
])
def test_area_grid(top, grid):
    assert area_grid(top) == grid
    assert area_name((0, 0), top) == grid[0][0]


def test_edge_labels():
    assert edge_labels('東') == {'top': '東', 'right': '南', 'bottom': '西', 'left': '北'}
    assert edge_labels(None) is None


@pytest.mark.parametrize('x, y, cell', [
    (0, 0, (0, 0)),
    (241, 0, (0, 0)),      # 中心 266 は左の列
    (242, 0, (0, 1)),      # 中心 267 は真ん中の列
    (750, 750, (2, 2)),
    (-10, 900, (2, 0)),    # 範囲外は端に丸める
])
def test_cell_of_uses_icon_center(x, y, cell):
    assert cell_of(x, y) == cell


@pytest.mark.parametrize('name, top, cell', [
    ('北', '東', (1, 0)),
    ('左', '東', (1, 0)),          # 見た目の名前も受け付ける
    ('中央', None, (1, 1)),
    ('左下', None, (2, 0)),
    (' 北エリア ', '北', (0, 1)),  # 空白と「エリア」を許す
])
def test_parse_area(name, top, cell):
    assert parse_area(name, top) == cell


def test_parse_area_direction_without_top():
    with pytest.raises(AreaError) as e:
        parse_area('北', None)
    assert str(e.value) == 'この場所は見取り図の上の方角が未設定なので、上・左下などで指定してください'


def test_parse_area_unknown_lists_choices():
    with pytest.raises(AreaError) as e:
        parse_area('北北東', '北')
    assert '北西' in str(e.value) and '左上' in str(e.value)


def test_placements_of_ignores_broken_data():
    assert placements_of(None) == []
    assert placements_of('not json') == []
    assert placements_of({'objects': []}) == []          # Fabric.js の旧形式
    good = {'locationCropId': 1, 'x': 10, 'y': 20}
    data = {'version': '2.0', 'placements': [good, {'locationCropId': 2}, {'x': 'a', 'y': 1}]}
    assert placements_of(data) == [good]
    assert placements_of(json.dumps(data)) == [good]


def test_planting_cells_unique_and_ordered():
    placements = [
        {'locationCropId': 5, 'x': 700, 'y': 300},   # (1, 2)
        {'locationCropId': 5, 'x': 700, 'y': 10},    # (0, 2)
        {'locationCropId': 5, 'x': 690, 'y': 20},    # (0, 2) 重複
        {'locationCropId': 6, 'x': 0, 'y': 0},
    ]
    assert planting_cells(placements, 5) == [(0, 2), (1, 2)]
    assert area_names(placements, 5, '東') == ['南東', '南']
    assert planting_cells(placements, 99) == []


def _center(spot):
    return spot.x + 25, spot.y + 25


def test_choose_spot_empty_is_cell_center():
    spot = choose_spot([], (0, 1))
    assert (spot.x, spot.y, spot.nearest) == (375, 108, None)


def test_choose_spot_stays_inside_cell_and_far_from_icon():
    placements = [{'locationCropId': 1, 'x': 375, 'y': 375}]   # 中央マスの真ん中
    spot = choose_spot(placements, (1, 1))
    assert cell_of(spot.x, spot.y) == (1, 1)
    lo, hi = 800 / 3, 1600 / 3
    assert lo <= spot.x and spot.x + 50 <= hi and lo <= spot.y and spot.y + 50 <= hi
    assert spot.nearest >= 140     # 角まで約 152px（候補の刻み方で数 px 変わる）


def test_choose_spot_counts_icons_in_neighbor_cells():
    placements = [{'locationCropId': 1, 'x': 515, 'y': 375}]   # 右のマスの境目近く
    spot = choose_spot(placements, (1, 1))
    assert _center(spot)[0] < 400


def test_choose_spot_crowded_reports_distance():
    placements = [{'locationCropId': 1, 'x': x - 25, 'y': y - 25}
                  for x in range(292, 509, 40) for y in range(292, 509, 40)]
    spot = choose_spot(placements, (1, 1))
    assert cell_of(spot.x, spot.y) == (1, 1)
    assert spot.nearest < 50
    assert crowded_warning('北') == '北エリアは混んでいて、ほかのアイコンと重なっています。画面で確かめてください'


def test_choose_spot_is_deterministic():
    placements = [{'locationCropId': 1, 'x': 100, 'y': 100}]
    assert choose_spot(placements, (0, 0)) == choose_spot(placements, (0, 0))
