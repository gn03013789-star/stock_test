"""FinMind 公開資料 API 封裝（台股月營收 / 財報 EPS）。

FinMind 為公開、免登入即可使用的台股開放資料 API（彙整自 TWSE/MOPS 等公開來源），
免費額度足供本工具使用。失敗一律回傳空清單，不丟例外。
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from ..core.models import EpsPoint, RevenuePoint
from ..utils.cache import get_or_set
from ..utils.http import fetch

log = logging.getLogger(__name__)

API = "https://api.finmindtrade.com/api/v4/data"


def month_revenue(stock_id: str, start_date: str) -> List[RevenuePoint]:
    """近 N 月營收（單位轉為「億元」方便閱讀）。"""

    def _producer():
        return fetch(API, params={
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": stock_id,
            "start_date": start_date,
        }, expect="json")

    data = get_or_set(f"finmind_rev:{stock_id}:{start_date}", _producer, ttl=86400)
    if not isinstance(data, dict) or data.get("status") != 200:
        return []
    points: List[RevenuePoint] = []
    for row in data.get("data", []):
        try:
            year = int(row["revenue_year"])
            month = int(row["revenue_month"])
            rev = float(row["revenue"]) / 1e8  # 元 -> 億元
            points.append(RevenuePoint(year=year, month=month, revenue=rev))
        except (KeyError, ValueError, TypeError):
            continue
    points.sort(key=lambda p: (p.year, p.month))
    return points


def quarterly_eps(stock_id: str, start_date: str) -> List[EpsPoint]:
    """近幾季 EPS（取財報中 type==EPS 之基本每股盈餘）。"""

    def _producer():
        return fetch(API, params={
            "dataset": "TaiwanStockFinancialStatements",
            "data_id": stock_id,
            "start_date": start_date,
        }, expect="json")

    data = get_or_set(f"finmind_eps:{stock_id}:{start_date}", _producer, ttl=86400)
    if not isinstance(data, dict) or data.get("status") != 200:
        return []
    points: List[EpsPoint] = []
    for row in data.get("data", []):
        if row.get("type") != "EPS":
            continue
        try:
            d = row["date"]  # YYYY-MM-DD（季底）
            y, m, _ = d.split("-")
            q = (int(m) - 1) // 3 + 1
            points.append(EpsPoint(period=f"{y}Q{q}", eps=float(row["value"])))
        except (KeyError, ValueError, TypeError):
            continue
    points.sort(key=lambda p: p.period)
    return points
