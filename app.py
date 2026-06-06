"""Streamlit 入口：streamlit run app.py

功能：
- 選擇市場（台股/美股）並從「市值前百大」清單挑選，或自行輸入代號/名稱。
- 線上即時預覽報告內容（基本資訊、股價/營收/EPS 圖表、新聞、目標價評等）。
- 可選擇下載完整 PDF（與預覽內容一致）。
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import streamlit as st

from stock_report.analysis import forecast as forecast_mod
from stock_report.config import DISCLAIMER
from stock_report.core.universe import top100
from stock_report.pipeline import build_report
from stock_report.report import charts
from stock_report.report.pdf_builder import build_pdf

HORIZON_OPTIONS = forecast_mod.HORIZON_OPTIONS  # {"1 週":5, ..., "3 個月":60}
DEFAULT_HORIZON_LABEL = "1 個月"


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "report"


# layout="centered" 對手機較友善（內容置中、單欄、易讀）
st.set_page_config(page_title="台股/美股投資分析報告", page_icon="📈",
                   layout="centered", initial_sidebar_state="collapsed")


# --------------------------------------------------------------------------- #
# 密碼保護（部署用）
#   - 在 Streamlit Cloud 的 Secrets 或環境變數設定 APP_PASSWORD 即啟用。
#   - 未設定時（本機開發）自動放行。
# --------------------------------------------------------------------------- #
def _configured_password() -> str:
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:  # noqa: BLE001  無 secrets.toml 時
        pass
    return os.environ.get("APP_PASSWORD", "")


def check_password() -> bool:
    pw_required = _configured_password()
    if not pw_required:
        return True  # 未設定密碼 -> 放行（本機開發）
    if st.session_state.get("auth_ok"):
        return True

    def _verify():
        if st.session_state.get("pw_input", "") == pw_required:
            st.session_state["auth_ok"] = True
            st.session_state.pop("pw_input", None)
        else:
            st.session_state["auth_ok"] = False

    st.title("🔒 請輸入存取密碼")
    st.text_input("密碼", type="password", key="pw_input", on_change=_verify)
    if st.session_state.get("auth_ok") is False:
        st.error("密碼錯誤，請再試一次。")
    return False


if not check_password():
    st.stop()


st.title("📈 台股/美股投資分析報告產生器")
st.caption("選擇市場與標的，線上即時預覽分析報告，或下載完整 PDF。")

# --------------------------------------------------------------------------- #
# 查詢區（不使用 st.form，讓市場切換即時連動右側清單）
# --------------------------------------------------------------------------- #
col1, col2 = st.columns([1, 3])
with col1:
    # 切換市場時清掉上一檔的殘留結果，避免顯示舊報告
    market_label = st.radio("市場", ["台股", "美股"], horizontal=False,
                            key="market_label")
    if st.session_state.get("_last_market") != market_label:
        st.session_state["_last_market"] = market_label
        st.session_state.pop("report", None)
        st.session_state.pop("pdf", None)

market = "US" if market_label == "美股" else "TW"
universe = top100(market)
PLACEHOLDER = "（不指定，使用下方輸入）"
options = [PLACEHOLDER] + [f"{sid}　{name}" for sid, name in universe]

with col2:
    picked = st.selectbox(
        f"{market_label}市值前百大（約略排序快照，可直接選取）", options,
        key=f"picked_{market}",   # 依市場用不同 key，切換時自動重置選項
    )
    manual = st.text_input(
        "或自行輸入代號／名稱", placeholder="例如：2330、台積電、AAPL"
    )

submitted = st.button("產生報告", type="primary")

# 決定查詢字串：自行輸入優先，其次下拉選取
query = ""
if submitted:
    # 每次重新搜尋先清掉上一份結果，避免殘留訊息
    st.session_state.pop("report", None)
    st.session_state.pop("pdf", None)
    if manual.strip():
        query = manual.strip()
    elif picked != PLACEHOLDER:
        query = picked.split("　")[0].strip()
    else:
        st.warning("請從清單選取一檔，或自行輸入代號／名稱。")


# --------------------------------------------------------------------------- #
# 產生報告（存入 session_state 供預覽與下載共用，避免重複計算）
# --------------------------------------------------------------------------- #
if query:
    progress_holder = st.empty()
    status = st.empty()
    with progress_holder.container():
        progress_bar = st.progress(0.0)

    def progress(msg, frac):
        progress_bar.progress(min(1.0, frac))
        status.write(f"⏳ {msg}")

    try:
        # 沿用使用者上次選的預測期間（預設 1 個月）
        h_days0 = HORIZON_OPTIONS.get(
            st.session_state.get("fc_horizon", DEFAULT_HORIZON_LABEL), 20)
        report = build_report(query, progress=progress, forecast_days=h_days0)
        pdf = build_pdf(report)
    except Exception as e:  # noqa: BLE001  最終防線
        progress_holder.empty()
        status.empty()
        st.error(f"產生報告時發生未預期錯誤：{e}")
    else:
        progress_holder.empty()
        status.empty()
        st.session_state["report"] = report
        st.session_state["pdf"] = pdf
        # 記錄目前 PDF/預測對應的預測天數（預設 20=1 個月）
        st.session_state["fc_days_applied"] = (
            report.forecast.horizon_days if report.forecast else 20
        )


# --------------------------------------------------------------------------- #
# 預覽
# --------------------------------------------------------------------------- #
def render_preview(report, pdf):
    p = report.profile

    # 若使用者在「預測」分頁改了預測期間，先在這裡重算預測並重建 PDF，
    # 確保下載的 PDF 與畫面顯示一致（重算僅用既有股價資料，不重新抓網路）。
    h_label = st.session_state.get("fc_horizon", DEFAULT_HORIZON_LABEL)
    h_days = HORIZON_OPTIONS.get(h_label, 20)
    if report.price.points and st.session_state.get("fc_days_applied") != h_days:
        new_fc = forecast_mod.forecast(report.price, horizon_days=h_days)
        report.forecast = new_fc
        report.forecast_insight = forecast_mod.insight(new_fc, p.currency)
        pdf = build_pdf(report)
        st.session_state["report"] = report
        st.session_state["pdf"] = pdf
        st.session_state["fc_days_applied"] = h_days

    # 下載鈕（置頂，方便取用）
    fname = (
        f"{_safe_filename(p.company_name)}_投資分析報告_"
        f"{report.generated_at:%Y%m%d}.pdf"
    )
    st.subheader(f"{p.company_name}（{p.stock_id}）")
    st.caption(
        f"{p.market_type or p.market}　|　產業：{p.industry_name or '—'}"
        f"　|　報告產出：{report.generated_at:%Y-%m-%d %H:%M}"
    )
    # 全寬下載鈕（手機好按）
    st.download_button("⬇️ 下載完整 PDF 報告", data=pdf, file_name=fname,
                       mime="application/pdf", type="primary",
                       use_container_width=True)

    # 摘要狀態（手機上自動換行堆疊）
    m = st.columns(3)
    m[0].metric("股價", "OK" if report.price.points else "—")
    m[1].metric("營收", "OK" if report.revenue.points else "—")
    m[2].metric("EPS", "OK" if report.eps.quarterly else "—")
    m2 = st.columns(2)
    m2[0].metric("新聞", f"{len(report.news.items)} 則")
    m2[1].metric("評等", f"{len(report.rating.items)} 則")

    labels = ["📊 股價", "🔮 預測", "💰 營收", "📈 EPS", "📰 新聞", "🎯 目標價/評等"]
    is_us = report.us_financials is not None
    if is_us:
        labels += ["🏦 財務摘要(SEC)", "📞 法說會", "🔗 延伸連結"]
    tabs = st.tabs(labels)

    # 股價
    with tabs[0]:
        if report.price.points:
            st.info(report.price_insight)
            png = charts.price_chart(report.price, title="近一年股價走勢（收盤價／成交量）")
            if png:
                st.image(png, use_container_width=True)
        else:
            st.warning("查無公開可得股價資料。")

    # 預測（情境模擬）
    with tabs[1]:
        # 預測期間選擇（改變時觸發 rerun，會在 render_preview 頂端重算）
        st.radio("預測期間", list(HORIZON_OPTIONS.keys()),
                 index=list(HORIZON_OPTIONS.keys()).index(DEFAULT_HORIZON_LABEL),
                 key="fc_horizon", horizontal=True)
        fc = report.forecast
        if fc is not None and fc.status.ok and fc.p50:
            st.warning("⚠️ 以下為基於歷史資料的統計模擬，非預測也非投資建議。")
            st.info(report.forecast_insight)
            png = charts.forecast_chart(report.price, fc)
            if png:
                st.image(png, use_container_width=True)
            c = st.columns(3)
            c[0].metric("悲觀情境(P10)", f"{fc.p10[-1]:.1f}")
            c[1].metric("中位情境(P50)", f"{fc.p50[-1]:.1f}",
                        delta=f"{(fc.p50[-1]-fc.last_price)/fc.last_price*100:+.1f}%")
            c[2].metric("樂觀情境(P90)", f"{fc.p90[-1]:.1f}")
        else:
            st.warning("查無足夠資料進行股價情境模擬。")

    # 營收
    with tabs[2]:
        if report.revenue.points:
            if report.revenue.is_quarterly:
                st.caption("（美股以季營收呈現）")
            st.info(report.revenue_insight)
            png = charts.revenue_chart(report.revenue)
            if png:
                st.image(png, use_container_width=True)
        else:
            st.warning("查無公開可得營收資料。")

    # EPS
    with tabs[3]:
        if report.eps.quarterly:
            st.info(report.eps_insight)
            png = charts.eps_chart(report.eps)
            if png:
                st.image(png, use_container_width=True)
        else:
            st.warning("查無公開可得 EPS 資料。")

    # 新聞
    with tabs[4]:
        news = report.news
        if news.used_industry_fallback:
            st.caption(f"個股新聞較少，已補入「{p.industry_name}」產業近期新聞。")
        if news.items:
            for it in news.items:
                d = f"{it.publish_date:%Y-%m-%d}" if it.publish_date else "日期不詳"
                st.markdown(f"**[{it.title}]({it.url})**" if it.url else f"**{it.title}**")
                meta = f"{it.source}　{d}"
                if it.matched_keyword:
                    meta += f"　·　關鍵字：{it.matched_keyword}"
                st.caption(meta)
                if it.summary_zh:
                    st.write(f"📝 摘要（中譯）：{it.summary_zh}")
                    if it.snippet:
                        st.caption(f"原文：{it.snippet}")
                elif it.snippet:
                    st.write(it.snippet)
                st.divider()
        else:
            st.warning("查無公開可得新聞資料。")

    # 目標價/評等
    with tabs[5]:
        rb = report.rating
        if rb.insufficient or not rb.items:
            st.warning("查無一致公開資料，僅整理公開可得資訊。")
        else:
            rows = []
            for r in rb.items:
                rows.append({
                    "日期": f"{r.publish_date:%Y-%m-%d}" if r.publish_date else "—",
                    "來源/券商": r.broker or r.source or "—",
                    "評等": r.rating or "—",
                    "目標價": f"{r.target_price:.1f}" if r.target_price is not None else "—",
                    "備註": r.note,
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption("＊以上為公開新聞整理之法人看法與目標價，非完整研究報告，僅供參考。")

    # ---- 美股專屬分頁 ----
    if is_us:
        # 財務摘要 (SEC)
        with tabs[6]:
            fin = report.us_financials
            if fin.rows:
                frows = [{
                    "會計年度": r.period,
                    "營收(百萬USD)": f"{r.revenue:,.0f}" if r.revenue is not None else "—",
                    "淨利(百萬USD)": f"{r.net_income:,.0f}" if r.net_income is not None else "—",
                    "稀釋EPS": f"{r.eps:.2f}" if r.eps is not None else "—",
                    "毛利率": f"{r.gross_margin:.1f}%" if r.gross_margin is not None else "—",
                } for r in fin.rows]
                st.dataframe(frows, use_container_width=True, hide_index=True)
                st.caption(f"資料來源：SEC EDGAR XBRL（CIK {fin.cik}），官方公開申報。")
            else:
                st.warning("查無公開可得 SEC 財報數據。")
            if fin.filings:
                st.markdown("**近期申報文件**")
                for f in fin.filings[:8]:
                    tag = "（財報發布）" if f.is_earnings else ""
                    st.markdown(f"- {f.date}　[{f.title}{tag}]({f.url})")

        # 法說會
        with tabs[7]:
            ec = report.earnings_call
            if ec.next_date:
                st.metric("下次財報／法說會預估日期", ec.next_date)
            if ec.press_releases:
                st.markdown("**財報新聞稿（SEC 8-K，官方公開全文）**")
                for f in ec.press_releases:
                    st.markdown(f"- {f.date}：[{f.url}]({f.url})")
            if ec.transcript_links:
                st.markdown("**電話會議逐字稿（公開新聞連結，非全文）**")
                for it in ec.transcript_links:
                    d = f"{it.publish_date:%Y-%m-%d}" if it.publish_date else ""
                    st.markdown(f"- [{it.title}]({it.url})　_{it.source}　{d}_")
                    if it.summary_zh:
                        st.caption(f"　中譯：{it.summary_zh}")
            if not (ec.next_date or ec.press_releases or ec.transcript_links):
                st.warning("查無公開可得法說會資訊。")

        # 延伸連結
        with tabs[8]:
            st.caption("第三方財報網站直達連結（資料多為付費或受版權保護，僅供導引，"
                       "本報告未擷取其內容）。")
            for label, url in report.references:
                st.markdown(f"- **{label}**：[{url}]({url})")


if "report" in st.session_state:
    render_preview(st.session_state["report"], st.session_state["pdf"])

st.divider()
st.caption(DISCLAIMER)
