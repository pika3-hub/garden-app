"""キーワード検索で表記の違いを吸収する（ひらがな／カタカナ、半角／全角）

検索される列と検索語の両方を fold() でそろえてから LIKE で比べる。列の側は SQLite の
関数 search_fold（app/database.py の get_db で登録）で、検索語の側は Python で fold() する。
例: WHERE search_fold(name) LIKE ? と f'%{fold(keyword)}%'
漢字とかな（蕪 と かぶ）はそろえない。
"""
import unicodedata

SQL_FUNCTION = 'search_fold'

# カタカナ（ァ〜ヶ、ヽヾ）をひらがなに。ヷ〜ヺ・ー はひらがなに対応する文字が無いのでそのまま
_KATA_TO_HIRA = {c: c - 0x60 for c in range(ord('ァ'), ord('ヶ') + 1)}
_KATA_TO_HIRA.update({ord('ヽ'): ord('ゝ'), ord('ヾ'): ord('ゞ')})


def fold(text):
    """NFKC（半角カナ→全角、全角英数→半角）のあと、カタカナをひらがなにする。None はそのまま"""
    if text is None:
        return None
    return unicodedata.normalize('NFKC', str(text)).translate(_KATA_TO_HIRA)
