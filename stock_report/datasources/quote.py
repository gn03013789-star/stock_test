"""即時報價與市場開盤判斷（盤中每 10 秒更新用）。

資料來源：yfinance（Yahoo），台股報價可能延遲約 15 分鐘，僅供參考。
任何失敗都不丟例外，回傳 None / False。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from ..core.models import StockProfile

log = logging.getLogger(__name__)


@dataclass
class Quote:
    price: float
    prev_close: float
    change: float
    change_pct: float
    volume: float
    day_open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    asof: str = ""
    currency: str = ""
    delayed: bool = True


# 市場交易時段（當地時間）
_MARKET_HOURS = {
    "TW": ("Asia/Taipei", time(9, 0), time(13, 30)),
    "US": ("America/New_York", time(9, 30), time(16, 0)),
}


def is_market_open(profile: StockProfile) -> bool:
    """粗略判斷是否為交易時段（僅看週一至週五與時間，不含假日）。"""
    cfg = _MARKET_HOURS.get(profile.market)
    if not cfg:
        return False
    tzname, open_t, close_t = cfg
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(tzname))
    except Exception as e:  # noqa: BLE001
        log.debug("時區判斷失敗：%s", e)
        return False
    if now.weekday() >= 5:  # 週六日
        return False
    return open_t <= now.time() <= close_t


def _yf_symbol(profile: StockProfile) -> str:
    if profile.market != "TW":
        return profile.stock_id
    return f"{profile.stock_id}{'.TWO' if profile.market_type == '上櫃' else '.TW'}"


def get_quote(profile: StockProfile) -> Optional[Quote]:
    """取得最新報價（含成交量）。失敗回 None。"""
    try:
        import yfinance as yf

        fi = yf.Ticker(_yf_symbol(profile)).fast_info
        price = float(fi["last_price"])
        prev = float(fi["previous_close"])
        change = price - prev
        pct = (change / prev * 100) if prev else 0.0

        def _get(key):
            try:
                v = fi[key]
                return float(v) if v is not None else None
            except Exception:  # noqa: BLE001
                return None

        return Quote(
            price=price,
            prev_close=prev,
            change=change,
            change_pct=pct,
            volume=_get("last_volume") or 0.0,
            day_open=_get("open"),
            day_high=_get("day_high"),
            day_low=_get("day_low"),
            asof=datetime.now().strftime("%H:%M:%S"),
            currency=profile.currency,
            delayed=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("取得即時報價失敗 %s：%s", profile.stock_id, e)
        return None
