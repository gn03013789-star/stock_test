"""Google News RSS provider（新聞骨幹）。

合法、穩定、可帶關鍵字，聚合多家媒體標題/連結/日期/Google 提供之摘要。
不抓各媒體全文，符合「不爬全文」原則。
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import List
from urllib.parse import quote

from ...core.models import NewsItem
from .base import NewsProvider

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    text = _TAG_RE.sub("", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class GoogleNewsProvider(NewsProvider):
    name = "Google News"

    BASE = "https://news.google.com/rss/search"

    def search(self, keyword: str, limit: int = 10) -> List[NewsItem]:
        import feedparser

        # hl/gl/ceid 設成繁中台灣，優先取得台灣媒體
        url = (
            f"{self.BASE}?q={quote(keyword)}"
            "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
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
            # Google News 標題格式："標題 - 媒體名"
            title = entry.get("title", "")
            src = ""
            if " - " in title:
                title, src = title.rsplit(" - ", 1)
            src = (getattr(entry, "source", {}) or {}).get("title", "") or src
            items.append(
                NewsItem(
                    title=title.strip(),
                    url=entry.get("link", ""),
                    source=src.strip() or self.name,
                    publish_date=pub,
                    snippet=_strip_html(entry.get("summary", ""))[:200],
                    matched_keyword=keyword,
                )
            )
        return items
