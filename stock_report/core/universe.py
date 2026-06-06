"""台股 / 美股市值前百大股票清單（約略排序的定期快照）。

說明：市值排名會隨股價變動，這裡採用「定期更新的靜態快照」以確保清單載入
快速且穩定（不依賴易失效的即時排名爬蟲）。順序大致依市值由大到小。
使用者仍可在介面自由輸入任意代號/名稱，不受此清單限制。
"""

from __future__ import annotations

from typing import List, Tuple

# 每筆：(代號, 顯示名稱)
TW_TOP100: List[Tuple[str, str]] = [
    ("2330", "台積電"), ("2317", "鴻海"), ("2454", "聯發科"), ("2308", "台達電"),
    ("2412", "中華電"), ("2382", "廣達"), ("2891", "中信金"), ("2881", "富邦金"),
    ("2882", "國泰金"), ("3711", "日月光投控"), ("2303", "聯電"), ("2886", "兆豐金"),
    ("2884", "玉山金"), ("1216", "統一"), ("2357", "華碩"), ("3045", "台灣大"),
    ("2002", "中鋼"), ("2885", "元大金"), ("2892", "第一金"), ("5880", "合庫金"),
    ("2880", "華南金"), ("2883", "開發金"), ("2887", "台新金"), ("1303", "南亞"),
    ("1301", "台塑"), ("2207", "和泰車"), ("3008", "大立光"), ("2379", "瑞昱"),
    ("2603", "長榮"), ("4904", "遠傳"), ("2912", "統一超"), ("5871", "中租-KY"),
    ("3034", "聯詠"), ("6505", "台塑化"), ("1326", "台化"), ("2890", "永豐金"),
    ("2327", "國巨"), ("2345", "智邦"), ("3231", "緯創"), ("2376", "技嘉"),
    ("4938", "和碩"), ("6669", "緯穎"), ("3037", "欣興"), ("2356", "英業達"),
    ("2409", "友達"), ("3661", "世芯-KY"), ("3443", "創意"), ("2474", "可成"),
    ("1101", "台泥"), ("2105", "正新"), ("9910", "豐泰"), ("1402", "遠東新"),
    ("2301", "光寶科"), ("2324", "仁寶"), ("6415", "矽力-KY"), ("8046", "南電"),
    ("4958", "臻鼎-KY"), ("2408", "南亞科"), ("3017", "奇鋐"), ("2360", "致茂"),
    ("2383", "台光電"), ("6488", "環球晶"), ("5483", "中美晶"), ("8299", "群聯"),
    ("2618", "長榮航"), ("2610", "華航"), ("2609", "陽明"), ("2615", "萬海"),
    ("1102", "亞泥"), ("1605", "華新"), ("2027", "大成鋼"), ("2059", "川湖"),
    ("9904", "寶成"), ("2353", "宏碁"), ("2377", "微星"), ("2347", "聯強"),
    ("3702", "大聯大"), ("2395", "研華"), ("3035", "智原"), ("3529", "力旺"),
    ("6531", "愛普-KY"), ("8069", "元太"), ("2049", "上銀"), ("1519", "華城"),
    ("1513", "中興電"), ("1503", "士電"), ("2371", "大同"), ("6446", "藥華藥"),
    ("2812", "台中銀"), ("2801", "彰銀"), ("5876", "上海商銀"), ("2823", "中壽"),
    ("9921", "巨大"), ("9941", "裕融"), ("2542", "興富發"), ("1476", "儒鴻"),
    ("1477", "聚陽"), ("3596", "智易"), ("6239", "力成"), ("3533", "嘉澤"),
    ("3653", "健策"), ("6770", "力積電"), ("4763", "材料-KY"),
]

US_TOP100: List[Tuple[str, str]] = [
    ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"), ("GOOGL", "Alphabet"),
    ("AMZN", "Amazon"), ("META", "Meta Platforms"), ("AVGO", "Broadcom"), ("TSLA", "Tesla"),
    ("BRK-B", "Berkshire Hathaway"), ("LLY", "Eli Lilly"), ("JPM", "JPMorgan Chase"),
    ("V", "Visa"), ("WMT", "Walmart"), ("UNH", "UnitedHealth"), ("XOM", "Exxon Mobil"),
    ("MA", "Mastercard"), ("ORCL", "Oracle"), ("COST", "Costco"), ("HD", "Home Depot"),
    ("PG", "Procter & Gamble"), ("JNJ", "Johnson & Johnson"), ("NFLX", "Netflix"),
    ("BAC", "Bank of America"), ("ABBV", "AbbVie"), ("KO", "Coca-Cola"),
    ("CRM", "Salesforce"), ("CVX", "Chevron"), ("MRK", "Merck"), ("AMD", "AMD"),
    ("PEP", "PepsiCo"), ("TMO", "Thermo Fisher"), ("LIN", "Linde"), ("ADBE", "Adobe"),
    ("WFC", "Wells Fargo"), ("CSCO", "Cisco"), ("ACN", "Accenture"), ("MCD", "McDonald's"),
    ("ABT", "Abbott"), ("DHR", "Danaher"), ("GE", "GE Aerospace"),
    ("TXN", "Texas Instruments"), ("QCOM", "Qualcomm"), ("DIS", "Disney"),
    ("INTU", "Intuit"), ("AMAT", "Applied Materials"), ("VZ", "Verizon"), ("IBM", "IBM"),
    ("CAT", "Caterpillar"), ("PFE", "Pfizer"), ("AXP", "American Express"),
    ("NOW", "ServiceNow"), ("GS", "Goldman Sachs"), ("MS", "Morgan Stanley"),
    ("ISRG", "Intuitive Surgical"), ("CMCSA", "Comcast"), ("RTX", "RTX"),
    ("NEE", "NextEra Energy"), ("UBER", "Uber"), ("HON", "Honeywell"), ("T", "AT&T"),
    ("SPGI", "S&P Global"), ("PGR", "Progressive"), ("LOW", "Lowe's"),
    ("BKNG", "Booking"), ("ELV", "Elevance Health"), ("TJX", "TJX"),
    ("BLK", "BlackRock"), ("SYK", "Stryker"), ("VRTX", "Vertex"), ("C", "Citigroup"),
    ("BSX", "Boston Scientific"), ("MDT", "Medtronic"), ("ADP", "ADP"), ("MU", "Micron"),
    ("GILD", "Gilead"), ("LRCX", "Lam Research"), ("CB", "Chubb"), ("PLD", "Prologis"),
    ("MMC", "Marsh & McLennan"), ("DE", "Deere"), ("SBUX", "Starbucks"),
    ("KLAC", "KLA"), ("REGN", "Regeneron"), ("PANW", "Palo Alto Networks"),
    ("SCHW", "Charles Schwab"), ("ETN", "Eaton"), ("BA", "Boeing"),
    ("ADI", "Analog Devices"), ("BMY", "Bristol-Myers Squibb"), ("AMT", "American Tower"),
    ("CI", "Cigna"), ("SO", "Southern Company"), ("MO", "Altria"), ("DUK", "Duke Energy"),
    ("CME", "CME Group"), ("ANET", "Arista Networks"), ("MDLZ", "Mondelez"),
    ("INTC", "Intel"), ("GD", "General Dynamics"), ("SHW", "Sherwin-Williams"),
]


def top100(market: str) -> List[Tuple[str, str]]:
    lst = US_TOP100 if market.upper() == "US" else TW_TOP100
    return lst[:100]
