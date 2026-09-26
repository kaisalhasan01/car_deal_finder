"""End-to-end ETL: fetch listings -> load the star schema (+ daily price snapshots)
-> value the whole market with the hedonic model -> store model summaries -> log the run.

    python -m pipeline.run --source sample                          # demo DB: car_deals_sample.db
    python -m pipeline.run --source blocket --query "volvo v60" --pages 5
    python -m pipeline.run --source blocket --make Volvo,Audi --county "Stockholms län" --pages 10
    python -m pipeline.run --source replay --replay data/raw/blocket/2026-09-26

Real data goes to car_deals.db and sample data to car_deals_sample.db. The two are
never mixed. Run the same search daily and the database builds price history, and
ads that vanish from a fully scanned search are marked inactive (likely sold).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import db                                      # noqa: E402
from pipeline.valuation import looks_damaged, value_listings  # noqa: E402
from reference.known_issues_data import ISSUES               # noqa: E402
from reference.lookup import get_spec, spec_key              # noqa: E402
from reference.specs_data import SPECS                       # noqa: E402
from scrapers import sample_data                             # noqa: E402

VALUATION_WINDOW_DAYS = 90   # comparables: every ad seen in the last 90 days


@dataclass
class FetchResult:
    listings: list[dict]
    source: str                      # what the rows are: 'sample' | 'blocket'
    scope: str                       # which search produced them
    reached_end: bool                # True only if the search was scanned to its last page
    stats: dict = field(default_factory=dict)


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def fetch(args) -> FetchResult:
    if args.source == "sample":
        rows = sample_data.generate(n=args.limit)
        return FetchResult(rows, "sample", "sample", True, {"generated": len(rows)})

    from scrapers.blocket import SearchFilters, build_scraper, iter_snapshot_listings

    if args.source == "replay":
        if not args.replay:
            raise SystemExit("--source replay needs --replay <snapshot dir or file>")
        rows = [it.as_dict() for it in iter_snapshot_listings([args.replay],
                                                              mileage_unit=args.mileage_unit)]
        return FetchResult(rows, "blocket", f"replay:{Path(args.replay).name}", False,
                           {"replayed": len(rows)})

    filters = SearchFilters(
        query=args.query, makes=_csv(args.make), counties=_csv(args.county),
        price_from=args.price_min, price_to=args.price_max,
        year_from=args.year_min, year_to=args.year_max, mileage_km_to=args.mileage_max,
    )
    snapshot_dir = None if args.no_snapshots else PROJECT_ROOT / "data" / "raw" / "blocket"
    scraper = build_scraper(args.transport, snapshot_dir=snapshot_dir,
                            mileage_unit=args.mileage_unit, delay=args.delay)
    rows = [it.as_dict() for it in scraper.search(pages=args.pages, filters=filters)]
    if args.limit and len(rows) > args.limit:
        rows = rows[:args.limit]
    stats = scraper.stats
    print(f"      {stats.summary()}")
    return FetchResult(rows, "blocket", filters.scope_key(),
                       stats.reached_end and not stats.errors,
                       {"pages_fetched": stats.pages_fetched, "ads_seen": stats.ads_seen,
                        "skipped": dict(stats.skipped), "match_count": stats.match_count})


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Swedish Car Deal Finder ETL")
    ap.add_argument("--source", choices=["sample", "blocket", "replay"], default="sample")
    ap.add_argument("--db", default=None, help="default: car_deals.db (real) / car_deals_sample.db")
    ap.add_argument("--rebuild", action="store_true", help="delete the database first")
    ap.add_argument("--allow-mixed", action="store_true", help="allow sample + real in one DB")
    ap.add_argument("--limit", type=int, default=None, help="sample size / cap on fetched ads")
    # Blocket search
    ap.add_argument("--query", default="", help='free text, e.g. "volvo v60"')
    ap.add_argument("--make", default="", help="comma list of brands, e.g. Volvo,Audi")
    ap.add_argument("--county", default="", help="comma list, e.g. 'Stockholms län'")
    ap.add_argument("--price-min", type=int)
    ap.add_argument("--price-max", type=int)
    ap.add_argument("--year-min", type=int)
    ap.add_argument("--year-max", type=int)
    ap.add_argument("--mileage-max", type=int, help="km")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between pages")
    ap.add_argument("--transport", choices=["direct", "brightdata"], default="direct")
    ap.add_argument("--mileage-unit", choices=["auto", "mil", "km"], default="auto")
    ap.add_argument("--no-snapshots", action="store_true", help="don't save raw pages")
    ap.add_argument("--replay", help="snapshot dir/file for --source replay")
    args = ap.parse_args(argv)
    if args.source == "sample" and args.limit is None:
        args.limit = 200

    db_path = Path(args.db) if args.db else (
        db.SAMPLE_DB_PATH if args.source == "sample" else db.DEFAULT_DB_PATH)
    if args.rebuild and db_path.exists():
        db_path.unlink()
    today, started = date.today(), datetime.now().isoformat(timespec="seconds")

    print(f"[1/5] Fetching listings (source={args.source}) ...")
    res = fetch(args)
    print(f"      got {len(res.listings)} listings")
    if not res.listings:
        print("      nothing to load — stopping (see messages above).")
        return 1

    print(f"[2/5] Preparing {db_path.name} (schema v{db.SCHEMA_VERSION}, reference data) ...")
    conn = db.connect(db_path)
    try:
        db.init_db(conn)
        db.check_source(conn, res.source, allow_mixed=args.allow_mixed)
    except (db.SchemaVersionError, db.MixedSourceError) as exc:
        print(f"      ERROR: {exc}")
        return 2
    n_specs, n_issues = db.load_specs(conn, SPECS), db.load_known_issues(conn, ISSUES)
    ids = db.spec_id_map(conn)
    spec_ids = {}
    for rec in res.listings:
        rec["damage_flag"] = looks_damaged(rec.get("title"), rec.get("model_spec"))
        spec_ids[rec["url"]] = ids.get(spec_key(get_spec(rec["brand"], rec["model"],
                                                         rec.get("fuel_type"))))

    print("[3/5] Loading listings + price snapshots ...")
    load = db.upsert_listings(conn, res.listings, source=res.source, scope=res.scope,
                              today=today, spec_ids=spec_ids)
    deactivated = db.deactivate_missing(conn, res.scope, today) if res.reached_end else 0
    print(f"      {load['loaded']} loaded ({load['new']} new, {load['price_changes']} price "
          f"changes), {deactivated} marked inactive")

    print("[4/5] Valuing the market (hierarchical hedonic model, leave-one-out) ...")
    market = db.fetch_listings(conn, active_only=False, source=res.source,
                               seen_since=today - timedelta(days=VALUATION_WINDOW_DAYS))
    valuer, vals = value_listings(market)
    n_valued = db.write_valuations(conn, [(m["listing_id"], v) for m, v in zip(market, vals)])
    n_models = db.write_valuation_models(conn, valuer.summaries(), today) if valuer.fitted else 0
    if valuer.fitted:
        print(f"      valued {n_valued} listings; {n_models} depreciation curves "
              f"(global σ {valuer.sigma_glob:.2f})")
    else:
        print("      too few listings to fit a market model yet — values left empty")

    print("[5/5] Logging run ...")
    run_id = db.log_run(
        conn, started_at=started, finished_at=datetime.now().isoformat(timespec="seconds"),
        source=res.source, scope=res.scope, pages_fetched=res.stats.get("pages_fetched"),
        ads_seen=res.stats.get("ads_seen"), listings_loaded=load["loaded"],
        new_listings=load["new"], price_changes=load["price_changes"],
        deactivated=deactivated, reached_end=int(res.reached_end),
        notes=str(res.stats.get("skipped") or ""))
    conn.close()
    print(f"      run #{run_id}: {load['loaded']} listings, {n_specs} specs, {n_issues} known issues")
    print(f"Done. Next: python -m pipeline.recommend --db {db_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
