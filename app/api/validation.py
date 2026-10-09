"""API 入力の検証。項目定義（Field）に沿って型変換し、誤りを details 形式で集める"""
import math
import re
from dataclasses import dataclass
from datetime import date

from app.api.errors import detail
from app.database import get_db

SQLITE_MAX_INT = 2**63 - 1
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
_INT_RE = re.compile(r'^-?\d+$')
_LONG_CHOICES = 10  # 選択肢がこれより多ければメッセージに列挙せず /meta へ案内する


@dataclass(frozen=True)
class Ref:
    """参照先（存在チェック用）"""
    table: str
    label: str
    hint: str  # 見つからないときの案内


REF_CROP = Ref('crops', '作物', 'GET /api/v1/lookup?q=名前 で検索してください')
REF_VARIETY = Ref('varieties', '品種', 'GET /api/v1/lookup?q=名前 で検索してください')
REF_LOCATION = Ref('locations', '場所', 'GET /api/v1/lookup?q=名前 で検索してください')
REF_PLANTING = Ref('plantings', '植え付け', 'GET /api/v1/plantings?q=作物名 で検索してください')
REF_HARVEST = Ref('harvests', '収穫', 'GET /api/v1/harvests?planting_id=... で検索してください')
REF_PHOTO = Ref('photo_pool', '写真プールの写真', 'GET /api/v1/photos で一覧を確認してください')


@dataclass(frozen=True)
class Field:
    """書き込める項目の定義"""
    kind: str                  # 'str' | 'int' | 'decimal' | 'date' | 'enum' | 'color' | 'ref'
    required: bool = False
    max_len: int | None = None
    min_value: float | None = None
    choices: object = None     # enum の選択肢（list か、list を返す関数）
    ref: Ref | None = None     # ref の参照先
    column: str | None = None  # DB カラム名が API の項目名と違うとき


def _to_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and _INT_RE.match(value.strip()):
        return int(value.strip())
    return None


def _to_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _ref_exists(ref, obj_id):
    if obj_id < 1 or obj_id > SQLITE_MAX_INT:
        return False
    return get_db().execute(f'SELECT 1 FROM {ref.table} WHERE id = ?', (obj_id,)).fetchone() is not None


def check_ref_id(ref, value):
    """参照 ID を検証して (id, None) か (None, 理由) を返す"""
    obj_id = _to_int(value)
    if obj_id is None:
        return None, '整数の ID で指定してください'
    if not _ref_exists(ref, obj_id):
        return None, f'ID {obj_id} の{ref.label}は存在しません。{ref.hint}'
    return obj_id, None


def check_value(field, value):
    """(変換後の値, 誤りの理由 or None) を返す。空文字・null は None（必須なら誤り）"""
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None, ('必須項目です' if field.required else None)

    kind = field.kind
    if kind == 'str':
        if not isinstance(value, str):
            return None, '文字列で指定してください'
        if field.max_len and len(value) > field.max_len:
            return None, f'{field.max_len}文字以内で指定してください（現在 {len(value)} 文字）'
        return value, None

    if kind in ('int', 'decimal'):
        number = _to_int(value) if kind == 'int' else _to_number(value)
        if number is None:
            return None, '整数で指定してください' if kind == 'int' else '数値で指定してください（単位は付けない）'
        if abs(number) > SQLITE_MAX_INT:
            return None, '値が大きすぎます'
        if field.min_value is not None and number < field.min_value:
            return None, f'{field.min_value:g} 以上で指定してください'
        return number, None

    if kind == 'date':
        if isinstance(value, str) and _DATE_RE.match(value):
            try:
                date.fromisoformat(value)
                return value, None
            except ValueError:
                pass
        return None, 'YYYY-MM-DD 形式の実在する日付で指定してください（例: 2026-10-09）'

    if kind == 'enum':
        choices = field.choices() if callable(field.choices) else field.choices
        if value in choices:
            return value, None
        if len(choices) > _LONG_CHOICES:
            return None, '使える値ではありません。GET /api/v1/meta で一覧を確認してください'
        return None, f'次のいずれかで指定してください: {", ".join(choices)}'

    if kind == 'color':
        if isinstance(value, str) and _COLOR_RE.match(value):
            return value, None
        return None, '#RRGGBB 形式で指定してください（例: #4CAF50）'

    if kind == 'ref':
        return check_ref_id(field.ref, value)

    raise ValueError(f'unknown field kind: {kind}')


def _scalar(value):
    return value if isinstance(value, (str, int, float, bool)) else None


def validate_payload(fields, payload, *, creating, reserved=(), read_only=()):
    """payload を検証して (cleaned, errors) を返す

    - creating=True なら必須項目の欠落も誤りにする（PATCH では送られた項目だけ検証）
    - reserved は画像・関連など、呼び出し側が別に検証するキー
    - 誤りは最初の1件で止めず、すべて errors に積む
    """
    cleaned, errors = {}, []
    usable = [*fields, *reserved]
    for key, value in payload.items():
        if key in reserved:
            continue
        if key in read_only:
            errors.append(detail(key, '読み取り専用の項目のため変更できません'))
            continue
        field = fields.get(key)
        if field is None:
            errors.append(detail(key, f'未知の項目です。使える項目: {", ".join(usable)}'))
            continue
        converted, reason = check_value(field, value)
        if reason:
            errors.append(detail(key, reason, _scalar(value)))
        else:
            cleaned[key] = converted
    if creating:
        for key, field in fields.items():
            if field.required and key not in payload:
                errors.append(detail(key, '必須項目です'))
    return cleaned, errors
