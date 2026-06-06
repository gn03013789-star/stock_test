"""NewsProvider 抽象介面。

每個 provider 的 search() 必須自我吞錯：失敗回傳空清單，
絕不向上拋出例外（單一來源失敗不可拖垮整體新聞模組）。
"""

from __future__ import annotations

import abc
import logging
from typing import List

from ...core.models import NewsItem

log = logging.getLogger(__name__)


class NewsProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def search(self, keyword: str, limit: int = 10) -> List[NewsItem]:
        """以關鍵字搜尋新聞，回傳 NewsItem 清單。失敗回空清單。"""
        raise NotImplementedError

    def safe_search(self, keyword: str, limit: int = 10) -> List[NewsItem]:
        """包一層 try/except，保證不拋例外。"""
        try:
            items = self.search(keyword, limit=limit) or []
            for it in items:
                it.matched_keyword = it.matched_keyword or keyword
                it.source = it.source or self.name
            return items
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] 搜尋 '%s' 失敗：%s", self.name, keyword, e)
            return []
