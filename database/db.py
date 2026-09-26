"""SQLite access layer for the Swedish Car Deal Finder.

Responsibilities:
  * create the schema (``init_db``)
  * resolve / insert dimension rows and return their surrogate keys
  * load normalized listing records into the star schema (``load_listings``)
  * load the curated reference data (``load_specs`` / ``load_known_issues``)
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "car_deals.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection, schema_path: Path | str = SCHEMA_PATH) -> None:
    conn.executescript(Path(schema_path).read_text(encoding="utf-8"))
    conn.commit()


# ---------------------------------------------------------------------------
# Dimension upserts
# ---------------------------------------------------------------------------
def _clean(value: str | None) -> str:
    if value is None:
        return "unknown"
    value = str(value).strip()
    return value if value else "unknown"


def get_or_create_car(conn: sqlite3.Connection, rec: dict) -> int:
    brand, model, year = str(rec["brand"]).strip(), str(rec["model"]).strip(), int(rec["year"])
    fuel, gearbox, color = _clean(rec.get("fuel_type")), _clean(rec.get("gearbox")), _clean(rec.get("color"))
    conn.execute(
        """INSERT OR IGNORE INTO dim_car (brand, model, year, fuel_type, gearbox, color)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (brand, model, year, fuel, gearbox, color),
    )
    row = conn.execute(
        """SELECT car_id FROM dim_car
           WHERE brand=? AND model=? AND year=? AND fuel_type=? AND gearbox=? AND color=?""",
        (brand, model, year, fuel, gearbox, color),
    ).fetchone()
    return row["car_id"]


def get_or_create_location(conn: sqlite3.Connection, rec: dict) -> int:
    city, county = str(rec["city"]).strip(), _clean(rec.get("county"))
    conn.execute("INSERT OR IGNORE INTO dim_location (city, county) VALUES (?, ?)", (city, county))
    row = conn.execute(
        "SELECT location_id FROM dim_location WHERE city=? AND county=?", (city, county)
    ).fetchone()
    return row["location_id"]


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def get_or_create_time(conn: sqlite3.Connection, listing_date) -> int:
    d = _as_date(listing_date)
    date_id = d.year * 10000 + d.month * 100 + d.day
    conn.execute(
        """INSERT OR IGNORE INTO dim_time (date_id, date, week, month, year)
           VALUES (?, ?, ?, ?, ?)""",
        (date_id, d.isoformat(), d.isocalendar().week, d.month, d.year),
    )
    return date_id


# ---------------------------------------------------------------------------
# Fact load
# ---------------------------------------------------------------------------
def load_listings(conn: sqlite3.Connection, records: Iterable[dict]) -> dict:
    inserted = 0
    for rec in records:
        car_id = get_or_create_car(conn, rec)
        location_id = get_or_create_location(conn, rec)
        date_id = get_or_create_time(conn, rec["listing_date"])
        conn.execute(
            """INSERT INTO fact_listings
                   (car_id, location_id, date_id, blocket_price, carinfo_value,
                    discount_pct, mileage, days_on_market, url, value_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                   car_id=excluded.car_id, location_id=excluded.location_id,
                   date_id=excluded.date_id, blocket_price=excluded.blocket_price,
                   carinfo_value=excluded.carinfo_value, discount_pct=excluded.discount_pct,
                   mileage=excluded.mileage, days_on_market=excluded.days_on_market,
                   value_method=excluded.value_method""",
            (
                car_id, location_id, date_id,
                int(rec["blocket_price"]), _int_or_none(rec.get("carinfo_value")),
                _float_or_none(rec.get("discount_pct")), _int_or_none(rec.get("mileage")),
                _int_or_none(rec.get("days_on_market")), rec.get("url"), rec.get("value_method"),
            ),
        )
        inserted += 1
    conn.commit()
    return {"records": inserted}


# ---------------------------------------------------------------------------
# Reference-data load (specs + known issues)
# ---------------------------------------------------------------------------
def load_specs(conn: sqlite3.Connection, specs: Iterable[dict]) -> int:
    n = 0
    for s in specs:
        conn.execute(
            """INSERT INTO car_specs
                   (brand, model, body_type, drivetrain, power_hp, primary_fuel,
                    fuel_l_per_100km, energy_kwh_per_100km, annual_tax_sek, reliability)
               VALUES (:brand, :model, :body_type, :drivetrain, :power_hp, :primary_fuel,
                       :fuel_l_per_100km, :energy_kwh_per_100km, :annual_tax_sek, :reliability)
               ON CONFLICT(brand, model) DO UPDATE SET
                   body_type=excluded.body_type, drivetrain=excluded.drivetrain,
                   power_hp=excluded.power_hp, primary_fuel=excluded.primary_fuel,
                   fuel_l_per_100km=excluded.fuel_l_per_100km,
                   energy_kwh_per_100km=excluded.energy_kwh_per_100km,
                   annual_tax_sek=excluded.annual_tax_sek, reliability=excluded.reliability""",
            {**{k: None for k in (
                "body_type", "drivetrain", "power_hp", "primary_fuel",
                "fuel_l_per_100km", "energy_kwh_per_100km", "annual_tax_sek", "reliability")}, **s},
        )
        n += 1
    conn.commit()
    return n


def load_known_issues(conn: sqlite3.Connection, issues: Iterable[dict]) -> int:
    n = 0
    for it in issues:
        conn.execute(
            """INSERT INTO known_issues
                   (brand, model, year_from, year_to, engine, category, severity,
                    issue, what_to_check, negotiation_leverage_sek)
               VALUES (:brand, :model, :year_from, :year_to, :engine, :category, :severity,
                       :issue, :what_to_check, :negotiation_leverage_sek)
               ON CONFLICT(brand, model, issue) DO UPDATE SET
                   year_from=excluded.year_from, year_to=excluded.year_to,
                   engine=excluded.engine, category=excluded.category,
                   severity=excluded.severity, what_to_check=excluded.what_to_check,
                   negotiation_leverage_sek=excluded.negotiation_leverage_sek""",
            {**{k: None for k in (
                "year_from", "year_to", "engine", "category", "severity",
                "what_to_check", "negotiation_leverage_sek")}, **it},
        )
        n += 1
    conn.commit()
    return n


def _int_or_none(value):
    return None if value is None else int(round(float(value)))


def _float_or_none(value):
    return None if value is None else float(value)
