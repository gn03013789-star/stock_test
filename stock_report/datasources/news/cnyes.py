"""鉅亨網（cnyes）新聞 provider（best-effort）。

使用鉅亨公開的新聞搜尋 API（回傳 JSON）。若改版或被限制，
safe_search 會吞錯回空清單，由 Google News 骨幹兜底。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List

from ...core.models import NewsItem
from .base import NewsProvider

log = logging.getLogger(__name__)

_MARK_RE = re.compile(r"</?mark>")


class CnyesProvider(NewsProvider):
    name = "鉅亨網"

    # 鉅亨公開新聞搜尋 API
    API = "https://api.cnyes.com/media/api/v1/search/news"

    def search(self, keyword: str, limit: int = 10) -> List[NewsItem]:
        from ...utils.http import fetch

        data = fetch(self.API, params={"q": keyword, "limit": limit}, expect="json")
        if not isinstance(data, dict):
            return []
        rows = (data.get("items") or {}).get("data") or data.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("data", [])

        items: List[NewsItem] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            news_id = row.get("newsId") or row.get("id")
            url = (
                f"https://news.cnyes.com/news/id/{news_id}"
                if news_id
                else row.get("url", "")
            )
            ts = row.get("publishAt") or row.get("publish_at")
            pub = None
            if ts:
                try:
                    pub = datetime.fromtimestamp(int(ts))
                except (ValueError, OSError, TypeError):
                    pub = None
            title = _MARK_RE.sub("", row.get("title") or "").strip()
            items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source=self.name,
                    publish_date=pub,
                    snippet=(row.get("summary") or "").strip()[:200],
                    matched_keyword=keyword,
                )
            )
        return items
