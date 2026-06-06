"""以 matplotlib 產生圖表 PNG（股價 / 營收 / EPS）。

所有函式回傳 PNG bytes 或 None（無資料）。皆設定中文字型。
"""

from __future__ import annotations

import io
import logging
from typing import List, Optional

from ..core.models import EpsData, ForecastResult, PriceData, RevenueData
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


def price_chart(data: PriceData, title: str = "股價走勢") -> Optional[bytes]:
    if not data.points:
        return None
    _ensure_mpl()
    import matplotlib.pyplot as plt

    pts = data.points
    dates = [p.date for p in pts]
    closes = [p.close for p in pts]

    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(dates, closes, color="#1f6feb", linewidth=1.3, label="收盤價")

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
