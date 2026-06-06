"""股價預測：線性回歸趨勢 + 蒙地卡羅（GBM）波動率錐。

重要：股價短期接近隨機漫步，本模組僅以「歷史趨勢與波動率」做統計模擬，
產生未來價格的「情境區間」，不代表未來實際走勢，絕非投資建議。

方法：
1. 取最近 window 個交易日，對收盤價做線性回歸 -> 趨勢延伸線（若近期趨勢延續）。
2. 以最近 window 日的對數報酬估計漂移 mu 與波動率 sigma。
3. 幾何布朗運動（GBM）蒙地卡羅模擬 n_sims 條未來路徑，取各日 10/50/90 百分位
   形成「悲觀 / 中位 / 樂觀」情境錐。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List

from ..core.models import ForecastResult, PriceData

log = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252

# 預測期間選項（顯示標籤 -> 交易日數）
HORIZON_OPTIONS = {
    "1 週": 5,
    "2 週": 10,
    "1 個月": 20,
    "3 個月": 60,
}


def horizon_label(days: int) -> str:
    """將交易日數轉為人類可讀的期間描述。"""
    for label, d in HORIZON_OPTIONS.items():
        if days == d:
            return label
    if days <= 5:
        return "約一週"
    if days <= 10:
        return "約兩週"
    if days <= 20:
        return "約一個月"
    if days <= 60:
        return "約三個月"
    return f"{days} 個交易日"


def forecast(
    price: PriceData,
    horizon_days: int = 20,
    window: int = 120,
    n_sims: int = 3000,
    seed: int = 42,
) -> ForecastResult:
    """產生未來 horizon_days 個交易日的價格情境。失敗時 status 標記錯誤。"""
    import numpy as np

    res = ForecastResult(horizon_days=horizon_days)
    pts = price.points
    if len(pts) < 30:
        res.status.add_error("股價資料不足，無法預測")
        return res

    closes = np.array([p.close for p in pts], dtype=float)
    closes = closes[closes > 0]
    if len(closes) < 30:
        res.status.add_error("有效股價資料不足，無法預測")
        return res

    last_price = float(closes[-1])
    res.last_price = last_price
    res.last_date = pts[-1].date

    w = int(min(window, len(closes)))
    res.window = w
    recent = closes[-w:]

    # --- 1) 線性回歸趨勢 ---
    x = np.arange(w)
    slope, intercept = np.polyfit(x, recent, 1)
    yhat = slope * x + intercept
    ss_res = float(np.sum((recent - yhat) ** 2))
    ss_tot = float(np.sum((recent - recent.mean()) ** 2))
    res.r2 = (1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    future_x = np.arange(w, w + horizon_days)
    res.trend = [float(v) for v in (slope * future_x + intercept)]

    # --- 2) 對數報酬估計 mu, sigma ---
    logret = np.diff(np.log(recent))
    mu = float(np.mean(logret))
    sigma = float(np.std(logret, ddof=1)) if len(logret) > 1 else 0.0
    res.annual_vol = sigma * np.sqrt(TRADING_DAYS_PER_YEAR) * 100

    # --- 3) GBM 蒙地卡羅 ---
    if sigma == 0:
        # 無波動：以趨勢線當所有情境
        res.p10 = res.p50 = res.p90 = list(res.trend)
    else:
        rng = np.random.default_rng(seed)
        drift = mu - 0.5 * sigma ** 2
        shocks = drift + sigma * rng.standard_normal((n_sims, horizon_days))
        log_paths = np.cumsum(shocks, axis=1)
        paths = last_price * np.exp(log_paths)
        res.p10 = [float(v) for v in np.percentile(paths, 10, axis=0)]
        res.p50 = [float(v) for v in np.percentile(paths, 50, axis=0)]
        res.p90 = [float(v) for v in np.percentile(paths, 90, axis=0)]

    res.future_dates = _future_trading_days(pts[-1].date, horizon_days)
    res.status.mark_ok("線性回歸 + 蒙地卡羅 GBM")
    return res


def _future_trading_days(start: date, n: int) -> List[date]:
    """回傳 start 之後的 n 個交易日（僅略過週末，不含假日）。"""
    out: List[date] = []
    d = start
    while len(out) < n:
        d = d + timedelta(days=1)
        if d.weekday() < 5:  # 0-4 為週一至週五
            out.append(d)
    return out


def insight(res: ForecastResult, currency: str = "") -> str:
    """產生中文情境說明（含免責）。"""
    if not res.status.ok or not res.p50:
        return "目前查無足夠資料進行股價情境模擬。"
    unit = currency or ""
    end_p50 = res.p50[-1]
    end_p10 = res.p10[-1]
    end_p90 = res.p90[-1]
    chg = (end_p50 - res.last_price) / res.last_price * 100 if res.last_price else 0
    direction = "上行" if chg > 0 else "下行" if chg < 0 else "持平"
    span = horizon_label(res.horizon_days)
    parts = [
        f"以最近 {res.window} 個交易日的趨勢與波動率，模擬未來 {res.horizon_days} "
        f"個交易日（{span}）的價格情境：",
        f"中位情境約 {end_p50:.1f}{unit}（較現價 {direction} {abs(chg):.1f}%），",
        f"樂觀情境（90 百分位）約 {end_p90:.1f}{unit}，"
        f"悲觀情境（10 百分位）約 {end_p10:.1f}{unit}。",
        f"年化波動率約 {res.annual_vol:.1f}%，趨勢線擬合度 R²={res.r2:.2f}。",
        "※ 本預測為基於歷史資料的統計模擬，股價受突發消息影響甚大，"
        "不代表未來實際走勢，僅供參考，不構成投資建議。",
    ]
    return "".join(parts)
