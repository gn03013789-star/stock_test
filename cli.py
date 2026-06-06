"""CLI 入口：python cli.py 2330

用法：
    python cli.py 2330
    python cli.py 台積電
    python cli.py AAPL
    python cli.py 2317 --output D:\\reports
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from stock_report.config import OUTPUT_DIR
from stock_report.pipeline import build_pdf_bytes


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "report"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="台股/美股投資分析 PDF 報告產生器")
    parser.add_argument("query", help="股票代號或名稱，例如 2330 / 台積電 / AAPL")
    parser.add_argument("--output", "-o", default=str(OUTPUT_DIR),
                        help="輸出資料夾（預設 ./output）")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示詳細日誌")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    def progress(msg, frac):
        bar = "█" * int(frac * 20)
        print(f"\r[{bar:<20}] {int(frac*100):3d}%  {msg:<24}", end="", flush=True)

    report, pdf = build_pdf_bytes(args.query, progress=progress)
    print()  # 換行

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = (
        f"{_safe_filename(report.profile.company_name)}_投資分析報告_"
        f"{report.generated_at:%Y%m%d}.pdf"
    )
    path = out_dir / fname
    path.write_bytes(pdf)

    print(f"\n✔ 報告已產生：{path}")
    print(f"  公司：{report.profile.company_name}（{report.profile.stock_id}）")
    print(f"  股價：{'OK' if report.price.points else '無資料'}"
          f"｜營收：{'OK' if report.revenue.points else '無資料'}"
          f"｜EPS：{'OK' if report.eps.quarterly else '無資料'}"
          f"｜新聞：{len(report.news.items)} 則"
          f"｜評等：{len(report.rating.items)} 則")
    return 0


if __name__ == "__main__":
    sys.exit(main())
