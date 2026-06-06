# 部署到 Streamlit Community Cloud（手機可用）

把這個 App 部署到網路上，戶外用手機瀏覽器即可開啟。免費、無需自架伺服器。

## 一、前置作業

1. 註冊 [GitHub](https://github.com) 與 [Streamlit Community Cloud](https://share.streamlit.io)（用 GitHub 登入）。
2. 確認專案含以下檔案（已備妥）：
   - `app.py`（主程式）
   - `requirements.txt`（Python 套件）
   - `packages.txt`（系統字型 `fonts-noto-cjk`，確保中文顯示）
   - `.streamlit/config.toml`（主題與伺服器設定）
   - `stock_report/`（套件原始碼）

> ⚠️ 千萬不要把 `.streamlit/secrets.toml` 提交到 GitHub（已列入 `.gitignore`）。

## 二、推上 GitHub

在專案資料夾（`D:\code\股票`）執行：

```bash
git init
git add .
git commit -m "台股/美股投資分析報告產生器"
git branch -M main
git remote add origin https://github.com/<你的帳號>/stock-report.git
git push -u origin main
```

（先在 GitHub 建一個空的 repository，例如 `stock-report`。）

## 三、在 Streamlit Cloud 部署

1. 進入 <https://share.streamlit.io> →「**Create app**」→「Deploy a public app from GitHub」。
2. 選擇你的 repo、branch `main`、Main file path 填 `app.py`。
3.（建議）展開「**Advanced settings**」把 **Python version** 選 **3.11**。
4. 在「**Secrets**」欄貼上（啟用密碼保護）：

   ```toml
   APP_PASSWORD = "你的密碼"
   # 可選：STOCK_REPORT_SEC_UA = "YourName research you@example.com"
   ```

5. 按「**Deploy**」。第一次建置約數分鐘（安裝套件 + 首次下載中文字型）。
6. 完成後會得到網址，例如 `https://你的app.streamlit.app`。手機瀏覽器打開、輸入密碼即可使用。

## 四、手機使用建議

- 在手機瀏覽器開啟網址後，可「**加入主畫面**」，像 App 一樣從桌面啟動。
- 介面已為手機優化（單欄置中、全寬按鈕、圖表自適應、分頁切換）。

## 五、更新版本

改完程式後重新 push 即可，Streamlit Cloud 會自動重新部署：

```bash
git add .
git commit -m "更新內容"
git push
```

## 六、常見問題

- **中文變方框**：確認 `packages.txt` 含 `fonts-noto-cjk`；本程式另會自動下載 Noto Sans TC 作為後備。
- **忘記密碼 / 想關閉密碼**：到 App 的 Settings → Secrets 修改或移除 `APP_PASSWORD`（移除即變公開）。
- **資源限制**：免費方案約 1GB RAM，本工具足夠；若同時多人使用較慢屬正常。
- **首次查詢較慢**：容器啟動後第一次會下載字型與抓資料，之後有快取會較快。

---

本工具所有投資相關內容僅供參考，不構成任何投資建議，使用者應自行評估風險。
