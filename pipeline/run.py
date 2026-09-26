"""End-to-end ETL pipeline: fetch listings -> estimate value -> compute discount
-> load into SQLite (incl. the curated reference tables for Power BI).

    python -m pipeline.run --source sample --limit 200
    python -m pipeline.run --source blocket --query "volvo v60" --pages 2
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import db                              # noqa: E402
from scrapers import sample_data                     # noqa: E402
from scrapers.blocket import BlocketScraper          # noqa: E402
from scrapers.carinfo import CarInfoValuer           # noqa: E402
from reference.specs_data import SPECS               # noqa: E402
from reference.known_issues_data import ISSUES       # noqa: E402


def fetch_listings(source: str, query: str, pages: int, limit: int) -> list[dict]:
    if source == "sample":
        return sample_data.generate(n=limit)
    if source in ("blocket", "blocket-bd"):
        if source == "blocket-bd":
            from scrapers.blocket_brightdata import BlocketBrightDataScraper
            scraper = BlocketBrightDataScraper()   # real data via Bright Data Web Unlocker
        else:
            scraper = BlocketScraper()             # plain requests (likely blocked)
        rows = [item.as_dict() for item in scraper.search(query=query, pages=pages)]
        return rows[:limit] if limit else rows
    raise ValueError(f"unknown source: {source}")


def build_records(listings: list[dict], enable_carinfo: bool) -> list[dict]:
    valuer = CarInfoValuer(listings, enable_carinfo=enable_carinfo)
    records = []
    for it in listings:
        value, method = valuer.estimate(it)
        pct = round((value - it["price"]) / value * 100, 2) if value else None
        records.append({
            "brand": it["brand"], "model": it["model"], "year": it["year"],
            "fuel_type": it.get("fuel_type"), "gearbox": it.get("gearbox"), "color": it.get("color"),
            "city": it.get("city", "unknown"), "county": it.get("county"),
            "listing_date": it.get("listing_date", date.today()),
            "blocket_price": it["price"], "carinfo_value": value, "discount_pct": pct,
            "mileage": it.get("mileage"), "days_on_market": it.get("days_on_market"),
            "url": it["url"], "value_method": method,
        })
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description="Swedish Car Deal Finder pipeline")
    ap.add_argument("--source", choices=["sample", "blocket", "blocket-bd"], default="sample",
                    help="blocket-bd = real listings via Bright Data Web Unlocker")
    ap.add_argument("--query", default="")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--db", default=str(db.DEFAULT_DB_PATH))
    ap.add_argument("--enable-carinfo", action="store_true")
    args = ap.parse_args()

    print(f"[1/4] Fetching listings (source={args.source}) ...")
    listings = fetch_listings(args.source, args.query, args.pages, args.limit)
    print(f"      got {len(listings)} listings")

    print("[2/4] Estimating market value + discount ...")
    records = build_records(listings, enable_carinfo=args.enable_carinfo)

    print(f"[3/4] Loading into SQLite ({args.db}) ...")
    conn = db.connect(args.db)
    db.init_db(conn)
    summary = db.load_listings(conn, records)
    n_specs = db.load_specs(conn, SPECS)
    n_issues = db.load_known_issues(conn, ISSUES)
    conn.close()
    print(f"      loaded {summary['records']} listings, {n_specs} specs, {n_issues} known issues")

    print("[4/4] Done. Run `python -m pipeline.recommend` for personalized matches.")


if __name__ == "__main__":
    main()
