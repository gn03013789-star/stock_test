"""共用 HTTP session。

設計原則：遇到 403 / robots / 連線錯誤時記錄並回傳 None，
讓呼叫端把該來源視為「失敗略過」，不可讓整體流程 crash。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from ..config import HTTP_RETRIES, HTTP_TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)

_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            }
        )
        _session = s
    return _session


def fetch(
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: Optional[float] = None,
    expect: str = "text",
) -> Optional[object]:
    """抓取 URL，失敗回傳 None（不丟例外）。

    expect: "text" / "json" / "bytes" / "response"
    """
    sess = get_session()
    timeout = timeout or HTTP_TIMEOUT
    last_err = None

    for attempt in range(HTTP_RETRIES + 1):
        try:
            resp = sess.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 403:
                log.warning("403 Forbidden（跳過此來源）: %s", url)
                return None
            if resp.status_code == 429:
                log.warning("429 Too Many Requests: %s", url)
                time.sleep(1.0 * (attempt + 1))
                last_err = "429"
                continue
            resp.raise_for_status()

            if expect == "json":
                return resp.json()
            if expect == "bytes":
                return resp.content
            if expect == "response":
                return resp
            resp.encoding = resp.apparent_encoding or resp.encoding
            return resp.text
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            log.debug("fetch 失敗（attempt %d）%s: %s", attempt + 1, url, e)
            time.sleep(0.4 * (attempt + 1))
        except ValueError as e:  # json 解析失敗
            last_err = str(e)
            log.debug("解析失敗 %s: %s", url, e)
            break

    log.warning("放棄抓取 %s（最後錯誤：%s）", url, last_err)
    return None
