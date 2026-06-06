"""以 matplotlib 產生圖表 PNG（股價 / 營收 / EPS）。

所有函式回傳 PNG bytes 或 None（無資料）。皆設定中文字型。
"""

from __future__ import annotations

import io
import logging
from typing import List, Optional

from ..core.models import EpsData, ForecastResult, PriceData, RevenueData, Technical
from . import fonts

log = logging.getLogger(__name__)

_FONT_READY = False


def _ensure_mpl():
    global _FONT_READY
    import matplotlib

    matplotlib.use("Agg")
    if not _FONT_READY:
        fonts.register_for_matplotlib()
        _FONT_READY = True


def _save(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return buf.getvalue()


# 均線定義：交易日數 -> (顯示名稱, 顏色)
MA_DEFS = {
    5: ("週線(5MA)", "#fb8500"),
    10: ("雙週線(10MA)", "#ffb703"),
    20: ("月線(20MA)", "#8338ec"),
    60: ("季線(60MA)", "#1a7f37"),
    120: ("半年線(120MA)", "#0096c7"),
    240: ("年線(240MA)", "#d00000"),
}
DEFAULT_MA = (5, 20)


def ma_label_to_period() -> dict:
    """{顯示名稱: 交易日數}，供 UI 多選使用。"""
    return {label: period for period, (label, _) in MA_DEFS.items()}


def price_chart(data: PriceData, title: str = "股價走勢",
                ma_periods=DEFAULT_MA) -> Optional[bytes]:
    if not data.points:
        return None
    _ensure_mpl()
    import matplotlib.pyplot as plt

    pts = data.points
    dates = [p.date for p in pts]
    closes = [p.close for p in pts]

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(dates, closes, color="#1f6feb", linewidth=1.3, label="日收盤")

    # 趨勢均線（可自選：週=5、月=20、季=60、年=240 …）
    def _ma(values, n):
        out = []
        for i in range(len(values)):
            if i + 1 < n:
                out.append(None)
            else:
                out.append(sum(values[i + 1 - n:i + 1]) / n)
        return out

    for n in sorted(set(ma_periods or [])):
        if n in MA_DEFS and len(closes) >= n:
            label, color = MA_DEFS[n]
            ax.plot(dates, _ma(closes, n), color=color, linewidth=1.0, label=label)

    # 成交量副軸
    vols = [p.volume for p in pts]
    if any(v for v in vols):
        ax2 = ax.twinx()
        ax2.bar(dates, [v or 0 for v in vols], color="#c9d1d9", alpha=0.4, width=1.0)
        ax2.set_ylabel("成交量", fontsize=8)
        ax2.tick_params(labelsize=7)

    # 標註高低點
    hi = max(pts, key=lambda p: p.close)
    lo = min(pts, key=lambda p: p.close)
    ax.annotate(f"高 {hi.close:.1f}", xy=(hi.date, hi.close),
                fontsize=8, color="#cf222e",
                xytext=(0, 8), textcoords="offset points", ha="center")
    ax.annotate(f"低 {lo.close:.1f}", xy=(lo.date, lo.close),
                fontsize=8, color="#1a7f37",
                xytext=(0, -12), textcoords="offset points", ha="center")

    ax.set_title(title, fontsize=12)
    ax.set_ylabel("價格", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, loc="upper left")
    fig.autofmt_xdate()
    return _save(fig)


def revenue_chart(data: RevenueData) -> Optional[bytes]:
    if not data.points:
        return None
    _ensure_mpl()
    import matplotlib.pyplot as plt

    pts = data.points
    labels = [p.label for p in pts]
    revs = [p.revenue for p in pts]
    x = range(len(pts))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    title = "季營收與年增率" if data.is_quarterly else "月營收與年增率"
    ax.bar(x, revs, color="#1f6feb", alpha=0.7, label=f"營收（{data.unit}）")
    ax.set_ylabel(f"營收（{data.unit}）", fontsize=9)

    yoys = [p.yoy for p in pts]
    if any(y is not None for y in yoys):
        ax2 = ax.twinx()
        ax2.plot(x, [y if y is not None else float("nan") for y in yoys],
                 color="#cf222e", marker="o", markersize=3, linewidth=1.2, label="YoY %")
        ax2.set_ylabel("年增率 %", fontsize=9)
        ax2.axhline(0, color="#999", linewidth=0.6)
        ax2.tick_params(labelsize=8)

    ax.set_title(title, fontsize=12)
    step = max(1, len(labels) // 12)
    ax.set_xticks(list(x)[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=7)
    ax.tick_params(labelsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    return _save(fig)


def forecast_chart(price: PriceData, fc: ForecastResult,
                   history_days: int = 90) -> Optional[bytes]:
    if not fc or not fc.status.ok or not fc.p50:
        return None
    _ensure_mpl()
    import matplotlib.pyplot as plt

    # 近期歷史
    hist = price.points[-history_days:] if price.points else []
    h_dates = [p.date for p in hist]
    h_close = [p.close for p in hist]

    fig, ax = plt.subplots(figsize=(8, 3.8))
    if h_dates:
        ax.plot(h_dates, h_close, color="#1f6feb", linewidth=1.3, label="歷史收盤")

    fd = fc.future_dates
    # 情境錐
    ax.fill_between(fd, fc.p10, fc.p90, color="#1f6feb", alpha=0.15,
                    label="情境區間（10~90 百分位）")
    ax.plot(fd, fc.p50, color="#cf222e", linewidth=1.4, linestyle="--",
            label="中位情境")
    ax.plot(fd, fc.trend, color="#1a7f37", linewidth=1.1, linestyle=":",
            label="趨勢延伸")
    # 接合點
    if h_dates:
        ax.plot([h_dates[-1], fd[0]], [h_close[-1], fc.p50[0]],
                color="#cf222e", linewidth=1.0, linestyle="--", alpha=0.6)

    from ..analysis.forecast import horizon_label

    ax.set_title(f"股價情境模擬（未來{horizon_label(fc.horizon_days)}，僅供參考）",
                 fontsize=12)
    ax.set_ylabel("價格", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, loc="best")
    fig.autofmt_xdate()
    return _save(fig)


def technical_chart(tech: Technical, history_days: int = 120) -> Optional[bytes]:
    """MACD / KD / RSI 三合一堆疊圖。"""
    if not tech or not tech.status.ok or not tech.dates:
        return None
    _ensure_mpl()
    import matplotlib.pyplot as plt

    s = slice(-history_days, None)
    x = tech.dates[s]

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(8, 7.2), sharex=True,
        gridspec_kw={"hspace": 0.25})

    # MACD
    dif, dea, hist = tech.dif[s], tech.dea[s], tech.macd_hist[s]
    colors = ["#cf222e" if (h or 0) >= 0 else "#1a7f37" for h in hist]
    ax1.bar(x, [h or 0 for h in hist], color=colors, alpha=0.5, width=1.0)
    ax1.plot(x, dif, color="#1f6feb", linewidth=1.0, label="DIF")
    ax1.plot(x, dea, color="#fb8500", linewidth=1.0, label="DEA")
    ax1.axhline(0, color="#999", linewidth=0.6)
    ax1.set_title("MACD（DIF／DEA／柱狀）", fontsize=11)
    ax1.legend(fontsize=7, loc="upper left")
    ax1.tick_params(labelsize=7)
    ax1.grid(True, alpha=0.2)

    # KD
    ax2.plot(x, tech.k[s], color="#1f6feb", linewidth=1.0, label="K")
    ax2.plot(x, tech.d[s], color="#cf222e", linewidth=1.0, label="D")
    ax2.axhline(80, color="#cf222e", linewidth=0.5, linestyle="--")
    ax2.axhline(20, color="#1a7f37", linewidth=0.5, linestyle="--")
    ax2.set_ylim(0, 100)
    ax2.set_title("KD 隨機指標（9）", fontsize=11)
    ax2.legend(fontsize=7, loc="upper left")
    ax2.tick_params(labelsize=7)
    ax2.grid(True, alpha=0.2)

    # RSI
    ax3.plot(x, tech.rsi[s], color="#8338ec", linewidth=1.0, label="RSI(14)")
    ax3.axhline(70, color="#cf222e", linewidth=0.5, linestyle="--")
    ax3.axhline(30, color="#1a7f37", linewidth=0.5, linestyle="--")
    ax3.set_ylim(0, 100)
    ax3.set_title("RSI 相對強弱指標（14）", fontsize=11)
    ax3.legend(fontsize=7, loc="upper left")
    ax3.tick_params(labelsize=7)
    ax3.grid(True, alpha=0.2)

    fig.autofmt_xdate()
    return _save(fig)


def eps_chart(data: EpsData) -> Optional[bytes]:
    if not data.quarterly:
        return None
    _ensure_mpl()
    import matplotlib.pyplot as plt

    pts = data.quarterly
    labels = [p.period for p in pts]
    vals = [p.eps for p in pts]
    x = range(len(pts))

    fig, ax = plt.subplots(figsize=(8, 3.4))
    colors = ["#1a7f37" if v >= 0 else "#cf222e" for v in vals]
    ax.bar(x, vals, color=colors, alpha=0.8)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:.2f}", xy=(i, v), fontsize=7, ha="center",
                    va="bottom" if v >= 0 else "top")
    ax.set_title("近季 EPS（元）", fontsize=12)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.axhline(0, color="#999", linewidth=0.6)
    ax.tick_params(labelsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    return _save(fig)
