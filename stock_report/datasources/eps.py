"""EPS 資料（近 8 季 + 年度）。

台股主來源：TWSE OpenAPI 綜合損益表（含每股盈餘）。
Fallback / 美股：yfinance quarterly earnings。
任何來源失敗都記錄在 status，不丟例外。
"""

from __future__ import annotations

import logging
from typing import List

from ..core.models import EpsData, EpsPoint, StockProfile

log = logging.getLogger(__name__)


def get_eps(profile: StockProfile) -> EpsData:
    data = EpsData()

    if profile.is_tw:
        # 主來源：FinMind 財報 EPS（含歷史季別）
        from datetime import date, timedelta

        from . import finmind

        start = (date.today() - timedelta(days=900)).isoformat()
        q = finmind.quarterly_eps(profile.stock_id, start)
        if q:
            data.quarterly = q[-8:]
            data.annual = _annual_from_quarterly(q)
            data.status.mark_ok("FinMind 財報 EPS")
            return data
        data.status.add_error("FinMind EPS 無資料或失敗")

        # Fallback：TWSE 綜合損益表（僅當期）
        q, a = _from_twse(profile.stock_id)
        if q or a:
            data.quarterly = q[-8:]
            data.annual = a[-3:]
            data.status.mark_ok("TWSE OpenAPI 綜合損益表（僅當期）")
            return data
        data.status.add_error("TWSE EPS 無資料或失敗")

    q = _from_yfinance(profile)
    if q:
        data.quarterly = q[-8:]
        data.status.mark_ok("yfinance 季 EPS")
        return data
    data.status.add_error("yfinance EPS 失敗")

    log.warning("EPS 資料全數失敗：%s", profile.stock_id)
    return data


def _annual_from_quarterly(q: List[EpsPoint]) -> List[EpsPoint]:
    """以季 EPS 加總出完整年度 EPS（僅取有 4 季的年度）。"""
    by_year: dict = {}
    for p in q:
        try:
            year = p.period.split("Q")[0]
        except (AttributeError, IndexError):
            continue
        by_year.setdefault(year, []).append(p.eps)
    annual = [
        EpsPoint(period=y, eps=round(sum(v), 2))
        for y, v in sorted(by_year.items())
        if len(v) == 4
    ]
    return annual[-3:]


def _from_twse(stock_id: str):
    """TWSE 綜合損益表 OpenAPI（季）。"""
    from ..utils.http import fetch

    quarterly: List[EpsPoint] = []
    # 一般業別綜合損益表（含基本每股盈餘）
    endpoints = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci",   # 一般業
        "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_basi",  # 金控
        "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_bd",    # 銀行
    ]
    for url in endpoints:
        data = fetch(url, expect="json")
        if not isinstance(data, list):
            continue
        for row in data:
            code = str(row.get("公司代號", "")).strip()
            if code != stock_id:
                continue
            eps_raw = row.get("基本每股盈餘（元）") or row.get("基本每股盈餘")
            ym = str(row.get("資料年月", "") or row.get("年度", "")).strip()
            try:
                eps_val = float(str(eps_raw).replace(",", ""))
            except (ValueError, TypeError):
                continue
            period = _roc_period_label(ym)
            quarterly.append(EpsPoint(period=period, eps=eps_val))
    quarterly.sort(key=lambda p: p.period)
    return quarterly, []


def _roc_period_label(ym: str) -> str:
    """11301 -> 2024Q1（粗略對應，月份 03/06/09/12 視為季底）。"""
    try:
        if len(ym) >= 5:
            year = int(ym[:-2]) + 1911
            month = int(ym[-2:])
            q = (month - 1) // 3 + 1
            return f"{year}Q{q}"
    except ValueError:
        pass
    return ym or "?"


def _from_yfinance(profile: StockProfile) -> List[EpsPoint]:
    try:
        import yfinance as yf

        symbol = profile.stock_id
        if profile.is_tw:
            symbol = f"{profile.stock_id}{'.TWO' if profile.market_type == '上櫃' else '.TW'}"
        tk = yf.Ticker(symbol)
        points: List[EpsPoint] = []

        # 新版 yfinance：income_stmt 有 'Diluted EPS' / 'Basic EPS'
        try:
            qf = tk.quarterly_income_stmt
            if qf is not None and not qf.empty:
                for key in ("Diluted EPS", "Basic EPS"):
                    if key in qf.index:
                        row = qf.loc[key].dropna()
                        for ts, val in row.items():
                            d = ts.date() if hasattr(ts, "date") else ts
                            q = (d.month - 1) // 3 + 1
                            points.append(EpsPoint(period=f"{d.year}Q{q}", eps=float(val)))
                        break
        except Exception:  # noqa: BLE001
            pass

        if not points:
            # 舊版 fallback：earnings
            try:
                earnings = tk.quarterly_earnings
                if earnings is not None and not earnings.empty and "Earnings" in earnings:
                    shares = (tk.info or {}).get("sharesOutstanding")
                    if shares:
                        for idx, val in earnings["Earnings"].items():
                            points.append(EpsPoint(period=str(idx), eps=float(val) / shares))
            except Exception:  # noqa: BLE001
                pass

        points.sort(key=lambda p: p.period)
        return points
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance EPS 失敗 %s：%s", profile.stock_id, e)
        return []
