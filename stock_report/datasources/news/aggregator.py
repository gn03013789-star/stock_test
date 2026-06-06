"""新聞聚合器：關鍵字策略 + 三層 fallback + 去重聚合。

關鍵字策略（依序）：
  1. company_name
  2. company_name + stock_id
  3. stock_id + company_name
  4. industry_name + company_name
  5. industry_name（fallback）

三層 fallback：
  第 1 層：以個股關鍵字向各 provider 搜尋。
  第 2 層：補上「股票代號 + 名稱」「名稱 + 股價/法人」等變體。
  第 3 層：個股結果不足 → 改以產業關鍵字搜尋近 30 天新聞。

任一 provider 失敗都被 safe_search 吞掉，不影響其他來源；
全部失敗仍回傳空的 NewsBundle + errors，不 crash。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from ...config import NEWS_LOOKBACK_DAYS, NEWS_MAX_ITEMS
from ...core.models import NewsBundle, NewsItem, StockProfile
from ...core.relevance import is_relevant
from .base import NewsProvider
from .cnyes import CnyesProvider
from .google_news import GoogleNewsProvider

log = logging.getLogger(__name__)


def _providers() -> List[NewsProvider]:
    return [GoogleNewsProvider(), CnyesProvider()]


def _stock_keywords(profile: StockProfile) -> List[str]:
    name = profile.company_name
    sid = profile.stock_id
    ind = profile.industry_name
    kws: List[str] = []
    if name:
        kws.append(name)
    if name and sid and sid != name:
        kws.append(f"{name} {sid}")
        kws.append(f"{sid} {name}")
    if ind and name:
        kws.append(f"{ind} {name}")
    # 去重保序
    seen, out = set(), []
    for k in kws:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def get_news(profile: StockProfile, max_items: int = NEWS_MAX_ITEMS) -> NewsBundle:
    bundle = NewsBundle()
    providers = _providers()
    collected: List[NewsItem] = []

    # --- 第 1、2 層：個股關鍵字 ---
    for kw in _stock_keywords(profile):
        for prov in providers:
            items = prov.safe_search(kw, limit=max_items)
            if items:
                bundle.status.mark_ok(prov.name)
            else:
                bundle.status.add_error(f"{prov.name}：'{kw}' 無結果")
            collected.extend(items)
        if len({i.url for i in collected}) >= max_items * 2:
            break

    # 相關性過濾：只留確實提及此檔（代號或獨立公司名）的新聞，
    # 避免短名稱對到他檔（如「華新」對到「華新科」）。
    relevant = [
        it for it in collected
        if is_relevant(f"{it.title} {it.snippet}", profile)
    ]
    deduped = _dedupe_and_sort(relevant)

    # --- 第 3 層：個股不足 → 產業 fallback ---
    if len(deduped) < max(3, max_items // 3) and profile.industry_name:
        log.info("個股新聞不足，改抓產業 '%s' 近 %d 天", profile.industry_name,
                 NEWS_LOOKBACK_DAYS)
        bundle.used_industry_fallback = True
        ind_items: List[NewsItem] = []
        for prov in providers:
            ind_items.extend(prov.safe_search(profile.industry_name, limit=max_items))
        cutoff = datetime.now() - timedelta(days=NEWS_LOOKBACK_DAYS)
        ind_items = [
            i for i in ind_items
            if (i.publish_date is None or i.publish_date >= cutoff)
        ]
        deduped = _dedupe_and_sort(deduped + ind_items)

    bundle.items = deduped[:max_items]
    if not bundle.items and not bundle.status.errors:
        bundle.status.add_error("所有新聞來源皆無結果")
    return bundle


def _dedupe_and_sort(items: List[NewsItem]) -> List[NewsItem]:
    seen = set()
    out: List[NewsItem] = []
    for it in items:
        key = it.url or it.title
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    # 有日期者優先、由新到舊；無日期者排後
    out.sort(key=lambda i: i.publish_date or datetime.min, reverse=True)
    return out
