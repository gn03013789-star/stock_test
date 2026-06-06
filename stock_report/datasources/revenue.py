"""月營收資料（台股近 24 個月）。

台股主來源：TWSE OpenAPI 月營收（t187ap05_L 系列為當期，歷史以彙總端點補）。
實作策略：TWSE OpenAPI 月營收彙總端點取當月 + 以 FinMind 風格公開端點不可得時，
退而以 yfinance 季營收近似（美股一律走季營收）。
任何來源失敗都記錄在 status，不丟例外。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ..core.models import RevenueData, RevenuePoint, StockProfile

log = logging.getLogger(__name__)


def get_revenue(profile: StockProfile) -> RevenueData:
    data = RevenueData()

    if profile.is_tw:
        # 主來源：FinMind 月營收（含完整歷史）
        from datetime import date, timedelta

        from . import finmind

        start = (date.today() - timedelta(days=800)).isoformat()
        points = finmind.month_revenue(profile.stock_id, start)
        if points:
            _compute_growth(points)
            data.points = points[-24:]
            data.unit = "億元"
            data.status.mark_ok("FinMind 月營收")
            return data
        data.status.add_error("FinMind 月營收無資料或失敗")

        # Fallback：TWSE OpenAPI（僅當期）
        points = _from_twse_opendata(profile.stock_id)
        if points:
            _compute_growth(points)
            data.points = points[-24:]
            data.unit = "千元"
            data.status.mark_ok("TWSE OpenAPI 月營收（僅當期）")
            return data
        data.status.add_error("TWSE 月營收無資料或失敗")

    # 美股或台股 fallback：季營收（yfinance）
    points = _from_yfinance_quarterly(profile)
    if points:
        _compute_growth(points)
        data.points = points[-8:]
        data.unit = f"百萬{profile.currency}"
        data.is_quarterly = True
        data.status.mark_ok("yfinance 季營收")
        if profile.is_tw:
            data.status.add_error("已退化為季營收（月營收來源不可得）")
        return data
    data.status.add_error("季營收來源亦失敗")

    log.warning("營收資料全數失敗：%s", profile.stock_id)
    return data


def _from_twse_opendata(stock_id: str) -> List[RevenuePoint]:
    """TWSE 月營收 OpenAPI。

    端點 t187ap05_L 提供「上市公司每月營業收入彙總表」當期資料；
    逐月查詢需走歷史 API。這裡走公開的逐月彙總端點，盡量取多月。
    若僅取得當期，仍回傳可用資料（不足 24 月由上層處理）。
    """
    from ..utils.http import fetch

    points: List[RevenuePoint] = []
    # 公開資訊觀測站月營收 OpenAPI（彙總，含多家公司當期）
    data = fetch(
        "https://openapi.twse.com.tw/v1/opendata/t187ap05_L", expect="json"
    )
    if isinstance(data, list):
        for row in data:
            code = str(row.get("公司代號", "")).strip()
            if code != stock_id:
                continue
            try:
                ym = str(row.get("資料年月", "")).strip()  # 例如 11305
                if len(ym) >= 5:
                    year = int(ym[:-2]) + 1911
                    month = int(ym[-2:])
                else:
                    continue
                rev = float(str(row.get("當月營收", "0")).replace(",", ""))
                points.append(RevenuePoint(year=year, month=month, revenue=rev))
            except (ValueError, TypeError):
                continue
    points.sort(key=lambda p: (p.year, p.month))
    return points


def _from_yfinance_quarterly(profile: StockProfile) -> List[RevenuePoint]:
    try:
        import yfinance as yf

        symbol = profile.stock_id
        if profile.is_tw:
            symbol = f"{profile.stock_id}{'.TWO' if profile.market_type == '上櫃' else '.TW'}"
        fin = yf.Ticker(symbol).quarterly_financials
        if fin is None or fin.empty or "Total Revenue" not in fin.index:
            return []
        rev_row = fin.loc["Total Revenue"].dropna()
        points: List[RevenuePoint] = []
        for ts, val in rev_row.items():
            d = ts.date() if hasattr(ts, "date") else ts
            points.append(
                RevenuePoint(year=d.year, month=d.month, revenue=float(val) / 1e6)
            )
        points.sort(key=lambda p: (p.year, p.month))
        return points
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance 季營收失敗 %s：%s", profile.stock_id, e)
        return []


def _compute_growth(points: List[RevenuePoint]) -> None:
    """就地計算 MoM / YoY。"""
    by_key = {(p.year, p.month): p for p in points}
    for i, p in enumerate(points):
        if i > 0 and points[i - 1].revenue:
            p.mom = (p.revenue - points[i - 1].revenue) / points[i - 1].revenue * 100
        prev_year = by_key.get((p.year - 1, p.month))
        if prev_year and prev_year.revenue:
            p.yoy = (p.revenue - prev_year.revenue) / prev_year.revenue * 100
