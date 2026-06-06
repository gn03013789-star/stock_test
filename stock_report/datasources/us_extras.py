"""美股法說會資訊與延伸資料連結。

依使用者選定方向：
- 法說會：整理「官方資料 + 連結」——下次財報日期（yfinance）、SEC 8-K 財報
  新聞稿連結（官方公開）、逐字稿標題+連結（公開新聞，不抓全文）。
- 第三方財報站（Morningstar/Roic.ai/Gurufocus/SEC）：提供深層連結導引，不擷取其數據。

任何失敗都記錄在 status，不丟例外。
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import quote

from ..core.models import (
    EarningsCallInfo,
    FilingItem,
    NewsItem,
    StockProfile,
    UsFinancials,
)

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def get_earnings_call(
    profile: StockProfile, financials: Optional[UsFinancials]
) -> EarningsCallInfo:
    info = EarningsCallInfo()

    # 1) 下次財報/法說會日期（yfinance）
    info.next_date = _next_earnings_date(profile.stock_id)

    # 2) SEC 8-K 財報新聞稿（Item 2.02）——複用已抓到的申報清單
    if financials and financials.filings:
        info.press_releases = [f for f in financials.filings if f.is_earnings][:4]

    # 3) 逐字稿標題 + 連結（公開新聞，英文站為主，不抓全文）
    name = profile.english_name or profile.company_name
    info.transcript_links = _transcript_links(f"{name} earnings call transcript")

    if info.next_date or info.press_releases or info.transcript_links:
        info.status.mark_ok("yfinance / SEC / 公開新聞")
    else:
        info.status.add_error("查無公開可得法說會資訊")
    return info


def _next_earnings_date(ticker: str) -> str:
    try:
        import yfinance as yf

        tk = yf.Ticker(ticker)
        cal = getattr(tk, "calendar", None)
        # 新版 yfinance：calendar 為 dict
        if isinstance(cal, dict):
            val = cal.get("Earnings Date")
            if isinstance(val, (list, tuple)) and val:
                return str(val[0])
            if val:
                return str(val)
        # 舊版：DataFrame
        if cal is not None and hasattr(cal, "loc"):
            try:
                return str(cal.loc["Earnings Date"][0])
            except Exception:  # noqa: BLE001
                pass
        # 退而求其次：earnings_dates 取未來最近一筆
        ed = getattr(tk, "earnings_dates", None)
        if ed is not None and not ed.empty:
            future = ed[ed.index > datetime.now(ed.index.tz)]
            if not future.empty:
                return str(future.index.min().date())
    except Exception as e:  # noqa: BLE001
        log.warning("取得下次財報日期失敗 %s：%s", ticker, e)
    return ""


def _transcript_links(query: str, limit: int = 6) -> List[NewsItem]:
    """以英文 locale 查 Google News RSS，取逐字稿/法說會相關標題與連結。"""
    try:
        import feedparser

        url = (
            f"https://news.google.com/rss/search?q={quote(query)}"
            "&hl=en-US&gl=US&ceid=US:en"
        )
        feed = feedparser.parse(url)
        items: List[NewsItem] = []
        for entry in feed.entries[:limit]:
            pub = None
            if getattr(entry, "published_parsed", None):
                try:
                    pub = datetime(*entry.published_parsed[:6])
                except (TypeError, ValueError):
                    pub = None
            title = entry.get("title", "")
            src = ""
            if " - " in title:
                title, src = title.rsplit(" - ", 1)
            items.append(NewsItem(
                title=title.strip(),
                url=entry.get("link", ""),
                source=src.strip() or "Google News",
                publish_date=pub,
                snippet=re.sub(
                    r"\s+", " ",
                    html.unescape(_TAG_RE.sub("", entry.get("summary", "")))
                ).strip()[:160],
                matched_keyword=query,
            ))
        return items
    except Exception as e:  # noqa: BLE001
        log.warning("逐字稿連結查詢失敗：%s", e)
        return []


def build_references(profile: StockProfile, cik: str = "") -> List[Tuple[str, str]]:
    """第三方財報站深層連結（不擷取資料，僅導引）。"""
    t = profile.stock_id.upper()
    refs: List[Tuple[str, str]] = []
    if cik:
        refs.append((
            "SEC EDGAR（官方申報全文）",
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
            "&type=10-K&dateb=&owner=include&count=40",
        ))
    refs.extend([
        ("Morningstar（財務評等與分析）",
         f"https://www.morningstar.com/search?query={quote(t)}"),
        ("Roic.ai（ROIC 與財務指標）", f"https://www.roic.ai/quote/{t}"),
        ("GuruFocus（價值投資指標）",
         f"https://www.gurufocus.com/stock/{t}/summary"),
        ("Motley Fool（法說會逐字稿）",
         f"https://www.fool.com/quote/{_fool_exchange(profile)}/{t.lower()}/"),
    ])
    return refs


def _fool_exchange(profile: StockProfile) -> str:
    # Motley Fool 網址含交易所；無法精準辨識時預設 nasdaq（連不到時使用者仍可自行搜尋）。
    exch = (profile.market_type or "").upper()
    if "NYSE" in exch:
        return "nyse"
    return "nasdaq"
