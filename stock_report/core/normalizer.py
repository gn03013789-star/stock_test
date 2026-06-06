"""股票名稱正規化：代號/名稱 -> StockProfile。

流程：
1. 判斷輸入是台股代號、美股代號，還是名稱。
2. 先查內建對照表。
3. 找不到走動態 fallback：
   - 台股：TWSE 公開上市清單 + TPEx 上櫃清單。
   - 美股：yfinance Ticker.info。
任何 fallback 失敗都不丟例外，盡量回傳可用的 StockProfile。
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from ..utils.cache import get_or_set
from ..utils.http import fetch
from . import stock_map
from .models import StockProfile

log = logging.getLogger(__name__)

_TW_ID_RE = re.compile(r"^\d{4,6}$")
_US_ID_RE = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,6}$")


def normalize(query: str) -> StockProfile:
    """將使用者輸入轉為 StockProfile。永遠回傳一個物件（盡力而為）。"""
    q = (query or "").strip()
    if not q:
        return StockProfile(stock_id="", company_name="(未輸入)", market="TW")

    # 1. 台股代號
    if _TW_ID_RE.match(q):
        return _profile_for_tw_id(q)

    # 2. 名稱反查（內建表）
    sid = stock_map.lookup_by_name(q)
    if sid:
        return _profile_for_tw_id(sid)

    # 3. 美股代號（純英文字母）
    if _US_ID_RE.match(q) and q.upper() == q.replace(" ", ""):
        return _profile_for_us(q.upper())

    # 4. 最後嘗試：當成美股代號 / 名稱
    if _US_ID_RE.match(q):
        return _profile_for_us(q.upper())

    # 完全無法判斷：先當台股名稱保留原字串
    log.info("無法辨識輸入 '%s'，以原字串建立 profile", q)
    return StockProfile(stock_id=q, company_name=q, market="TW")


# --------------------------------------------------------------------------- #
# 台股
# --------------------------------------------------------------------------- #
def _profile_for_tw_id(stock_id: str) -> StockProfile:
    info = stock_map.lookup_by_id(stock_id)
    if info:
        return StockProfile(
            stock_id=stock_id,
            company_name=info["name"],
            aliases=info.get("aliases", []),
            english_name=info.get("english", ""),
            industry_name=info.get("industry", ""),
            market_type=info.get("market", ""),
            market="TW",
            currency="TWD",
        )

    # fallback：查 TWSE / TPEx 公開清單
    dyn = _lookup_tw_listing(stock_id)
    if dyn:
        return StockProfile(
            stock_id=stock_id,
            company_name=dyn.get("name", stock_id),
            industry_name=dyn.get("industry", ""),
            market_type=dyn.get("market", ""),
            market="TW",
            currency="TWD",
        )

    log.warning("台股代號 %s 查無資料，回傳最小 profile", stock_id)
    return StockProfile(stock_id=stock_id, company_name=stock_id, market="TW")


def _lookup_tw_listing(stock_id: str) -> Optional[dict]:
    """從 TWSE / TPEx 公開清單動態查詢公司名與市場別。"""

    def _producer():
        # TWSE 上市清單（含中文簡稱與產業別）
        twse = fetch(
            "https://openapi.twse.com.tw/v1/opendata/t187ap03_L", expect="json"
        )
        if isinstance(twse, list):
            for row in twse:
                if str(row.get("公司代號", "")).strip() == stock_id:
                    return {
                        "name": row.get("公司簡稱", "").strip(),
                        "industry": stock_map.industry_name_from_code(
                            row.get("產業別", "")),
                        "market": "上市",
                    }
        # TPEx 上櫃清單
        tpex = fetch(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
            expect="json",
        )
        if isinstance(tpex, list):
            for row in tpex:
                if str(row.get("SecuritiesCompanyCode", "")).strip() == stock_id:
                    return {
                        "name": row.get("CompanyName", "").strip(),
                        "industry": "",
                        "market": "上櫃",
                    }
        return None

    try:
        return get_or_set(f"tw_listing:{stock_id}", _producer, ttl=86400)
    except Exception as e:  # noqa: BLE001 - fallback 不可 crash
        log.warning("TWSE/TPEx 清單查詢失敗：%s", e)
        return None


# --------------------------------------------------------------------------- #
# 美股
# --------------------------------------------------------------------------- #
def _profile_for_us(ticker: str) -> StockProfile:
    name, industry, exch, currency = ticker, "", "US", "USD"
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        name = info.get("longName") or info.get("shortName") or ticker
        industry = info.get("sector") or info.get("industry") or ""
        exch = info.get("exchange") or "US"
        currency = info.get("currency") or "USD"
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance 查詢美股 %s 失敗：%s", ticker, e)

    return StockProfile(
        stock_id=ticker,
        company_name=name,
        english_name=name,
        industry_name=industry,
        market_type=f"美股 {exch}",
        market="US",
        currency=currency,
    )
