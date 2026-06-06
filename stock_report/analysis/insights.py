"""由數據產生簡短中文趨勢說明（規則式，不做投資建議）。"""

from __future__ import annotations

from ..core.models import EpsData, PriceData, RevenueData


def price_insight(data: PriceData) -> str:
    pts = data.points
    if not pts:
        return "目前查無足夠股價資料以分析趨勢。"
    last = pts[-1].close
    parts = [f"最新收盤約 {last:.2f}。"]

    def _chg(days: int, label: str):
        window = data.window(days)
        if len(window) >= 2 and window[0].close:
            chg = (window[-1].close - window[0].close) / window[0].close * 100
            trend = "上漲" if chg > 0 else "下跌" if chg < 0 else "持平"
            return f"近{label}{trend} {abs(chg):.1f}%"
        return None

    seg = [s for s in (_chg(90, "3個月"), _chg(180, "6個月"), _chg(365, "1年")) if s]
    if seg:
        parts.append("，".join(seg) + "。")

    hi = max(pts, key=lambda p: p.close)
    lo = min(pts, key=lambda p: p.close)
    parts.append(
        f"一年區間高點 {hi.close:.2f}（{hi.date}），低點 {lo.close:.2f}（{lo.date}）。"
    )
    return "".join(parts)


def revenue_insight(data: RevenueData) -> str:
    pts = data.points
    if not pts:
        return "目前查無足夠營收資料以分析趨勢。"
    unit = "季營收" if data.is_quarterly else "月營收"
    latest = pts[-1]
    parts = [f"最新{unit}（{latest.label}）約 {latest.revenue:,.0f} {data.unit}。"]
    if latest.yoy is not None:
        sign = "+" if latest.yoy >= 0 else "-"
        parts.append(f"年增率 {sign}{abs(latest.yoy):.1f}%。")
    if latest.mom is not None:
        period_word = "季" if data.is_quarterly else "月"
        d = f"{period_word}增" if latest.mom >= 0 else f"{period_word}減"
        parts.append(f"較前期{d} {abs(latest.mom):.1f}%。")
    # 近期 YoY 連續方向
    yoys = [p.yoy for p in pts[-6:] if p.yoy is not None]
    if len(yoys) >= 3:
        if all(y > 0 for y in yoys):
            parts.append("近期營收年增率連續為正，動能偏多。")
        elif all(y < 0 for y in yoys):
            parts.append("近期營收年增率連續為負，需留意動能轉弱。")
    return "".join(parts)


def eps_insight(data: EpsData) -> str:
    q = data.quarterly
    if not q:
        return "目前查無足夠 EPS 資料以分析趨勢。"
    latest = q[-1]
    parts = [f"最新一季（{latest.period}）EPS 為 {latest.eps:.2f} 元。"]
    if len(q) >= 2:
        prev = q[-2]
        diff = latest.eps - prev.eps
        d = "增加" if diff > 0 else "減少" if diff < 0 else "持平"
        parts.append(f"較前一季{d} {abs(diff):.2f} 元。")
    vals = [p.eps for p in q[-4:]]
    if len(vals) >= 3:
        if all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)):
            parts.append("近幾季 EPS 呈逐季成長。")
        elif all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)):
            parts.append("近幾季 EPS 呈逐季下滑。")
    if data.annual:
        ann = "、".join(f"{a.period}:{a.eps:.2f}" for a in data.annual)
        parts.append(f"年度 EPS：{ann}。")
    return "".join(parts)
