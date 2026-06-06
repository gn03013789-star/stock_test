"""目標價 / 投資評等模組。

不假設官方 API。複用新聞 provider，以「目標價/評等/法人/外資看法」等
關鍵字組合搜尋公開新聞，再用輕量規則抽取目標價、評等詞、券商名。
資料不足時 insufficient=True，由 PDF 顯示「查無一致公開資料」提示。
任何來源失敗都記錄在 status，不丟例外。
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from ..config import RATING_MAX_ITEMS
from ..core.models import RatingBundle, RatingItem, StockProfile
from .news.cnyes import CnyesProvider
from .news.google_news import GoogleNewsProvider

log = logging.getLogger(__name__)

# 評等詞彙
_RATING_WORDS = ["買進", "加碼", "增持", "強力買進", "區間操作", "中立", "持有",
                 "減碼", "賣出", "落後大盤", "優於大盤", "表現與大盤一致"]

# 目標價：抓「目標價 ... 數字」或「上看 數字」
_TARGET_RE = re.compile(
    r"(?:目標價|上看|喊到|看至|目標價位)\D{0,8}?([0-9]{2,4}(?:\.\d+)?)"
)

# 常見券商 / 法人關鍵字（可辨識才填）
_BROKERS = ["外資", "投信", "自營商", "高盛", "摩根", "大摩", "小摩", "美林",
            "瑞銀", "瑞信", "花旗", "野村", "里昂", "麥格理", "匯豐", "凱基",
            "元大", "富邦", "群益", "國泰", "中信", "永豐", "統一投顧", "兆豐"]


def _rating_keywords(profile: StockProfile) -> List[str]:
    name = profile.company_name
    return [
        f"{name} 目標價",
        f"{name} 評等",
        f"{name} 法人",
        f"{name} 外資 看法",
        f"{name} 買進",
        f"{name} 中立",
        f"{name} 賣出",
    ]


def get_rating(profile: StockProfile, max_items: int = RATING_MAX_ITEMS) -> RatingBundle:
    bundle = RatingBundle()
    providers = [GoogleNewsProvider(), CnyesProvider()]

    raw_items = []
    for kw in _rating_keywords(profile):
        for prov in providers:
            found = prov.safe_search(kw, limit=8)
            if found:
                bundle.status.mark_ok(prov.name)
            raw_items.extend(found)

    # 去重 + 相關性過濾（只保留確實提及此檔者，剔除他檔的目標價/評等）
    from ..core.relevance import is_relevant

    seen, news_items = set(), []
    for it in raw_items:
        key = it.url or it.title
        if not key or key in seen:
            continue
        if not is_relevant(f"{it.title} {it.snippet}", profile):
            continue
        seen.add(key)
        news_items.append(it)

    ratings: List[RatingItem] = []
    for it in news_items:
        text = f"{it.title} {it.snippet}"
        target = _extract_target(text)
        rating = _extract_rating(text)
        broker = _extract_broker(text)
        # 只保留至少含一項可辨識資訊者
        if target is None and not rating and not broker:
            continue
        ratings.append(
            RatingItem(
                source=it.source,
                url=it.url,
                publish_date=it.publish_date,
                broker=broker,
                rating=rating,
                target_price=target,
                note=it.title[:60],
            )
        )

    # 依日期排序
    from datetime import datetime

    ratings.sort(key=lambda r: r.publish_date or datetime.min, reverse=True)
    bundle.items = ratings[:max_items]

    if not bundle.items:
        bundle.insufficient = True
        bundle.status.add_error("查無一致公開資料，僅整理公開可得資訊")

    return bundle


def _extract_target(text: str) -> Optional[float]:
    m = _TARGET_RE.search(text)
    if m:
        try:
            val = float(m.group(1))
            # 合理範圍過濾（避免抓到年份/百分比）
            if 1 <= val <= 5000:
                return val
        except ValueError:
            pass
    return None


def _extract_rating(text: str) -> str:
    for w in _RATING_WORDS:
        if w in text:
            return w
    return ""


def _extract_broker(text: str) -> str:
    found = [b for b in _BROKERS if b in text]
    return "、".join(dict.fromkeys(found)) if found else ""
