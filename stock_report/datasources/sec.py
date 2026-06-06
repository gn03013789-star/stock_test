"""SEC EDGAR 美股財報資料（官方、公開、免金鑰）。

提供：
- ticker -> CIK 對照
- 年度財務摘要（營收 / 淨利 / EPS / 毛利率）取自 XBRL companyfacts
- 近期申報清單（10-K / 10-Q / 8-K），並標記財報發布之 8-K（Item 2.02）

注意：SEC 要求帶可識別的 User-Agent；本模組以 config.SEC_USER_AGENT 帶入。
任何失敗都記錄在 status，不丟例外。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..config import SEC_USER_AGENT
from ..core.models import FilingItem, FinancialRow, SourceStatus, UsFinancials
from ..utils.cache import get_or_set
from ..utils.http import fetch

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# 概念優先序（XBRL us-gaap tag）
_REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
_NET_INCOME_TAGS = ["NetIncomeLoss"]
_EPS_TAGS = ["EarningsPerShareDiluted", "EarningsPerShareBasic"]
_GROSS_TAGS = ["GrossProfit"]


def get_us_financials(ticker: str, years: int = 5) -> UsFinancials:
    out = UsFinancials()
    cik = ticker_to_cik(ticker)
    if not cik:
        out.status.add_error("查無對應 SEC CIK")
        return out
    out.cik = cik

    facts = _company_facts(cik)
    if facts:
        out.rows = _build_rows(facts, years)
        if out.rows:
            out.status.mark_ok("SEC EDGAR XBRL")
        else:
            out.status.add_error("companyfacts 無可用年度數據")
    else:
        out.status.add_error("companyfacts 取得失敗")

    out.filings = _recent_filings(cik)
    if out.filings and not out.status.ok:
        out.status.mark_ok("SEC EDGAR 申報清單")
    return out


# --------------------------------------------------------------------------- #
# CIK 對照
# --------------------------------------------------------------------------- #
def ticker_to_cik(ticker: str) -> Optional[str]:
    ticker = ticker.upper().replace(".", "-")

    def _producer():
        return fetch("https://www.sec.gov/files/company_tickers.json",
                     headers=_HEADERS, expect="json")

    data = get_or_set("sec_tickers", _producer, ttl=7 * 86400)
    if not isinstance(data, dict):
        return None
    for row in data.values():
        if str(row.get("ticker", "")).upper() == ticker:
            return str(row["cik_str"]).zfill(10)
    return None


# --------------------------------------------------------------------------- #
# companyfacts -> 年度財務摘要
# --------------------------------------------------------------------------- #
def _company_facts(cik: str) -> Optional[dict]:
    def _producer():
        return fetch(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                     headers=_HEADERS, timeout=30, expect="json")

    return get_or_set(f"sec_facts:{cik}", _producer, ttl=86400)


def _annual_series(facts: dict, tags: List[str]) -> Dict[int, float]:
    """從 us-gaap 概念抽出「年度」序列：{會計年度: 數值}。

    僅取期間約一年（350~380 天）的資料點，依會計年度結束日歸年，最新申報優先。
    """
    us = (facts.get("facts") or {}).get("us-gaap") or {}
    chosen: Dict[int, Tuple[str, float]] = {}  # year -> (filed, val)
    for tag in tags:
        node = us.get(tag)
        if not node:
            continue
        for unit_vals in node.get("units", {}).values():
            for d in unit_vals:
                start, end = d.get("start"), d.get("end")
                val, filed = d.get("val"), d.get("filed", "")
                if start is None or end is None or val is None:
                    continue
                try:
                    sd = datetime.strptime(start, "%Y-%m-%d")
                    ed = datetime.strptime(end, "%Y-%m-%d")
                except ValueError:
                    continue
                days = (ed - sd).days
                if not (350 <= days <= 380):
                    continue  # 只要全年期間
                year = ed.year
                prev = chosen.get(year)
                if prev is None or filed > prev[0]:
                    chosen[year] = (filed, float(val))
        if chosen:
            break  # 該 tag 已有資料就不再試後續 tag
    return {y: v for y, (f, v) in chosen.items()}


def _instant_eps(facts: dict, tags: List[str]) -> Dict[int, float]:
    """EPS 為每股盈餘（期間值），同樣取全年期間。"""
    return _annual_series(facts, tags)


def _build_rows(facts: dict, years: int) -> List[FinancialRow]:
    rev = _annual_series(facts, _REVENUE_TAGS)
    ni = _annual_series(facts, _NET_INCOME_TAGS)
    eps = _instant_eps(facts, _EPS_TAGS)
    gross = _annual_series(facts, _GROSS_TAGS)

    all_years = sorted(set(rev) | set(ni) | set(eps), reverse=True)[:years]
    rows: List[FinancialRow] = []
    for y in sorted(all_years):
        r = rev.get(y)
        g = gross.get(y)
        gm = (g / r * 100) if (r and g) else None
        rows.append(FinancialRow(
            period=f"FY{y}",
            revenue=(r / 1e6) if r is not None else None,       # -> 百萬美元
            net_income=(ni.get(y) / 1e6) if ni.get(y) is not None else None,
            eps=eps.get(y),
            gross_margin=gm,
        ))
    return rows


# --------------------------------------------------------------------------- #
# 近期申報清單
# --------------------------------------------------------------------------- #
def _recent_filings(cik: str, limit: int = 12) -> List[FilingItem]:
    def _producer():
        return fetch(f"https://data.sec.gov/submissions/CIK{cik}.json",
                     headers=_HEADERS, timeout=30, expect="json")

    data = get_or_set(f"sec_sub:{cik}", _producer, ttl=43200)
    if not isinstance(data, dict):
        return []
    rec = (data.get("filings") or {}).get("recent") or {}
    forms = rec.get("form", [])
    dates = rec.get("filingDate", [])
    items = rec.get("items", [])
    accs = rec.get("accessionNumber", [])
    prims = rec.get("primaryDocument", [])

    cik_int = str(int(cik))
    out: List[FilingItem] = []
    for i in range(len(forms)):
        form = forms[i]
        if form not in ("10-K", "10-Q", "8-K"):
            continue
        acc_nodash = accs[i].replace("-", "")
        doc = prims[i] or ""
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"
            if doc else
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={cik}&type={form}"
        )
        is_earnings = form == "8-K" and "2.02" in (items[i] if i < len(items) else "")
        title = {"10-K": "年報 10-K", "10-Q": "季報 10-Q",
                 "8-K": "重大訊息 8-K（財報發布）" if is_earnings else "重大訊息 8-K"}[form]
        out.append(FilingItem(form=form, date=dates[i], title=title, url=url,
                              is_earnings=is_earnings))
        if len(out) >= limit:
            break
    return out
