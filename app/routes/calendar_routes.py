from flask import Blueprint, render_template, request
from datetime import date

from app.models.calendar import Calendar

bp = Blueprint('calendar', __name__, url_prefix='/calendar')


@bp.route('/')
def index():
    """カレンダービュー"""
    # クエリパラメータから年月を取得（デフォルトは今月）
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    # 年月の範囲チェック
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # 前月・次月の計算
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # カレンダーデータを取得
    calendar_weeks = Calendar.get_calendar_weeks(year, month)
    month_data = Calendar.get_month_data(year, month)

    return render_template('calendar/index.html',
                           year=year,
                           month=month,
                           today=today,
                           prev_year=prev_year,
                           prev_month=prev_month,
                           next_year=next_year,
                           next_month=next_month,
                           calendar_weeks=calendar_weeks,
                           month_data=month_data)
