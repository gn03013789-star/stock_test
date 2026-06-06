"""技術指標：MACD、KD（隨機指標）、RSI。

僅用公開股價資料計算，純統計指標，不構成投資建議。
KD 需要最高/最低價（PricePoint.high/low）；若缺漏則以收盤價近似。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ..core.models import PriceData, Technical

log = logging.getLogger(__name__)


def _ema(values: List[float], n: int) -> List[float]:
    k = 2.0 / (n + 1)
    out: List[float] = []
    ema: Optional[float] = None
    for v in values:
        ema = v if ema is None else v * k + ema * (1 - k)
        out.append(ema)
    return out


def _macd(closes: List[float], fast=12, slow=26, signal=9):
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [a - b for a, b in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    hist = [a - b for a, b in zip(dif, dea)]
    return dif, dea, hist


def _kd(highs, lows, closes, n=9):
    k_list: List[Optional[float]] = []
    d_list: List[Optional[float]] = []
    k_prev, d_prev = 50.0, 50.0
    for i in range(len(closes)):
        if i < n - 1:
            k_list.append(None)
            d_list.append(None)
            continue
        hh = max(highs[i - n + 1:i + 1])
        ll = min(lows[i - n + 1:i + 1])
        rsv = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100
        k_prev = 2 / 3 * k_prev + 1 / 3 * rsv
        d_prev = 2 / 3 * d_prev + 1 / 3 * k_prev
        k_list.append(k_prev)
        d_list.append(d_prev)
    return k_list, d_list


def _rsi(closes: List[float], n=14):
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for i in range(n, len(closes)):
        if i > n:
            avg_gain = (avg_gain * (n - 1) + gains[i - 1]) / n
            avg_loss = (avg_loss * (n - 1) + losses[i - 1]) / n
        rs = float("inf") if avg_loss == 0 else avg_gain / avg_loss
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + rs)
    return out


def _obv(closes: List[float], volumes: List[Optional[float]]):
    out: List[Optional[float]] = [0.0]
    for i in range(1, len(closes)):
        v = volumes[i] or 0.0
        if closes[i] > closes[i - 1]:
            out.append(out[-1] + v)
        elif closes[i] < closes[i - 1]:
            out.append(out[-1] - v)
        else:
            out.append(out[-1])
    return out


def compute(price: PriceData) -> Technical:
    tech = Technical()
    pts = price.points
    if len(pts) < 30:
        tech.status.add_error("股價資料不足，無法計算技術指標")
        return tech

    closes = [p.close for p in pts]
    highs = [p.high if p.high is not None else p.close for p in pts]
    lows = [p.low if p.low is not None else p.close for p in pts]
    volumes = [p.volume for p in pts]

    tech.dates = [p.date for p in pts]
    tech.dif, tech.dea, tech.macd_hist = _macd(closes)
    tech.k, tech.d = _kd(highs, lows, closes)
    tech.rsi = _rsi(closes)
    if any(v for v in volumes):
        tech.obv = _obv(closes, volumes)
    tech.status.mark_ok("MACD / KD / RSI / OBV")
    return tech


def insight(tech: Technical) -> str:
    if not tech.status.ok:
        return "目前查無足夠資料計算技術指標。"
    parts = []

    # MACD
    if tech.dif and tech.dea:
        dif, dea, hist = tech.dif[-1], tech.dea[-1], tech.macd_hist[-1]
        bias = "偏多" if hist > 0 else "偏空" if hist < 0 else "中性"
        cross = ""
        if len(tech.macd_hist) >= 2 and tech.macd_hist[-2] is not None:
            if tech.macd_hist[-2] <= 0 < hist:
                cross = "，剛出現黃金交叉"
            elif tech.macd_hist[-2] >= 0 > hist:
                cross = "，剛出現死亡交叉"
        parts.append(
            f"MACD：DIF={dif:.2f}、DEA={dea:.2f}、柱狀={hist:+.2f}（{bias}{cross}）。")

    # KD
    if tech.k and tech.k[-1] is not None:
        k, d = tech.k[-1], tech.d[-1]
        zone = "超買區(>80)" if k > 80 else "超賣區(<20)" if k < 20 else "中性區"
        kd_bias = "K>D 偏多" if k > d else "K<D 偏空" if k < d else "K≈D"
        parts.append(f"KD：K={k:.1f}、D={d:.1f}（{kd_bias}，位於{zone}）。")

    # RSI
    rsi_vals = [v for v in tech.rsi if v is not None]
    if rsi_vals:
        rsi = rsi_vals[-1]
        zone = "超買(>70)" if rsi > 70 else "超賣(<30)" if rsi < 30 else "中性"
        parts.append(f"RSI(14)={rsi:.1f}（{zone}）。")

    # OBV（量能）
    if tech.obv and len(tech.obv) >= 6:
        recent, past = tech.obv[-1], tech.obv[-6]
        flow = "量能流入（偏多）" if recent > past else \
               "量能流出（偏空）" if recent < past else "量能持平"
        parts.append(f"OBV 近 5 日{flow}。")

    parts.append("※ 技術指標為統計訊號，僅供參考，不構成投資建議。")
    return "".join(parts)
