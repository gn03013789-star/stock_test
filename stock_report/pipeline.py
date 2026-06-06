"""端到端流程：輸入查詢字串 -> 產生 Report -> PDF bytes。

每個資料模組獨立執行，任一失敗都不影響其他模組（各自回傳含 status 的空結構）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from .analysis import forecast as forecast_mod
from .analysis import indicators as indicators_mod
from .analysis import insights
from .core.models import (
    EpsData,
    NewsBundle,
    PriceData,
    RatingBundle,
    Report,
    RevenueData,
)
from .core.normalizer import normalize
from .datasources import eps as eps_mod
from .datasources import price as price_mod
from .datasources import rating as rating_mod
from .datasources import revenue as revenue_mod
from .datasources.news import get_news

log = logging.getLogger(__name__)

ProgressCb = Optional[Callable[[str, float], None]]


def build_report(query: str, progress: ProgressCb = None,
                 forecast_days: int = 20) -> Report:
    """查詢字串 -> Report。各模組獨立 try/except，不中斷整體。"""

    def _step(msg: str, frac: float):
        log.info(msg)
        if progress:
            try:
                progress(msg, frac)
            except Exception:  # noqa: BLE001
                pass

    _step("正在辨識股票…", 0.05)
    profile = normalize(query)

    _step(f"查詢股價（{profile.company_name}）…", 0.2)
    price = _safe(lambda: price_mod.get_price(profile), None) or PriceData()

    _step("計算股價情境模擬…", 0.3)
    fc = _safe(lambda: forecast_mod.forecast(price, horizon_days=forecast_days), None)
    fc_insight = forecast_mod.insight(fc, profile.currency) if fc else ""

    _step("計算技術指標…", 0.33)
    tech = _safe(lambda: indicators_mod.compute(price), None)
    tech_insight = indicators_mod.insight(tech) if tech else ""

    _step("查詢營收…", 0.4)
    revenue = _safe(lambda: revenue_mod.get_revenue(profile), None) or RevenueData()

    _step("查詢 EPS…", 0.55)
    eps = _safe(lambda: eps_mod.get_eps(profile), None) or EpsData()

    _step("彙整新聞…", 0.7)
    news = _safe(lambda: get_news(profile), None) or NewsBundle()

    _step("彙整目標價與評等…", 0.85)
    rating = _safe(lambda: rating_mod.get_rating(profile), None) or RatingBundle()

    # --- 美股專屬：SEC 財報、法說會、延伸連結 ---
    us_financials = None
    earnings_call = None
    references: list = []
    if profile.market == "US":
        _step("查詢 SEC 財報與法說會…", 0.9)
        from .datasources import sec, us_extras

        us_financials = _safe(lambda: sec.get_us_financials(profile.stock_id), None)
        earnings_call = _safe(
            lambda: us_extras.get_earnings_call(profile, us_financials), None)
        cik = us_financials.cik if us_financials else ""
        references = _safe(lambda: us_extras.build_references(profile, cik), None) or []

    # --- 英文新聞翻譯為繁中摘要 ---
    from .config import ENABLE_TRANSLATION

    if ENABLE_TRANSLATION:
        _step("翻譯英文新聞摘要…", 0.93)
        _safe(lambda: _translate_news(news.items), None)
        if earnings_call is not None:
            _safe(lambda: _translate_news(earnings_call.transcript_links), None)

    _step("產生趨勢說明…", 0.95)
    report = Report(
        profile=profile,
        generated_at=datetime.now(),
        price=price,
        revenue=revenue,
        eps=eps,
        news=news,
        rating=rating,
        price_insight=insights.price_insight(price),
        revenue_insight=insights.revenue_insight(revenue),
        eps_insight=insights.eps_insight(eps),
        forecast=fc,
        forecast_insight=fc_insight,
        technical=tech,
        technical_insight=tech_insight,
        us_financials=us_financials,
        earnings_call=earnings_call,
        references=references,
    )
    _step("完成。", 1.0)
    return report


def build_pdf_bytes(query: str, progress: ProgressCb = None) -> tuple[Report, bytes]:
    from .report.pdf_builder import build_pdf

    report = build_report(query, progress=progress)
    pdf = build_pdf(report)
    return report, pdf


def _translate_news(items) -> None:
    """就地為英文新聞填入繁中摘要（summary_zh）。"""
    from .utils.translate import looks_english, to_zh

    for it in items:
        text = it.snippet or it.title
        if looks_english(text):
            it.summary_zh = to_zh(text)


def _safe(fn, default):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        log.warning("模組執行失敗：%s", e)
        return default
