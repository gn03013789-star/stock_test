"""股價走勢資料。

主來源：yfinance（台股 .TW / 上櫃 .TWO，美股直接代號）。
Fallback：TWSE STOCK_DAY 月資料（僅台股，抓近一年逐月）。
任何來源失敗都記錄在 status，不丟例外。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from ..core.models import PriceData, PricePoint, StockProfile

log = logging.getLogger(__name__)


def get_price(profile: StockProfile) -> PriceData:
    data = PriceData()

    # 1) yfinance
    points = _from_yfinance(profile)
    if points:
        data.points = points
        data.status.mark_ok("yfinance")
        return data
    data.status.add_error("yfinance 無資料或失敗")

    # 2) 台股 fallback：TWSE
    if profile.is_tw:
        points = _from_twse(profile.stock_id)
        if points:
            data.points = points
            data.status.mark_ok("TWSE STOCK_DAY")
            return data
        data.status.add_error("TWSE STOCK_DAY 無資料或失敗")

    log.warning("股價資料全數失敗：%s", profile.stock_id)
    return data


def _yf_symbol(profile: StockProfile) -> str:
    if not profile.is_tw:
        return profile.stock_id
    suffix = ".TWO" if profile.market_type == "上櫃" else ".TW"
    return f"{profile.stock_id}{suffix}"


def _from_yfinance(profile: StockProfile) -> List[PricePoint]:
    try:
        import yfinance as yf

        symbol = _yf_symbol(profile)
        hist = yf.Ticker(symbol).history(period="1y", auto_adjust=False)
        if hist is None or hist.empty:
            # 上市/上櫃判斷可能有誤，台股再試另一個後綴
            if profile.is_tw:
                alt = f"{profile.stock_id}{'.TW' if symbol.endswith('.TWO') else '.TWO'}"
                hist = yf.Ticker(alt).history(period="1y", auto_adjust=False)
            if hist is None or hist.empty:
                return []
        points: List[PricePoint] = []
        for idx, row in hist.iterrows():
            d = idx.date() if hasattr(idx, "date") else idx
            close = row.get("Close")
            vol = row.get("Volume")
            hi = row.get("High")
            lo = row.get("Low")
            if close is None or close != close:  # NaN 檢查
                continue
            points.append(
                PricePoint(
                    date=d,
                    close=float(close),
                    volume=float(vol) if vol == vol else None,
                    high=float(hi) if hi is not None and hi == hi else None,
                    low=float(lo) if lo is not None and lo == lo else None,
                )
            )
        return points
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance 股價失敗 %s：%s", profile.stock_id, e)
        return []


def _from_twse(stock_id: str) -> List[PricePoint]:
    """TWSE STOCK_DAY：逐月抓近 12 個月日收盤。"""
    from ..utils.http import fetch

    points: List[PricePoint] = []
    today = date.today()
    for back in range(12):
        ym = today.replace(day=1) - timedelta(days=back * 28)
        ymd = ym.strftime("%Y%m01")
        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        data = fetch(url, params={"response": "json", "date": ymd, "stockNo": stock_id},
                     expect="json")
        if not isinstance(data, dict) or data.get("stat") != "OK":
            continue
        for row in data.get("data", []):
            try:
                # row: [日期, 成交股數, 成交金額, 開盤, 最高, 最低, 收盤, 漲跌, 成交筆數]
                roc = row[0].split("/")
                y = int(roc[0]) + 1911
                d = date(y, int(roc[1]), int(roc[2]))
                close = float(row[6].replace(",", ""))
                vol = float(row[1].replace(",", "")) if row[1] else None

                def _f(v):
                    try:
                        return float(v.replace(",", ""))
                    except (ValueError, AttributeError):
                        return None

                points.append(PricePoint(date=d, close=close, volume=vol,
                                         high=_f(row[4]), low=_f(row[5])))
            except (ValueError, IndexError):
                continue
    points.sort(key=lambda p: p.date)
    return points


def high_low(points: List[PricePoint]) -> Optional[dict]:
    """回傳區間高低點供圖表標註。"""
    if not points:
        return None
    hi = max(points, key=lambda p: p.close)
    lo = min(points, key=lambda p: p.close)
    return {
        "high": hi.close,
        "high_date": hi.date,
        "low": lo.close,
        "low_date": lo.date,
        "last": points[-1].close,
    }
