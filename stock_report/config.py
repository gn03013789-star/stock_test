"""全域設定：路徑、逾時、User-Agent、字型來源等常數。"""

from __future__ import annotations

import os
from pathlib import Path

# --- 專案路徑 ---
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent

# 快取與輸出目錄（放在使用者家目錄底下，避免污染專案）
CACHE_DIR = Path(os.environ.get("STOCK_REPORT_CACHE", PROJECT_DIR / ".cache"))
FONT_CACHE_DIR = CACHE_DIR / "fonts"
HTTP_CACHE_DIR = CACHE_DIR / "http"
OUTPUT_DIR = Path(os.environ.get("STOCK_REPORT_OUTPUT", PROJECT_DIR / "output"))

for _d in (CACHE_DIR, FONT_CACHE_DIR, HTTP_CACHE_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- HTTP ---
HTTP_TIMEOUT = float(os.environ.get("STOCK_REPORT_HTTP_TIMEOUT", "12"))
HTTP_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# HTTP 快取存活時間（秒）。預設 6 小時，減少重複請求。
HTTP_CACHE_TTL = int(os.environ.get("STOCK_REPORT_HTTP_TTL", str(6 * 3600)))

# --- 中文字型 ---
# Noto Sans TC（思源黑體）Google Fonts 開源可商用。
# 注意：reportlab 不支援 CFF/PostScript outline 的 OTF，故使用 glyf outline 的
# 可變 TTF（NotoSansTC[wght].ttf）作為跨平台下載來源。
NOTO_SANS_TC_URL = (
    "https://github.com/google/fonts/raw/main/ofl/notosanstc/"
    "NotoSansTC%5Bwght%5D.ttf"
)
NOTO_SANS_TC_FILENAME = "NotoSansTC-VF.ttf"
# Windows 內建微軟正黑體（TrueType，可被 reportlab 直接使用）。
# 在 Windows 上優先採用，免下載且穩定。
WINDOWS_FONT_FALLBACK = Path(r"C:\Windows\Fonts\msjh.ttc")

# --- SEC EDGAR ---
# SEC 要求帶可識別的 User-Agent（含聯絡方式），否則可能被限制。
# 可用環境變數 STOCK_REPORT_SEC_UA 覆寫成你自己的聯絡資訊。
SEC_USER_AGENT = os.environ.get(
    "STOCK_REPORT_SEC_UA",
    "StockReportTool/0.1 (research; contact: user@example.com)",
)

# --- 翻譯 ---
# 是否將英文新聞翻為繁中摘要（免金鑰，透過 deep-translator）。
ENABLE_TRANSLATION = os.environ.get("STOCK_REPORT_TRANSLATE", "1") != "0"

# --- 報告 ---
DISCLAIMER = "所有投資相關內容僅供參考，不構成任何投資建議，使用者應自行評估風險。"
NEWS_MAX_ITEMS = 12          # 新聞區塊最多顯示幾則
NEWS_LOOKBACK_DAYS = 30      # 同產業 fallback 的回看天數
RATING_MAX_ITEMS = 10        # 目標價/評等最多顯示幾則
