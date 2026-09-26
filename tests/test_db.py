"""Star schema v2: init, upserts, price history, deactivation, source guard, views."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from database import db


def _rec(url="https://x/1", price=100_000, **kw):
    base = {"brand": "Volvo", "model": "V60", "year": 2018, "mileage": 120_000, "price": price,
            "city": "Linköping", "county": "Östergötlands län", "url": url,
            "listing_date": date(2026, 9, 1), "fuel_type": "Diesel", "gearbox": "Automat",
            "seller_type": "private"}
    return {**base, **kw}


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    yield c
    c.close()


def test_init_creates_schema_views_and_version(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert {"fact_listings", "fact_price_snapshots", "dim_car", "dim_location", "dim_seller",
            "dim_date", "car_specs", "known_issues", "valuation_models", "etl_runs"} <= names
    assert {"vw_listings", "vw_deal_board", "vw_price_changes", "vw_model_market"} <= names
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    db.init_db(conn)                                         # idempotent


def test_old_schema_is_refused(tmp_path):
    c = sqlite3.connect(tmp_path / "old.db")
    c.execute("CREATE TABLE fact_listings (listing_id INTEGER PRIMARY KEY, blocket_price INT)")
    c.commit()
    with pytest.raises(db.SchemaVersionError):
        db.init_db(c)


def test_upsert_keeps_first_seen_and_tracks_price_history(conn):
    d1, d2 = date(2026, 9, 20), date(2026, 9, 26)
    s1 = db.upsert_listings(conn, [_rec()], source="blocket", scope="q", today=d1)
    s2 = db.upsert_listings(conn, [_rec(price=92_000)], source="blocket", scope="q", today=d2)
    assert (s1["new"], s2["new"], s2["price_changes"]) == (1, 0, 1)
    row = conn.execute("SELECT * FROM vw_listings").fetchone()
    assert row["price_sek"] == 92_000 and row["first_price_sek"] == 100_000
    assert row["price_change_sek"] == -8_000
    assert row["first_seen_date"] == "2026-09-20" and row["last_seen_date"] == "2026-09-26"
    assert row["days_on_market"] == 25                       # published 2026-09-01
    changes = conn.execute("SELECT * FROM vw_price_changes").fetchone()
    assert changes["observations"] == 2 and changes["price_drops"] == 1


def test_calendar_is_continuous(conn):
    db.upsert_listings(conn, [_rec()], source="blocket", scope="q", today=date(2026, 9, 26))
    days = conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM dim_date").fetchone()
    assert tuple(days) == (26, "2026-09-01", "2026-09-26")
    sat = conn.execute("SELECT weekday_name, is_weekend FROM dim_date WHERE date='2026-09-26'").fetchone()
    assert tuple(sat) == ("lördag", 1)


def test_ads_missing_from_a_complete_scan_are_deactivated(conn):
    d1, d2 = date(2026, 9, 20), date(2026, 9, 26)
    db.upsert_listings(conn, [_rec("https://x/1"), _rec("https://x/2")], source="blocket",
                       scope="q", today=d1)
    db.upsert_listings(conn, [_rec("https://x/1")], source="blocket", scope="q", today=d2)
    assert db.deactivate_missing(conn, "q", d2) == 1
    active = {r[0] for r in conn.execute("SELECT url FROM fact_listings WHERE is_active=1")}
    assert active == {"https://x/1"}
    assert len(db.fetch_listings(conn)) == 1 and len(db.fetch_listings(conn, active_only=False)) == 2


def test_sample_and_real_data_never_mix(conn):
    db.upsert_listings(conn, [_rec()], source="sample", scope="sample", today=date(2026, 9, 26))
    with pytest.raises(db.MixedSourceError):
        db.check_source(conn, "blocket")
    db.check_source(conn, "sample")                          # same source is fine


def test_fetch_listings_returns_matcher_shape(conn):
    db.upsert_listings(conn, [_rec(drivetrain="AWD", regnr="ABC123")], source="blocket",
                       scope="q", today=date(2026, 9, 26))
    (row,) = db.fetch_listings(conn)
    assert row["year"] == 2018 and row["price"] == 100_000 and row["mileage"] == 120_000
    assert row["drivetrain"] == "AWD" and row["regnr"] == "ABC123"
    assert row["seller_type"] == "private" and row["fuel_type"] == "Diesel"
