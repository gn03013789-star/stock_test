"""簡單的本地檔案快取，減少重複網路請求。"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..config import HTTP_CACHE_DIR, HTTP_CACHE_TTL

log = logging.getLogger(__name__)


def _key_path(key: str) -> Path:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return HTTP_CACHE_DIR / f"{h}.json"


def get_or_set(
    key: str,
    producer: Callable[[], Any],
    *,
    ttl: int = HTTP_CACHE_TTL,
) -> Any:
    """若快取有效則回傳快取，否則呼叫 producer 並寫入快取。

    producer 回傳 None 時不寫入快取（代表來源失敗）。
    """
    path = _key_path(key)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - payload["ts"] < ttl:
                return payload["data"]
        except (json.JSONDecodeError, KeyError, OSError) as e:
            log.debug("快取讀取失敗 %s: %s", key, e)

    data = producer()
    if data is not None:
        try:
            path.write_text(
                json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False),
                encoding="utf-8",
            )
        except (OSError, TypeError) as e:
            log.debug("快取寫入失敗 %s: %s", key, e)
    return data
