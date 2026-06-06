"""中文字型管理：首次執行自動下載 Noto Sans TC，並提供 fallback。

優先序：
  1. 已下載快取的 Noto Sans TC。
  2. 線上下載 Noto Sans TC 至快取。
  3. Windows 內建微軟正黑體 msjh.ttc。
回傳可用字型檔路徑；全部失敗回傳 None（呼叫端改用內建字型，中文可能變方塊）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..config import (
    FONT_CACHE_DIR,
    NOTO_SANS_TC_FILENAME,
    NOTO_SANS_TC_URL,
    WINDOWS_FONT_FALLBACK,
)

log = logging.getLogger(__name__)

FONT_NAME = "ReportCJK"
_resolved: Optional[Path] = None


def ensure_font() -> Optional[Path]:
    """確保有可用的中文字型，回傳檔案路徑（TrueType 優先，相容 reportlab）。"""
    global _resolved
    if _resolved and _resolved.exists():
        return _resolved

    # 1) 已快取的 Noto TTF
    cached = FONT_CACHE_DIR / NOTO_SANS_TC_FILENAME
    if cached.exists() and cached.stat().st_size > 100_000:
        _resolved = cached
        return cached

    # 2) Windows 內建 TrueType 字型（穩定、免下載，reportlab 可直接使用）
    if WINDOWS_FONT_FALLBACK.exists():
        log.info("使用 Windows 內建字型：%s", WINDOWS_FONT_FALLBACK)
        _resolved = WINDOWS_FONT_FALLBACK
        return WINDOWS_FONT_FALLBACK

    # 3) 下載 Noto Sans TC（非 Windows 環境）
    downloaded = _download(cached)
    if downloaded:
        _resolved = downloaded
        return downloaded

    log.warning("找不到任何中文字型，中文可能無法正確顯示。")
    return None


def _download(dest: Path) -> Optional[Path]:
    from ..utils.http import fetch

    log.info("下載中文字型 Noto Sans TC ...（首次執行）")
    content = fetch(NOTO_SANS_TC_URL, timeout=60, expect="bytes")
    if content and len(content) > 100_000:
        try:
            dest.write_bytes(content)
            log.info("字型已下載：%s（%.1f MB）", dest, len(content) / 1e6)
            return dest
        except OSError as e:
            log.warning("字型寫入失敗：%s", e)
    return None


def register_for_reportlab() -> str:
    """向 reportlab 註冊中文字型，回傳字型名稱（失敗回 Helvetica）。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    path = ensure_font()
    candidates = [path] if path else []
    # 若主字型註冊失敗，再試 Windows 內建 TrueType 字型
    if WINDOWS_FONT_FALLBACK.exists() and WINDOWS_FONT_FALLBACK not in candidates:
        candidates.append(WINDOWS_FONT_FALLBACK)

    for cand in candidates:
        try:
            if cand.suffix.lower() in (".ttc", ".otc"):
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(cand), subfontIndex=0))
            else:
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(cand)))
            return FONT_NAME
        except Exception as e:  # noqa: BLE001
            log.warning("reportlab 字型註冊失敗（%s）：%s", cand.name, e)

    log.warning("無可用中文字型，改用 Helvetica（中文將無法顯示）。")
    return "Helvetica"


def register_for_matplotlib() -> Optional[str]:
    """設定 matplotlib 中文字型，回傳 font family 名稱。"""
    import matplotlib
    from matplotlib import font_manager

    path = ensure_font()
    if not path:
        return None
    try:
        font_manager.fontManager.addfont(str(path))
        prop = font_manager.FontProperties(fname=str(path))
        family = prop.get_name()
        matplotlib.rcParams["font.family"] = family
        matplotlib.rcParams["axes.unicode_minus"] = False
        return family
    except Exception as e:  # noqa: BLE001
        log.warning("matplotlib 字型設定失敗：%s", e)
        return None
