"""內建台股對照表 + 動態查詢 fallback。

對照表涵蓋常見/權值標的，提供代號、中文名、別名、產業、市場別。
找不到時由 normalizer 走 TWSE 清單 / yfinance 動態補齊。
"""

from __future__ import annotations

from typing import Dict, List, Optional

# 欄位：stock_id -> dict(name, aliases, english, industry, market)
# market: 上市 / 上櫃
_TW_STOCKS: Dict[str, dict] = {
    "2330": dict(name="台積電", aliases=["台積", "TSMC"], english="Taiwan Semiconductor",
                 industry="半導體", market="上市"),
    "2317": dict(name="鴻海", aliases=["鴻海精密", "Hon Hai", "Foxconn"], english="Hon Hai Precision",
                 industry="電子代工", market="上市"),
    "2454": dict(name="聯發科", aliases=["MediaTek", "聯發"], english="MediaTek",
                 industry="半導體", market="上市"),
    "2308": dict(name="台達電", aliases=["台達", "Delta"], english="Delta Electronics",
                 industry="電子零組件", market="上市"),
    "2303": dict(name="聯電", aliases=["UMC"], english="United Microelectronics",
                 industry="半導體", market="上市"),
    "2412": dict(name="中華電", aliases=["中華電信", "Chunghwa Telecom"], english="Chunghwa Telecom",
                 industry="電信", market="上市"),
    "2882": dict(name="國泰金", aliases=["國泰金控", "Cathay"], english="Cathay Financial",
                 industry="金融", market="上市"),
    "2881": dict(name="富邦金", aliases=["富邦金控", "Fubon"], english="Fubon Financial",
                 industry="金融", market="上市"),
    "2886": dict(name="兆豐金", aliases=["兆豐金控", "Mega"], english="Mega Financial",
                 industry="金融", market="上市"),
    "2891": dict(name="中信金", aliases=["中信金控", "CTBC"], english="CTBC Financial",
                 industry="金融", market="上市"),
    "2002": dict(name="中鋼", aliases=["中國鋼鐵", "China Steel"], english="China Steel",
                 industry="鋼鐵", market="上市"),
    "1301": dict(name="台塑", aliases=["台灣塑膠", "Formosa Plastics"], english="Formosa Plastics",
                 industry="塑膠", market="上市"),
    "1303": dict(name="南亞", aliases=["南亞塑膠", "Nan Ya"], english="Nan Ya Plastics",
                 industry="塑膠", market="上市"),
    "2603": dict(name="長榮", aliases=["長榮海運", "Evergreen"], english="Evergreen Marine",
                 industry="航運", market="上市"),
    "2609": dict(name="陽明", aliases=["陽明海運", "Yang Ming"], english="Yang Ming Marine",
                 industry="航運", market="上市"),
    "2615": dict(name="萬海", aliases=["萬海航運", "Wan Hai"], english="Wan Hai Lines",
                 industry="航運", market="上市"),
    "2357": dict(name="華碩", aliases=["ASUS", "華碩電腦"], english="ASUSTeK Computer",
                 industry="電腦及週邊", market="上市"),
    "2382": dict(name="廣達", aliases=["Quanta", "廣達電腦"], english="Quanta Computer",
                 industry="電腦及週邊", market="上市"),
    "2376": dict(name="技嘉", aliases=["Gigabyte"], english="Gigabyte Technology",
                 industry="電腦及週邊", market="上市"),
    "3008": dict(name="大立光", aliases=["Largan", "大立光電"], english="Largan Precision",
                 industry="光學", market="上市"),
    "2379": dict(name="瑞昱", aliases=["Realtek"], english="Realtek Semiconductor",
                 industry="半導體", market="上市"),
    "3034": dict(name="聯詠", aliases=["Novatek"], english="Novatek Microelectronics",
                 industry="半導體", market="上市"),
    "3037": dict(name="欣興", aliases=["Unimicron", "欣興電子"], english="Unimicron Technology",
                 industry="電子零組件", market="上市"),
    "3661": dict(name="世芯", aliases=["世芯-KY", "Alchip"], english="Alchip Technologies",
                 industry="半導體", market="上市"),
    "3443": dict(name="創意", aliases=["創意電子", "GUC"], english="Global Unichip",
                 industry="半導體", market="上市"),
    "2356": dict(name="英業達", aliases=["Inventec"], english="Inventec",
                 industry="電子代工", market="上市"),
    "2353": dict(name="宏碁", aliases=["Acer"], english="Acer",
                 industry="電腦及週邊", market="上市"),
    "2474": dict(name="可成", aliases=["Catcher"], english="Catcher Technology",
                 industry="電子零組件", market="上市"),
    "1101": dict(name="台泥", aliases=["台灣水泥", "TCC"], english="Taiwan Cement",
                 industry="水泥", market="上市"),
    "1216": dict(name="統一", aliases=["統一企業", "Uni-President"], english="Uni-President",
                 industry="食品", market="上市"),
    "2912": dict(name="統一超", aliases=["統一超商", "7-11", "President Chain"],
                 english="President Chain Store", industry="零售", market="上市"),
    "2884": dict(name="玉山金", aliases=["玉山金控", "E.Sun"], english="E.Sun Financial",
                 industry="金融", market="上市"),
    "5880": dict(name="合庫金", aliases=["合作金庫金控"], english="Taiwan Cooperative Financial",
                 industry="金融", market="上市"),
    "2207": dict(name="和泰車", aliases=["和泰汽車", "Hotai"], english="Hotai Motor",
                 industry="汽車", market="上市"),
    "6505": dict(name="台塑化", aliases=["台塑石化", "Formosa Petrochemical"],
                 english="Formosa Petrochemical", industry="石化", market="上市"),
    "3045": dict(name="台灣大", aliases=["台灣大哥大", "Taiwan Mobile"], english="Taiwan Mobile",
                 industry="電信", market="上市"),
    "4904": dict(name="遠傳", aliases=["遠傳電信", "FET"], english="Far EasTone",
                 industry="電信", market="上市"),
    "6446": dict(name="藥華藥", aliases=["藥華醫藥", "PharmaEssentia"], english="PharmaEssentia",
                 industry="生技醫療", market="上市"),
    "1519": dict(name="華城", aliases=["華城電機"], english="Fortune Electric",
                 industry="重電", market="上市"),
    "1513": dict(name="中興電", aliases=["中興電工"], english="CHINA ENGINE",
                 industry="重電", market="上市"),
    # 上櫃示例
    "6488": dict(name="環球晶", aliases=["環球晶圓", "GlobalWafers"], english="GlobalWafers",
                 industry="半導體", market="上櫃"),
    "5483": dict(name="中美晶", aliases=["SAS"], english="Sino-American Silicon",
                 industry="半導體", market="上櫃"),
    "8299": dict(name="群聯", aliases=["群聯電子", "Phison"], english="Phison Electronics",
                 industry="半導體", market="上櫃"),
    "6510": dict(name="精測", aliases=["中華精測"], english="Chunghwa Precision Test",
                 industry="半導體", market="上櫃"),
}


# TWSE 上市產業別代碼 -> 名稱（公開資訊觀測站 t187ap03_L 的「產業別」常為代碼）
_TW_INDUSTRY_CODES = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維", "05": "電機機械",
    "06": "電器電纜", "07": "化學生技醫療", "08": "玻璃陶瓷", "09": "造紙",
    "10": "鋼鐵", "11": "橡膠", "12": "汽車", "13": "電子", "14": "建材營造",
    "15": "航運", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "19": "綜合", "20": "其他", "21": "化學工業", "22": "生技醫療",
    "23": "油電燃氣", "24": "半導體", "25": "電腦及週邊設備", "26": "光電",
    "27": "通信網路", "28": "電子零組件", "29": "電子通路", "30": "資訊服務",
    "31": "其他電子", "32": "文化創意", "33": "農業科技", "34": "電子商務",
    "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
}


def industry_name_from_code(value: str) -> str:
    """將產業別代碼轉為名稱；非代碼則原樣回傳。"""
    v = (value or "").strip()
    return _TW_INDUSTRY_CODES.get(v.zfill(2), v) if v.isdigit() else v


def lookup_by_id(stock_id: str) -> Optional[dict]:
    return _TW_STOCKS.get(stock_id)


def lookup_by_name(query: str) -> Optional[str]:
    """以名稱/別名反查代號，回傳 stock_id 或 None。"""
    q = query.strip().lower()
    for sid, info in _TW_STOCKS.items():
        candidates = [info["name"], info.get("english", ""), *info.get("aliases", [])]
        for c in candidates:
            if c and c.lower() == q:
                return sid
    # 模糊比對：query 出現在名稱中
    for sid, info in _TW_STOCKS.items():
        if q and (q in info["name"].lower() or info["name"] in query):
            return sid
    return None


def all_ids() -> List[str]:
    return list(_TW_STOCKS.keys())
