# 台股/美股投資分析 PDF 報告產生器

輸入台股/美股**代號或名稱**，自動整合公開可得資料，產生一份**中文 PDF 投資分析報告**。

## 功能

報告含七大區塊：

1. **個股基本資訊** — 公司名稱、代號、產業、市場別、產出日期
2. **股價走勢分析** — 近一年收盤價/成交量圖、3/6/12 個月漲跌、區間高低點
3. **股價預測（情境模擬）** — 線性回歸趨勢 + 蒙地卡羅波動率錐，畫出未來約一個月的
   悲觀/中位/樂觀情境區間（**僅統計模擬，非預測、非投資建議**）
4. **近兩年營收分析** — 月營收 + MoM/YoY 圖表（美股退化為季營收）
5. **EPS 分析** — 近 8 季 EPS + 年度 EPS 圖表
6. **新聞與研究摘要** — 多來源彙整（標題/日期/來源/連結/摘要/關鍵字）
7. **目標價與投資評等** — 整理公開新聞中的法人看法、目標價、評等（醒目版面）
8. **投資免責聲明** — 固定置底

美股額外提供（台股略過）：

- **美股財務摘要（SEC EDGAR）** — 近 5 年營收/淨利/稀釋 EPS/毛利率（官方 XBRL）+ 近期 10-K/10-Q/8-K 申報連結
- **法說會與電話會議** — 下次財報日期（yfinance）、SEC 8-K 財報新聞稿官方全文連結（Item 2.02）、逐字稿公開新聞連結（不抓全文）
- **延伸財報資料連結** — Morningstar / Roic.ai / GuruFocus / SEC / Motley Fool 直達連結（不擷取其付費/版權數據）

## 設計重點

- **新聞模組多來源 + 三層 fallback**：名稱正規化 → 5 組關鍵字策略 →
  Google News RSS / 鉅亨網 provider → 個股不足時改抓同產業近 30 天新聞。
  任一來源失敗都被吞錯，不影響其他來源，全失敗也只回空結構不 crash。
- **目標價/評等不假設官方 API**：複用新聞聚合 + 規則式抽取目標價/評等/券商，
  查無一致資料時顯示「查無一致公開資料，僅整理公開可得資訊」。
- **所有資料模組皆有 fallback**，回傳 `(資料, status)`，遇 403/反爬/連線錯誤
  記錄並略過，不讓整體流程失敗。

## 資料來源（皆公開可得）

| 類別 | 主來源 | Fallback |
|------|--------|----------|
| 股價 | yfinance | TWSE `STOCK_DAY` |
| 月營收（台股） | FinMind 月營收 | TWSE OpenAPI（當期）/ yfinance 季營收 |
| EPS（台股） | FinMind 財報 | TWSE 綜合損益表 / yfinance |
| 美股基本面 | yfinance | — |
| 美股財報 / 申報 | SEC EDGAR XBRL（官方） | — |
| 美股法說會 | yfinance 日期 + SEC 8-K + 公開新聞連結 | — |
| 新聞 / 評等 | Google News RSS | 鉅亨網搜尋 API |
| 名稱正規化 | 內建對照表 | TWSE/TPEx 公開清單 / yfinance |

> 不抓取需登入、付費牆、未授權或受版權保護之研究報告全文或電話會議逐字稿全文；
> Morningstar / Roic.ai / GuruFocus 等付費/版權站僅以深層連結導引。
> SEC EDGAR 需帶可識別的 User-Agent，可用環境變數 `STOCK_REPORT_SEC_UA` 設定你的聯絡資訊。

## 安裝

```bash
pip install -r requirements.txt
```

> 首次產生報告時會自動準備中文字型：Windows 直接使用內建微軟正黑體
> （`C:\Windows\Fonts\msjh.ttc`）；其他平台自動下載 Noto Sans TC。

## 使用方式

### 網頁介面（推薦）

```bash
streamlit run app.py
```

操作流程：

1. 選擇市場（**台股 / 美股**）。
2. 從「**市值前百大**」清單直接挑選，或自行輸入任意代號／名稱。
3. 線上即時**預覽**報告：分頁顯示股價、營收、EPS 圖表與新聞、目標價/評等。
4. 需要時再點右上角「**⬇️ 下載 PDF**」取得完整報告（與預覽內容一致）。

> 市值前百大為約略排序的定期快照（避免依賴易失效的即時排名爬蟲），
> 清單見 `stock_report/core/universe.py`，可自行增修。

> **部署到手機可用的網路版**：見 [DEPLOY.md](DEPLOY.md)（Streamlit Community Cloud，
> 免費、含密碼保護、行動版介面）。設定環境變數/Secrets `APP_PASSWORD` 即啟用密碼門。

### 命令列

```bash
python cli.py 2330            # 台積電
python cli.py 台積電           # 以名稱查詢
python cli.py AAPL            # 美股
python cli.py 2317 -o D:\out  # 指定輸出資料夾
python cli.py 2330 -v         # 顯示詳細日誌
```

PDF 預設輸出至 `./output/`。

## 測試

```bash
python -m unittest tests.test_resilience -v
```

測試涵蓋：名稱正規化、新聞來源失敗隔離、評等查無資料的處理、空資料仍能產生 PDF。

## 專案結構

```
stock_report/
├── core/         # 資料模型 + 名稱正規化 + 台股對照表
├── datasources/  # price / revenue / eps / finmind / news/ / rating
├── analysis/     # 規則式中文趨勢說明
├── report/       # 字型 / 圖表 / PDF 組裝
├── utils/        # HTTP session（容錯）+ 檔案快取
└── pipeline.py   # 端到端流程
app.py            # Streamlit 入口
cli.py            # CLI 入口
```

## 免責聲明

所有投資相關內容僅供參考，不構成任何投資建議，使用者應自行評估風險。
