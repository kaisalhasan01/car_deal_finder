"""Shared service layer for the API and the Streamlit app.

Loads the market (real listings from the database, or a clearly labelled demo),
keeps a fitted valuer per data version, and answers the questions both front-ends
ask: who matches this profile, and what is this car worth.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from database import db
from pipeline.matcher import BuyerProfile, attach_valuations, rank
from pipeline.valuation import HedonicValuer, value_listings
from scrapers import sample_data

VALUATION_WINDOW_DAYS = 90


@dataclass
class Market:
    listings: list[dict]        # active listings with valuation fields
    comparables: list[dict]     # everything the valuer learned from
    valuer: HedonicValuer
    label: str                  # human description of the data
    demo: bool                  # True -> synthetic data, must be labelled
    db_path: Path | None
    version: str                # changes when the data changes (cache key)


_CACHE: dict[str, Market] = {}


def _db_version(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT COUNT(*), COALESCE(MAX(run_id), 0) FROM etl_runs").fetchone()
    return f"{row[0]}:{row[1]}"


def load_market(db_path: Path | str | None = None, allow_demo: bool = True,
                demo_size: int = 300) -> Market:
    """The current market. Cached until the database gets a new ETL run."""
    path = Path(db_path) if db_path else db.DEFAULT_DB_PATH
    if path.exists():
        conn = db.connect(path)
        try:
            db.init_db(conn)
            version = f"{path}:{_db_version(conn)}"
            if version in _CACHE:
                return _CACHE[version]
            active = db.fetch_listings(conn, active_only=True)
            comparables = db.fetch_listings(
                conn, active_only=False,
                seen_since=date.today() - timedelta(days=VALUATION_WINDOW_DAYS))
            last = conn.execute("SELECT MAX(finished_at) FROM etl_runs").fetchone()[0]
        finally:
            conn.close()
        if active:
            demo = any(r["source"] == "sample" for r in active)
            label = (f"{path.name}: {len(active)} aktiva annonser, uppdaterad "
                     f"{(last or '?')[:16].replace('T', ' ')}")
            market = Market(active, comparables, HedonicValuer().fit(comparables), label, demo,
                            path, version)
            _CACHE[version] = market
            return market
    if not allow_demo:
        raise FileNotFoundError(f"No listings in {path}. Run the ETL first.")
    version = f"demo:{demo_size}:{date.today()}"
    if version not in _CACHE:
        listings = sample_data.generate(n=demo_size)
        valuer, vals = value_listings(listings)
        _CACHE[version] = Market(attach_valuations(listings, vals), listings, valuer,
                                 f"{demo_size} syntetiska annonser (demo)", True, None, version)
    return _CACHE[version]


def recommend(market: Market, profile: BuyerProfile, top_n: int = 10) -> list[dict]:
    return rank(market.listings, profile, top_n=top_n)


def valuate(market: Market, car: dict) -> dict | None:
    """Market value of any car (not necessarily listed), against current comparables."""
    v = market.valuer.value(car)
    return v.as_dict() if v else None


def model_curve(market: Market, brand: str, model: str, km_per_year: int = 15_000,
                margin: int = 3) -> list[dict]:
    """Typical value by age, from `margin` years before to after the ages seen in the data.
    Each point says whether it lies inside the data (`in_data`) or is extrapolated."""
    rng = market.valuer.age_range()
    if rng is None:
        return []
    lo, hi = max(0, int(rng[0]) - margin), int(rng[1]) + margin
    points = market.valuer.curve(brand, model, ages=range(lo, hi + 1), km_per_year=km_per_year)
    return [{**pt, "in_data": rng[0] <= pt["age"] <= rng[1]} for pt in points]


def clear_cache() -> None:
    _CACHE.clear()
