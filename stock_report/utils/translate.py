"""英文 -> 繁體中文翻譯（免金鑰，透過 deep-translator）。

設計原則：翻譯失敗一律回傳原文，絕不丟例外；結果快取避免重複請求。
"""

from __future__ import annotations

import logging
import re

from .cache import get_or_set

log = logging.getLogger(__name__)

_ASCII_RE = re.compile(r"[A-Za-z]")
_CJK_RE = re.compile(r"[一-鿿]")

# 單次翻譯長度上限（GoogleTranslator 限制約 5000 字）
_MAX_LEN = 4500


def looks_english(text: str) -> bool:
    """粗略判斷字串是否以英文為主（含英文字母且幾乎無中日韓字）。"""
    if not text:
        return False
    if _CJK_RE.search(text):
        return False
    return bool(_ASCII_RE.search(text))


def to_zh(text: str) -> str:
    """將英文翻為繁中；非英文或失敗時回傳原文。"""
    if not text or not looks_english(text):
        return text
    snippet = text[:_MAX_LEN]

    def _producer():
        try:
            from deep_translator import GoogleTranslator

            return GoogleTranslator(source="auto", target="zh-TW").translate(snippet)
        except Exception as e:  # noqa: BLE001  翻譯失敗不可影響主流程
            log.warning("翻譯失敗：%s", e)
            return None  # None 不寫快取，回傳原文

    result = get_or_set(f"tr_zh:{snippet}", _producer, ttl=30 * 86400)
    return result or text
