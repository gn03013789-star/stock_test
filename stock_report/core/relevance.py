"""判斷一段文字是否確實在講「這一檔股票」。

用於過濾新聞 / 目標價搜尋結果，避免短名稱（如「華新」對到「華新科」）或
搜尋引擎回傳的他檔個股（如搜「華新 目標價」卻回傳臻鼎、信邦的目標價）混入。
"""

from __future__ import annotations

import re

from .models import StockProfile


def _is_cjk(ch: str) -> bool:
    return bool(ch) and "一" <= ch <= "鿿"


_CODE_AFTER_RE = re.compile(r"[（(](\d{4})[）)]")


def _cjk_standalone(text: str, name: str, stock_id: str = "") -> bool:
    """name 以「獨立詞」出現（前後不接其他中日韓字），避免 華新 命中 華新科。

    另外：若 name 後面緊接 (####) 且代號與本檔不同（如 華新(4435)），視為他檔，跳過。
    """
    start = 0
    while True:
        i = text.find(name, start)
        if i < 0:
            return False
        before = text[i - 1] if i > 0 else ""
        after = text[i + len(name)] if i + len(name) < len(text) else ""
        if not _is_cjk(before) and not _is_cjk(after):
            m = _CODE_AFTER_RE.match(text[i + len(name):])
            if m and stock_id and m.group(1) != stock_id:
                start = i + 1
                continue  # 名稱後接他檔代號，略過此處
            return True
        start = i + 1


def _token_match(text: str, term: str, stock_id: str = "") -> bool:
    if not term:
        return False
    if term.isdigit():
        # 台股代號：前後不可緊接其他數字（避免 1605 命中 41605）
        return re.search(rf"(?<!\d){re.escape(term)}(?!\d)", text) is not None
    if re.fullmatch(r"[A-Za-z0-9.\-]+", term):
        # 英文代號/單字：以英文邊界比對
        return re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])",
                         text, re.IGNORECASE) is not None
    # 中文名稱：需獨立詞，且後方不可緊接他檔代號
    return _cjk_standalone(text, term, stock_id)


def relevance_terms(profile: StockProfile) -> list:
    terms = set()
    if profile.stock_id:
        terms.add(profile.stock_id)
    for nm in (profile.company_name, profile.english_name, *profile.aliases):
        if nm:
            terms.add(nm)
    # 英文名第一個字（>=3 字元）作為輔助比對（如 "Apple Inc." -> "Apple"）
    if profile.english_name:
        first = profile.english_name.split()[0]
        if len(first) >= 3:
            terms.add(first)
    return [t for t in terms if t]


def is_relevant(text: str, profile: StockProfile) -> bool:
    """文字是否確實提及此檔（代號或獨立公司名）。"""
    if not text:
        return False
    return any(
        _token_match(text, term, profile.stock_id)
        for term in relevance_terms(profile)
    )
