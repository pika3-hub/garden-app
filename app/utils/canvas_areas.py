"""見取り図のエリア（3×3）の計算。

キャンバスは 800×800px の座標系で、3×3 のマスに分ける。アイコンのマスは中心で決める。
マスの名前は、場所に上の方角（top）が設定されていれば方角、無ければ見た目（上・左下など）。
"""
import json
import math
from typing import NamedTuple

CANVAS_SIZE = 800
ICON_SIZE = 50
TOP_DIRECTIONS = ('北', '東', '南', '西')

# 配置のしかたが混んでいると判断する、最も近いアイコン中心までの距離（px）
CROWDED_DISTANCE = 50

# ほかのアイコン中心からこれだけ離れていれば十分とみなし、マスの中央に近い点を選ぶ（px）
COMFORT_DISTANCE = 80

# マスの境目からアイコンまでの余白（px）。アイコンの下の名前は最大 90px 幅で、左右に 20px はみ出す
CELL_MARGIN = 20

# 候補の点を並べる刻み（px）
_STEP = 4

Cell = tuple[int, int]  # (row, col)、0〜2

_VISUAL = [['左上', '上', '右上'], ['左', '中央', '右'], ['左下', '下', '右下']]


class Spot(NamedTuple):
    x: int  # 保存する左上座標
    y: int
    nearest: float | None  # 最も近いアイコン中心までの距離（アイコンが無ければ None）


class AreaError(ValueError):
    """エリアの指定が受け付けられない。メッセージがそのまま API の reason になる。"""


def _clamp(n: int) -> int:
    return max(0, min(2, n))


def cell_of(x: float, y: float) -> Cell:
    """左上座標 (x, y) のアイコンの中心があるマス。範囲外は端のマスに丸める。"""
    half = ICON_SIZE / 2
    col = _clamp(math.floor((x + half) * 3 / CANVAS_SIZE))
    row = _clamp(math.floor((y + half) * 3 / CANVAS_SIZE))
    return row, col


def _sides(top: str) -> dict:
    i = TOP_DIRECTIONS.index(top)
    return {
        'top': top,
        'right': TOP_DIRECTIONS[(i + 1) % 4],
        'bottom': TOP_DIRECTIONS[(i + 2) % 4],
        'left': TOP_DIRECTIONS[(i + 3) % 4],
    }


def edge_labels(top: str | None) -> dict | None:
    """見取り図の上下左右の辺の方角。上の方角が未設定なら None。"""
    return _sides(top) if top in TOP_DIRECTIONS else None


def area_name(cell: Cell, top: str | None) -> str:
    row, col = cell
    if top not in TOP_DIRECTIONS:
        return _VISUAL[row][col]
    if cell == (1, 1):
        return '中央'
    sides = _sides(top)
    parts = []
    if row != 1:
        parts.append(sides['top'] if row == 0 else sides['bottom'])
    if col != 1:
        parts.append(sides['left'] if col == 0 else sides['right'])
    parts.sort(key=lambda d: d not in ('北', '南'))  # 南北の字を先に並べる
    return ''.join(parts)


def area_grid(top: str | None) -> list[list[str]]:
    return [[area_name((r, c), top) for c in range(3)] for r in range(3)]


def _all_direction_names() -> set[str]:
    names = set()
    for t in TOP_DIRECTIONS:
        for row in area_grid(t):
            names.update(row)
    names.discard('中央')
    return names


def parse_area(name: str, top: str | None) -> Cell:
    """エリア名をマスにする。受け付けられなければ AreaError。"""
    text = (name or '').strip()
    if text.endswith('エリア'):
        text = text[:-len('エリア')].strip()
    for r, row in enumerate(_VISUAL):
        if text in row:
            return r, row.index(text)
    if top in TOP_DIRECTIONS:
        for r, row in enumerate(area_grid(top)):
            if text in row:
                return r, row.index(text)
    elif text in _all_direction_names():
        raise AreaError('この場所は見取り図の上の方角が未設定なので、上・左下などで指定してください')
    choices = [n for row in _VISUAL for n in row]
    if top in TOP_DIRECTIONS:
        choices = [n for row in area_grid(top) for n in row] + [n for n in choices if n != '中央']
    raise AreaError(f'エリア「{text}」は指定できません。使える名前: ' + '、'.join(choices))


def placements_of(canvas: dict | str | None) -> list[dict]:
    """canvas_data（version 2.0）の配置のうち、x・y が数値のものだけ。壊れていれば []。"""
    if isinstance(canvas, str):
        try:
            canvas = json.loads(canvas)
        except ValueError:
            return []
    if not isinstance(canvas, dict) or canvas.get('version') != '2.0':
        return []
    items = canvas.get('placements')
    if not isinstance(items, list):
        return []

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

    return [p for p in items if isinstance(p, dict) and is_num(p.get('x')) and is_num(p.get('y'))]


def planting_cells(placements: list[dict], planting_id: int) -> list[Cell]:
    """植え付けのアイコンがあるマス。重複なし、行→列の順。"""
    cells = {cell_of(p['x'], p['y']) for p in placements if p.get('locationCropId') == planting_id}
    return sorted(cells)


def area_names(placements: list[dict], planting_id: int, top: str | None) -> list[str]:
    return [area_name(c, top) for c in planting_cells(placements, planting_id)]


def choose_spot(placements: list[dict], cell: Cell) -> Spot:
    """マスの中でほかのアイコンから離れた置き場所を選ぶ。

    COMFORT_DISTANCE 以上離れた点があれば、その中でマスの中央に最も近い点。無ければ最も離れた点。
    境目から CELL_MARGIN 内側に置き、隣のマスにあるように見えないようにする。"""
    row, col = cell
    half = ICON_SIZE / 2
    size = CANVAS_SIZE / 3
    mid_x = col * size + size / 2
    mid_y = row * size + size / 2
    centers = [(p['x'] + half, p['y'] + half) for p in placements]
    if not centers:
        return Spot(round(mid_x - half), round(mid_y - half), None)

    def candidates(start, end):
        v = start
        while v <= end + 1e-9:
            yield v
            v += _STEP

    best = None
    inset = half + CELL_MARGIN
    for cy in candidates(row * size + inset, (row + 1) * size - inset):
        for cx in candidates(col * size + inset, (col + 1) * size - inset):
            nearest = min(math.hypot(cx - ox, cy - oy) for ox, oy in centers)
            to_mid = math.hypot(cx - mid_x, cy - mid_y)
            key = (-min(nearest, COMFORT_DISTANCE), to_mid)
            if best is None or key < best[0]:
                best = (key, cx, cy, nearest)
    _, cx, cy, nearest = best
    return Spot(round(cx - half), round(cy - half), nearest)


def crowded_warning(area: str) -> str:
    return f'{area}エリアは混んでいて、ほかのアイコンと重なっています。画面で確かめてください'
