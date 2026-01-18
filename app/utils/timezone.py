from datetime import datetime, timezone, timedelta

# 日本標準時 (JST: UTC+9)
JST = timezone(timedelta(hours=9))


def get_jst_now():
    """現在の日本標準時を取得

    Returns:
        str: 'YYYY-MM-DD HH:MM:SS' 形式の文字列
    """
    return datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
