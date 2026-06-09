"""核心資料結構（dataclass）。

設計原則：每個資料模組回傳「資料 + 狀態」，任何來源失敗都記錄在 status 內，
絕不向上拋出例外讓整體 crash。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


# --------------------------------------------------------------------------- #
# 通用狀態
# --------------------------------------------------------------------------- #
@dataclass
class SourceStatus:
    """記錄某資料模組的取得狀況。"""

    ok: bool = False
    source: str = ""              # 實際成功的來源名稱
    errors: List[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def mark_ok(self, source: str) -> None:
        self.ok = True
        self.source = source


# --------------------------------------------------------------------------- #
# 個股基本資訊
# --------------------------------------------------------------------------- #
@dataclass
class StockProfile:
    stock_id: str                       # 代號，如 2330 / AAPL
    company_name: str                   # 中文（台股）或英文（美股）公司名
    aliases: List[str] = field(default_factory=list)
    english_name: str = ""
    industry_name: str = ""
    market_type: str = ""               # 上市 / 上櫃 / 美股 NASDAQ 等
    market: str = "TW"                  # TW / US
    currency: str = "TWD"

    @property
    def is_tw(self) -> bool:
        return self.market == "TW"

    def all_names(self) -> List[str]:
        names = [self.company_name, self.english_name, *self.aliases]
        return [n for n in names if n]


# --------------------------------------------------------------------------- #
# 股價
# --------------------------------------------------------------------------- #
@dataclass
class PricePoint:
    date: date
    close: float
    volume: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None


@dataclass
class PriceData:
    points: List[PricePoint] = field(default_factory=list)
    status: SourceStatus = field(default_factory=SourceStatus)

    def window(self, days: int) -> List[PricePoint]:
        """回傳最近 N 天（日曆日）的資料點。"""
        if not self.points:
            return []
        cutoff = self.points[-1].date
        from datetime import timedelta

        start = cutoff - timedelta(days=days)
        return [p for p in self.points if p.date >= start]


# --------------------------------------------------------------------------- #
# 月營收
# --------------------------------------------------------------------------- #
@dataclass
class RevenuePoint:
    year: int
    month: int
    revenue: float                      # 當月營收（千元或原幣，視來源）
    mom: Optional[float] = None         # 月增率 %
    yoy: Optional[float] = None         # 年增率 %

    @property
    def label(self) -> str:
        return f"{self.year}/{self.month:02d}"


@dataclass
class RevenueData:
    points: List[RevenuePoint] = field(default_factory=list)
    unit: str = "千元"
    is_quarterly: bool = False          # 美股退化為季營收時為 True
    status: SourceStatus = field(default_factory=SourceStatus)


# --------------------------------------------------------------------------- #
# EPS
# --------------------------------------------------------------------------- #
@dataclass
class EpsPoint:
    period: str                         # 如 2024Q1 / 2023（年度）
    eps: float


@dataclass
class EpsData:
    quarterly: List[EpsPoint] = field(default_factory=list)
    annual: List[EpsPoint] = field(default_factory=list)
    status: SourceStatus = field(default_factory=SourceStatus)


# --------------------------------------------------------------------------- #
# 新聞
# --------------------------------------------------------------------------- #
@dataclass
class NewsItem:
    title: str
    url: str
    source: str = ""
    publish_date: Optional[datetime] = None
    snippet: str = ""
    matched_keyword: str = ""
    summary_zh: str = ""                  # 英文新聞的中文翻譯摘要（台股留空）


@dataclass
class NewsBundle:
    items: List[NewsItem] = field(default_factory=list)
    status: SourceStatus = field(default_factory=SourceStatus)
    used_industry_fallback: bool = False


# --------------------------------------------------------------------------- #
# 目標價 / 評等
# --------------------------------------------------------------------------- #
@dataclass
class RatingItem:
    source: str
    url: str
    publish_date: Optional[datetime] = None
    broker: str = ""                    # 券商 / 法人（若可辨識）
    rating: str = ""                    # 買進 / 中立 / 賣出 / 增持 / 減碼
    target_price: Optional[float] = None
    note: str = ""


@dataclass
class RatingBundle:
    items: List[RatingItem] = field(default_factory=list)
    status: SourceStatus = field(default_factory=SourceStatus)
    # 查無一致公開資料時為 True，PDF 會顯示提示語。
    insufficient: bool = False


# --------------------------------------------------------------------------- #
# 美股財報（SEC EDGAR）
# --------------------------------------------------------------------------- #
@dataclass
class FinancialRow:
    period: str                          # 如 FY2024（會計年度）
    revenue: Optional[float] = None      # 營收（百萬美元）
    net_income: Optional[float] = None   # 淨利（百萬美元）
    eps: Optional[float] = None          # 稀釋每股盈餘
    gross_margin: Optional[float] = None  # 毛利率 %


@dataclass
class FilingItem:
    form: str                            # 10-K / 10-Q / 8-K
    date: str
    title: str
    url: str
    is_earnings: bool = False            # 8-K 是否為財報發布（Item 2.02）


@dataclass
class UsFinancials:
    rows: List[FinancialRow] = field(default_factory=list)
    filings: List[FilingItem] = field(default_factory=list)
    cik: str = ""
    status: SourceStatus = field(default_factory=SourceStatus)


@dataclass
class EarningsCallInfo:
    next_date: str = ""                  # 下次財報/法說會日期（若可得）
    press_releases: List[FilingItem] = field(default_factory=list)  # 8-K 財報新聞稿
    transcript_links: List[NewsItem] = field(default_factory=list)  # 逐字稿標題+連結
    status: SourceStatus = field(default_factory=SourceStatus)


# --------------------------------------------------------------------------- #
# 技術指標（KD / MACD / RSI）
# --------------------------------------------------------------------------- #
@dataclass
class Technical:
    dates: List[date] = field(default_factory=list)
    # MACD
    dif: List[Optional[float]] = field(default_factory=list)
    dea: List[Optional[float]] = field(default_factory=list)
    macd_hist: List[Optional[float]] = field(default_factory=list)
    # KD（隨機指標）
    k: List[Optional[float]] = field(default_factory=list)
    d: List[Optional[float]] = field(default_factory=list)
    # RSI
    rsi: List[Optional[float]] = field(default_factory=list)
    # OBV（能量潮 / 量能）
    obv: List[Optional[float]] = field(default_factory=list)
    # 文字研判
    ma_alignment: str = ""               # 均線多空排列
    kd_divergence: str = ""              # KD 背離偵測
    status: SourceStatus = field(default_factory=SourceStatus)


# --------------------------------------------------------------------------- #
# 股價預測（線性回歸趨勢 + 蒙地卡羅波動率錐）
# --------------------------------------------------------------------------- #
@dataclass
class ForecastResult:
    horizon_days: int = 0                 # 預測交易日數
    last_date: Optional[date] = None
    last_price: float = 0.0
    future_dates: List[date] = field(default_factory=list)
    trend: List[float] = field(default_factory=list)   # 線性回歸延伸線
    p10: List[float] = field(default_factory=list)      # 悲觀情境
    p50: List[float] = field(default_factory=list)      # 中位情境
    p90: List[float] = field(default_factory=list)      # 樂觀情境
    annual_vol: float = 0.0               # 年化波動率 %
    r2: float = 0.0                       # 線性回歸 R²
    window: int = 0                       # 估計所用的交易日數
    status: SourceStatus = field(default_factory=SourceStatus)


# --------------------------------------------------------------------------- #
# 彙總報告
# --------------------------------------------------------------------------- #
@dataclass
class Report:
    profile: StockProfile
    generated_at: datetime
    price: PriceData
    revenue: RevenueData
    eps: EpsData
    news: NewsBundle
    rating: RatingBundle
    # 各區塊的簡短中文趨勢說明
    price_insight: str = ""
    revenue_insight: str = ""
    eps_insight: str = ""
    # 股價預測
    forecast: Optional["ForecastResult"] = None
    forecast_insight: str = ""
    # 技術指標
    technical: Optional["Technical"] = None
    technical_insight: str = ""
    # 美股專屬（台股為 None）
    us_financials: Optional["UsFinancials"] = None
    earnings_call: Optional["EarningsCallInfo"] = None
    references: List[tuple] = field(default_factory=list)  # (label, url)
