"""驗證核心韌性：來源失敗回傳空結構而非例外，且 PDF 仍能產生。

執行：python -m pytest tests/ -q   （或 python -m unittest）
這些測試不依賴網路（以 monkeypatch 模擬失敗）。
"""

from __future__ import annotations

import unittest
from datetime import datetime

from stock_report.core.models import (
    EpsData,
    NewsBundle,
    PriceData,
    RatingBundle,
    Report,
    RevenueData,
    StockProfile,
)
from stock_report.core.normalizer import normalize
from stock_report.datasources.news import aggregator
from stock_report.datasources.news.base import NewsProvider


class _ExplodingProvider(NewsProvider):
    name = "Exploding"

    def search(self, keyword, limit=10):
        raise RuntimeError("模擬來源爆炸")


class TestNormalizer(unittest.TestCase):
    def test_tw_id(self):
        p = normalize("2330")
        self.assertEqual(p.stock_id, "2330")
        self.assertEqual(p.company_name, "台積電")
        self.assertEqual(p.market, "TW")

    def test_name_lookup(self):
        p = normalize("台積電")
        self.assertEqual(p.stock_id, "2330")

    def test_empty(self):
        p = normalize("")
        self.assertIsInstance(p, StockProfile)  # 不丟例外


class TestNewsResilience(unittest.TestCase):
    def test_safe_search_swallows_exception(self):
        prov = _ExplodingProvider()
        # safe_search 必須吞掉例外回空清單
        self.assertEqual(prov.safe_search("台積電"), [])

    def test_aggregator_all_fail_returns_empty_bundle(self):
        # 所有 provider 都爆炸時，仍回傳 NewsBundle 而非 crash
        original = aggregator._providers
        aggregator._providers = lambda: [_ExplodingProvider(), _ExplodingProvider()]
        try:
            bundle = aggregator.get_news(
                StockProfile(stock_id="2330", company_name="台積電",
                             industry_name="半導體")
            )
        finally:
            aggregator._providers = original
        self.assertIsInstance(bundle, NewsBundle)
        self.assertEqual(bundle.items, [])
        self.assertTrue(bundle.status.errors)


class TestRatingResilience(unittest.TestCase):
    def test_rating_insufficient_when_no_data(self):
        from stock_report.datasources import rating as rating_mod
        from stock_report.datasources.news import cnyes, google_news

        # 讓所有 provider 回空，模擬查無任何公開資料
        orig_g = google_news.GoogleNewsProvider.search
        orig_c = cnyes.CnyesProvider.search
        google_news.GoogleNewsProvider.search = lambda self, kw, limit=10: []
        cnyes.CnyesProvider.search = lambda self, kw, limit=10: []
        try:
            bundle = rating_mod.get_rating(
                StockProfile(stock_id="0000", company_name="不存在公司")
            )
        finally:
            google_news.GoogleNewsProvider.search = orig_g
            cnyes.CnyesProvider.search = orig_c
        self.assertIsInstance(bundle, RatingBundle)
        self.assertTrue(bundle.insufficient)


class TestForecast(unittest.TestCase):
    def _synthetic_price(self, n=150, start=100.0):
        from datetime import date, timedelta

        from stock_report.core.models import PricePoint

        pts = []
        d = date(2025, 1, 1)
        price = start
        for i in range(n):
            price *= 1.001 + (0.01 if i % 7 == 0 else -0.008)
            pts.append(PricePoint(date=d + timedelta(days=i), close=price))
        return PriceData(points=pts)

    def test_forecast_produces_ordered_bands(self):
        from stock_report.analysis.forecast import forecast

        fc = forecast(self._synthetic_price(), horizon_days=10, n_sims=500)
        self.assertTrue(fc.status.ok)
        self.assertEqual(len(fc.p50), 10)
        # 百分位帶必須有序：P10 <= P50 <= P90
        for a, b, c in zip(fc.p10, fc.p50, fc.p90):
            self.assertLessEqual(a, b + 1e-6)
            self.assertLessEqual(b, c + 1e-6)

    def test_forecast_insufficient_data_no_crash(self):
        from stock_report.analysis.forecast import forecast

        fc = forecast(self._synthetic_price(n=10))
        self.assertFalse(fc.status.ok)
        self.assertTrue(fc.status.errors)


class TestIndicators(unittest.TestCase):
    def _price(self, n=120):
        from datetime import date, timedelta

        from stock_report.core.models import PricePoint

        pts, d, base = [], date(2025, 1, 1), 100.0
        for i in range(n):
            base *= 1.002 if i % 5 else 0.99
            pts.append(PricePoint(date=d + timedelta(days=i), close=base,
                                  high=base * 1.01, low=base * 0.99))
        return PriceData(points=pts)

    def test_compute_indicators(self):
        from stock_report.analysis.indicators import compute

        t = compute(self._price())
        self.assertTrue(t.status.ok)
        self.assertEqual(len(t.k), len(t.dates))
        # KD 介於 0~100
        kvals = [v for v in t.k if v is not None]
        self.assertTrue(all(0 <= v <= 100 for v in kvals))
        rvals = [v for v in t.rsi if v is not None]
        self.assertTrue(all(0 <= v <= 100 for v in rvals))

    def test_insufficient_no_crash(self):
        from stock_report.analysis.indicators import compute

        t = compute(self._price(n=10))
        self.assertFalse(t.status.ok)


class TestRelevance(unittest.TestCase):
    def setUp(self):
        self.p = StockProfile(stock_id="1605", company_name="華新",
                              industry_name="電器電纜")

    def test_matches_own_id_and_standalone_name(self):
        from stock_report.core.relevance import is_relevant

        self.assertTrue(is_relevant("盤中速報 - 華新(1605)大跌7%", self.p))
        self.assertTrue(is_relevant("華新 除息 0.9 元", self.p))

    def test_rejects_confusable_longer_name(self):
        from stock_report.core.relevance import is_relevant

        # 華新科(2492) 不應被當成 華新(1605)
        self.assertFalse(is_relevant("華新科大漲7.65%，報422元", self.p))

    def test_rejects_other_code_after_name(self):
        from stock_report.core.relevance import is_relevant

        # 名稱後緊接他檔代號
        self.assertFalse(is_relevant("《投信賣超》華新(4435)、神基(4430)", self.p))

    def test_ascii_ticker_word_boundary(self):
        from stock_report.core.relevance import is_relevant

        ap = StockProfile(stock_id="AAPL", company_name="Apple Inc.",
                          english_name="Apple Inc.", market="US")
        self.assertTrue(is_relevant("HSBC raises AAPL target to 260", ap))
        self.assertFalse(is_relevant("PINEAPPLES are tasty", ap))


class TestSecResilience(unittest.TestCase):
    def test_unknown_ticker_returns_empty_not_crash(self):
        from stock_report.datasources import sec

        fin = sec.get_us_financials("ZZZZNOTREAL")
        self.assertEqual(fin.rows, [])
        self.assertFalse(fin.status.ok)
        self.assertTrue(fin.status.errors)

    def test_pdf_builds_with_us_sections_empty(self):
        from stock_report.core.models import EarningsCallInfo, UsFinancials
        from stock_report.report.pdf_builder import build_pdf

        report = Report(
            profile=StockProfile(stock_id="AAPL", company_name="Apple Inc.",
                                 market="US", market_type="美股 NASDAQ"),
            generated_at=datetime.now(),
            price=PriceData(), revenue=RevenueData(), eps=EpsData(),
            news=NewsBundle(), rating=RatingBundle(insufficient=True),
            us_financials=UsFinancials(),          # 空 SEC 資料
            earnings_call=EarningsCallInfo(),       # 空法說會
            references=[("SEC", "https://sec.gov")],
        )
        pdf = build_pdf(report)
        self.assertTrue(pdf.startswith(b"%PDF"))


class TestPdfWithEmptyData(unittest.TestCase):
    def test_pdf_builds_with_all_empty_sections(self):
        from stock_report.report.pdf_builder import build_pdf

        report = Report(
            profile=StockProfile(stock_id="2330", company_name="台積電",
                                 industry_name="半導體", market_type="上市"),
            generated_at=datetime.now(),
            price=PriceData(),
            revenue=RevenueData(),
            eps=EpsData(),
            news=NewsBundle(),
            rating=RatingBundle(insufficient=True),
            price_insight="查無資料",
            revenue_insight="查無資料",
            eps_insight="查無資料",
        )
        pdf = build_pdf(report)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)


class TestRatingExtraction(unittest.TestCase):
    def test_extract_target_price(self):
        from stock_report.datasources.rating import _extract_target, _extract_rating

        self.assertEqual(_extract_target("外資看好台積電，目標價上看 1500 元"), 1500.0)
        self.assertEqual(_extract_rating("某外資給予買進評等"), "買進")
        self.assertIsNone(_extract_target("今年營收成長"))


if __name__ == "__main__":
    unittest.main()
