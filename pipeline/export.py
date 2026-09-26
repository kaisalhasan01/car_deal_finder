"""Export the star schema for Power BI (or Excel, Tableau, pandas ...).

    python -m pipeline.export                       # CSV -> powerbi/data/ (real DB, else sample)
    python -m pipeline.export --format parquet      # typed columns, no locale surprises
    python -m pipeline.export --db car_deals_sample.db --out powerbi/sample_data

CSV is UTF-8 with BOM, comma-separated, dot decimals and ISO dates. In Power BI,
set the locale to English (United States) when changing types, or use Parquet,
which keeps the types. See powerbi/README.md.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import db   # noqa: E402

# name -> SQL. Star schema tables keep their keys; two convenience views are added.
EXPORTS = {
    "fact_listings": "SELECT * FROM fact_listings",
    "fact_price_snapshots": "SELECT * FROM fact_price_snapshots",
    "dim_car": "SELECT * FROM dim_car",
    "dim_location": "SELECT * FROM dim_location",
    "dim_seller": "SELECT * FROM dim_seller",
    "dim_date": "SELECT * FROM dim_date",
    "car_specs": "SELECT * FROM car_specs",
    "known_issues": "SELECT * FROM known_issues",
    "listing_issues": "SELECT * FROM vw_listing_issues",
    "valuation_models": "SELECT * FROM valuation_models",
    "etl_runs": "SELECT * FROM etl_runs",
    # One flat table: the fastest way to start (no relationships needed).
    "listings_flat": "SELECT * FROM vw_listings",
}


def export(db_path: Path, out_dir: Path, fmt: str = "csv") -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = db.connect(db_path)
    db.init_db(conn)                       # refreshes views; refuses old schemas
    counts = {}
    try:
        for name, sql in EXPORTS.items():
            df = pd.read_sql_query(sql, conn)
            if fmt == "parquet":
                df.to_parquet(out_dir / f"{name}.parquet", index=False)
            else:
                df.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
            counts[name] = len(df)
    finally:
        conn.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Export the star schema for Power BI")
    ap.add_argument("--db", default=None, help="default: car_deals.db, else car_deals_sample.db")
    ap.add_argument("--out", default=str(ROOT / "powerbi" / "data"))
    ap.add_argument("--format", choices=["csv", "parquet"], default="csv")
    args = ap.parse_args(argv)
    db_path = Path(args.db) if args.db else (
        db.DEFAULT_DB_PATH if db.DEFAULT_DB_PATH.exists() else db.SAMPLE_DB_PATH)
    if not db_path.exists():
        print(f"{db_path} not found — run `python -m pipeline.run` first.")
        return 2
    try:
        counts = export(db_path, Path(args.out), args.format)
    except ImportError as exc:
        print(f"Parquet needs pyarrow: pip install pyarrow ({exc})")
        return 2
    print(f"exported {db_path.name} -> {args.out} ({args.format})")
    for name, n in counts.items():
        print(f"   {name:22s} {n:>6} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
