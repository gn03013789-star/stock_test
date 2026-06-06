"""以 reportlab 組裝 PDF 投資分析報告。

七大區塊：基本資訊 → 股價 → 營收 → EPS → 新聞 → 目標價/評等 → 免責聲明。
頁尾固定顯示免責聲明。缺資料的區塊顯示「查無公開可得資料」而非略過。
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm

from ..config import DISCLAIMER
from ..core.models import Report
from . import charts, fonts

log = logging.getLogger(__name__)


def build_pdf(report: Report) -> bytes:
    """產生 PDF，回傳 bytes。"""
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        Image,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    font = fonts.register_for_reportlab()
    styles = _styles(font)
    buf = io.BytesIO()

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=2.0 * cm,
        title=f"{report.profile.company_name} 投資分析報告",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([
        PageTemplate(id="all", frames=[frame],
                     onPage=lambda c, d: _footer(c, d, font))
    ])

    story: list = []
    _section_header(story, report, styles)
    _section_basic(story, report, styles)
    _section_price(story, report, styles, Image, Spacer, Table, TableStyle)
    _section_forecast(story, report, styles, Image, Spacer)
    _section_revenue(story, report, styles, Image, Spacer)
    _section_eps(story, report, styles, Image, Spacer)
    _section_news(story, report, styles, Spacer)
    _section_rating(story, report, styles, Spacer, Table, TableStyle)
    # 美股專屬區塊
    _section_us_financials(story, report, styles, Spacer, Table, TableStyle)
    _section_earnings_call(story, report, styles, Spacer)
    _section_references(story, report, styles, Spacer)
    _section_disclaimer(story, styles, Spacer)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# 樣式
# --------------------------------------------------------------------------- #
def _styles(font: str):
    ss = getSampleStyleSheet()
    base = dict(fontName=font)
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName=font,
                                 fontSize=20, leading=26, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("st", fontName=font, fontSize=11,
                                    textColor=colors.HexColor("#57606a"),
                                    alignment=TA_CENTER, leading=16),
        "h2": ParagraphStyle("h2", fontName=font, fontSize=14, leading=20,
                             textColor=colors.HexColor("#0a3069"), spaceBefore=10,
                             spaceAfter=6),
        "body": ParagraphStyle("b", fontName=font, fontSize=10, leading=15,
                               alignment=TA_LEFT),
        "small": ParagraphStyle("s", fontName=font, fontSize=8.5, leading=12,
                                textColor=colors.HexColor("#57606a")),
        "newslink": ParagraphStyle("nl", fontName=font, fontSize=9, leading=13,
                                   textColor=colors.HexColor("#0969da")),
        "ratinghead": ParagraphStyle("rh", fontName=font, fontSize=13, leading=18,
                                     textColor=colors.white),
        "disclaimer": ParagraphStyle("d", fontName=font, fontSize=9, leading=14,
                                     textColor=colors.HexColor("#57606a"),
                                     alignment=TA_CENTER),
        "_font": font,
    }


def _footer(canvas, doc, font):
    canvas.saveState()
    canvas.setFont(font, 7.5)
    canvas.setFillColor(colors.HexColor("#8c959f"))
    canvas.drawString(1.8 * cm, 1.1 * cm, DISCLAIMER)
    canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"第 {doc.page} 頁")
    canvas.restoreState()


def _esc(text) -> str:
    s = "" if text is None else str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# 區塊
# --------------------------------------------------------------------------- #
def _section_header(story, report: Report, st):
    from reportlab.platypus import Paragraph, Spacer

    p = report.profile
    story.append(Paragraph(f"{_esc(p.company_name)} 投資分析報告", st["title"]))
    story.append(Paragraph(
        f"股票代號 {_esc(p.stock_id)}　|　{_esc(p.market_type or p.market)}　|　"
        f"報告產出：{report.generated_at:%Y-%m-%d %H:%M}",
        st["subtitle"]))
    story.append(Spacer(1, 8))


def _section_basic(story, report: Report, st):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    p = report.profile
    story.append(Paragraph("一、個股基本資訊", st["h2"]))
    rows = [
        ["公司名稱", p.company_name, "股票代號", p.stock_id],
        ["產業分類", p.industry_name or "—", "市場別", p.market_type or p.market],
        ["英文名稱", p.english_name or "—", "常見別名", "、".join(p.aliases) or "—"],
    ]
    t = Table(rows, colWidths=[2.4 * cm, 5.5 * cm, 2.4 * cm, 5.5 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), st["_font"]),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f6f8fa")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f6f8fa")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#57606a")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#57606a")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))


def _img(png: Optional[bytes], Image, width=17 * cm):
    if not png:
        return None
    bio = io.BytesIO(png)
    img = Image(bio)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width
    img.drawHeight = width * ratio
    return img


def _section_price(story, report: Report, st, Image, Spacer, Table, TableStyle):
    from reportlab.platypus import Paragraph

    story.append(Paragraph("二、股價走勢分析", st["h2"]))
    if not report.price.points:
        story.append(Paragraph("查無公開可得股價資料。", st["body"]))
        story.append(Spacer(1, 6))
        return
    story.append(Paragraph(_esc(report.price_insight), st["body"]))
    story.append(Spacer(1, 4))
    png = charts.price_chart(report.price,
                             title="近一年股價走勢（日線／週月均線／成交量）")
    img = _img(png, Image)
    if img:
        story.append(img)
    story.append(Spacer(1, 6))


def _section_forecast(story, report: Report, st, Image, Spacer):
    from reportlab.platypus import Paragraph

    fc = report.forecast
    story.append(Paragraph("三、股價預測（情境模擬）", st["h2"]))
    if fc is None or not fc.status.ok or not fc.p50:
        story.append(Paragraph("查無足夠資料進行股價情境模擬。", st["body"]))
        story.append(Spacer(1, 6))
        return
    story.append(Paragraph(_esc(report.forecast_insight), st["body"]))
    story.append(Spacer(1, 4))
    img = _img(charts.forecast_chart(report.price, fc), Image)
    if img:
        story.append(img)
    story.append(Spacer(1, 6))


def _section_revenue(story, report: Report, st, Image, Spacer):
    from reportlab.platypus import Paragraph

    title = "四、近兩年營收分析"
    if report.revenue.is_quarterly:
        title += "（美股／以季營收呈現）"
    story.append(Paragraph(title, st["h2"]))
    if not report.revenue.points:
        story.append(Paragraph("查無公開可得營收資料。", st["body"]))
        story.append(Spacer(1, 6))
        return
    story.append(Paragraph(_esc(report.revenue_insight), st["body"]))
    story.append(Spacer(1, 4))
    img = _img(charts.revenue_chart(report.revenue), Image)
    if img:
        story.append(img)
    story.append(Spacer(1, 6))


def _section_eps(story, report: Report, st, Image, Spacer):
    from reportlab.platypus import Paragraph

    story.append(Paragraph("五、EPS 分析", st["h2"]))
    if not report.eps.quarterly:
        story.append(Paragraph("查無公開可得 EPS 資料。", st["body"]))
        story.append(Spacer(1, 6))
        return
    story.append(Paragraph(_esc(report.eps_insight), st["body"]))
    story.append(Spacer(1, 4))
    img = _img(charts.eps_chart(report.eps), Image)
    if img:
        story.append(img)
    story.append(Spacer(1, 6))


def _section_news(story, report: Report, st, Spacer):
    from reportlab.platypus import Paragraph

    story.append(Paragraph("六、新聞與研究摘要", st["h2"]))
    news = report.news
    if news.used_industry_fallback:
        story.append(Paragraph(
            f"（個股新聞較少，以下含「{_esc(report.profile.industry_name)}」"
            "產業近期新聞）", st["small"]))
    if not news.items:
        story.append(Paragraph("查無公開可得新聞資料。", st["body"]))
        if news.status.errors:
            story.append(Paragraph("來源狀態：" + _esc("；".join(news.status.errors[:3])),
                                   st["small"]))
        story.append(Spacer(1, 6))
        return

    for it in news.items:
        d = f"{it.publish_date:%Y-%m-%d}" if it.publish_date else "日期不詳"
        head = f"• <b>{_esc(it.title)}</b>"
        story.append(Paragraph(head, st["body"]))
        meta = f"{_esc(it.source)}　{d}"
        if it.matched_keyword:
            meta += f"　關鍵字：{_esc(it.matched_keyword)}"
        story.append(Paragraph(meta, st["small"]))
        if it.summary_zh:
            story.append(Paragraph(f"摘要（中譯）：{_esc(it.summary_zh)}", st["small"]))
        elif it.snippet:
            story.append(Paragraph(_esc(it.snippet), st["small"]))
        if it.url:
            story.append(Paragraph(
                f'<link href="{_esc(it.url)}">{_esc(it.url)}</link>', st["newslink"]))
        story.append(Spacer(1, 4))


def _section_rating(story, report: Report, st, Spacer, Table, TableStyle):
    from reportlab.platypus import Paragraph

    # 醒目標題列
    head_tbl = Table([[Paragraph("七、目標價與投資評等", st["ratinghead"])]],
                     colWidths=[17.4 * cm])
    head_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0a3069")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(Spacer(1, 4))
    story.append(head_tbl)
    story.append(Spacer(1, 4))

    rb = report.rating
    if rb.insufficient or not rb.items:
        box = Table([[Paragraph("查無一致公開資料，僅整理公開可得資訊。", st["body"])]],
                    colWidths=[17.4 * cm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff8c5")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d4a72c")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(box)
        story.append(Spacer(1, 6))
        return

    header = ["日期", "來源/券商", "評等", "目標價", "備註"]
    rows = [header]
    for r in rb.items:
        d = f"{r.publish_date:%Y-%m-%d}" if r.publish_date else "—"
        who = r.broker or r.source or "—"
        tp = f"{r.target_price:.1f}" if r.target_price is not None else "—"
        rows.append([
            Paragraph(_esc(d), st["small"]),
            Paragraph(_esc(who), st["small"]),
            Paragraph(_esc(r.rating or "—"), st["small"]),
            Paragraph(_esc(tp), st["small"]),
            Paragraph(_esc(r.note), st["small"]),
        ])
    t = Table(rows, colWidths=[2.2 * cm, 3.2 * cm, 2.0 * cm, 1.8 * cm, 8.2 * cm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), st["_font"]),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde7f0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
    ]))
    story.append(t)
    story.append(Paragraph(
        "＊以上為公開新聞中整理之法人看法與目標價，非完整研究報告，僅供參考。",
        st["small"]))
    story.append(Spacer(1, 6))


def _section_us_financials(story, report: Report, st, Spacer, Table, TableStyle):
    from reportlab.platypus import Paragraph

    fin = report.us_financials
    if fin is None:
        return
    story.append(Paragraph("八、美股財務摘要（SEC EDGAR）", st["h2"]))
    if not fin.rows:
        story.append(Paragraph("查無公開可得 SEC 財報數據。", st["body"]))
    else:
        header = ["會計年度", "營收(百萬美元)", "淨利(百萬美元)", "稀釋EPS", "毛利率"]
        rows = [header]
        for r in fin.rows:
            rows.append([
                r.period,
                f"{r.revenue:,.0f}" if r.revenue is not None else "—",
                f"{r.net_income:,.0f}" if r.net_income is not None else "—",
                f"{r.eps:.2f}" if r.eps is not None else "—",
                f"{r.gross_margin:.1f}%" if r.gross_margin is not None else "—",
            ])
        t = Table(rows, colWidths=[3.0 * cm, 3.8 * cm, 3.8 * cm, 2.6 * cm, 2.4 * cm],
                  repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), st["_font"]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde7f0")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f6f8fa")]),
        ]))
        story.append(t)
        story.append(Paragraph(
            f"資料來源：SEC EDGAR XBRL（CIK {fin.cik}），官方公開申報。", st["small"]))

    # 近期申報連結
    if fin.filings:
        story.append(Spacer(1, 4))
        story.append(Paragraph("近期申報文件：", st["body"]))
        for f in fin.filings[:8]:
            tag = "（財報發布）" if f.is_earnings else ""
            story.append(Paragraph(
                f"• {f.date}　{_esc(f.title)}{tag}："
                f'<link href="{_esc(f.url)}">{_esc(f.url)}</link>', st["small"]))
    story.append(Spacer(1, 6))


def _section_earnings_call(story, report: Report, st, Spacer):
    from reportlab.platypus import Paragraph

    ec = report.earnings_call
    if ec is None:
        return
    story.append(Paragraph("九、法說會與電話會議", st["h2"]))
    if ec.next_date:
        story.append(Paragraph(f"下次財報／法說會預估日期：<b>{_esc(ec.next_date)}</b>",
                               st["body"]))
    if ec.press_releases:
        story.append(Paragraph("財報新聞稿（SEC 8-K，官方公開全文）：", st["body"]))
        for f in ec.press_releases:
            story.append(Paragraph(
                f"• {f.date}：<link href=\"{_esc(f.url)}\">{_esc(f.url)}</link>",
                st["small"]))
    if ec.transcript_links:
        story.append(Paragraph("電話會議逐字稿（公開新聞連結，非全文）：", st["body"]))
        for it in ec.transcript_links:
            d = f"{it.publish_date:%Y-%m-%d}" if it.publish_date else ""
            line = f"• {_esc(it.title)}　{d}"
            if it.summary_zh:
                line += f"<br/>　中譯：{_esc(it.summary_zh)}"
            line += f'<br/><link href="{_esc(it.url)}">{_esc(it.url)}</link>'
            story.append(Paragraph(line, st["small"]))
    if not (ec.next_date or ec.press_releases or ec.transcript_links):
        story.append(Paragraph("查無公開可得法說會資訊。", st["body"]))
    story.append(Spacer(1, 6))


def _section_references(story, report: Report, st, Spacer):
    from reportlab.platypus import Paragraph

    if not report.references:
        return
    story.append(Paragraph("十、延伸財報資料連結", st["h2"]))
    story.append(Paragraph(
        "以下為第三方財報網站之直達連結（資料多為付費或受版權保護，僅供導引，"
        "本報告未擷取其內容）：", st["small"]))
    for label, url in report.references:
        story.append(Paragraph(
            f'• {_esc(label)}：<link href="{_esc(url)}">{_esc(url)}</link>',
            st["small"]))
    story.append(Spacer(1, 6))


def _section_disclaimer(story, st, Spacer):
    from reportlab.platypus import Paragraph, Table, TableStyle

    story.append(Spacer(1, 10))
    box = Table([[Paragraph(DISCLAIMER, st["disclaimer"])]], colWidths=[17.4 * cm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f8fa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7de")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(box)
