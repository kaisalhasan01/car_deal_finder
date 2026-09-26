"""SQLite access layer for the Swedish Car Deal Finder (schema v2).

Responsibilities:
  * create/verify the schema and views (`init_db`, schema version in PRAGMA user_version)
  * keep a continuous calendar dimension (`ensure_dates`)
  * upsert listings into the star schema with price snapshots (`upsert_listings`)
  * mark ads that disappeared from a fully-scanned search as inactive (`deactivate_missing`)
  * store valuations, model summaries and a run log
  * read listings back for the advisor, API and valuation (`fetch_listings`)
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "car_deals.db"            # real Blocket data
SAMPLE_DB_PATH = PROJECT_ROOT / "car_deals_sample.db"      # synthetic demo data
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
VIEWS_PATH = Path(__file__).resolve().parent / "views.sql"
SCHEMA_VERSION = 2

MONTHS_SV = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti",
             "september", "oktober", "november", "december"]
WEEKDAYS_SV = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]


class SchemaVersionError(RuntimeError):
    pass


class MixedSourceError(RuntimeError):
    pass


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables + views. Refuses to touch a database from an older schema."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    has_tables = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='fact_listings'"
    ).fetchone()[0]
    if has_tables and version != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Database schema v{version or 1} found, v{SCHEMA_VERSION} required. v1 databases only "
            "ever held sample data: delete the .db file or run the pipeline with --rebuild.")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.executescript(VIEWS_PATH.read_text(encoding="utf-8"))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def date_id(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def ensure_dates(conn: sqlite3.Connection, start: date, end: date) -> None:
    """Fill dim_date with every day in [start, end] (a continuous calendar)."""
    if start > end:
        start, end = end, start
    rows, d = [], start
    while d <= end:
        iso = d.isocalendar()
        rows.append((date_id(d), d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month,
                     MONTHS_SV[d.month - 1], iso[1], iso[2], WEEKDAYS_SV[iso[2] - 1],
                     1 if iso[2] >= 6 else 0))
        d += timedelta(days=1)
    conn.executemany(
        """INSERT OR IGNORE INTO dim_date (date_id, date, year, quarter, month, month_name,
                                          iso_week, weekday, weekday_name, is_weekend)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows)


# ---------------------------------------------------------------------------
# Dimensions (get-or-create with a per-connection cache)
# ---------------------------------------------------------------------------
def _clean(value, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


class _DimCache:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cache: dict[tuple, int] = {}

    def get(self, table: str, id_col: str, cols: tuple[str, ...], values: tuple) -> int:
        key = (table, *values)
        if key in self.cache:
            return self.cache[key]
        where = " AND ".join(f"{c}=?" for c in cols)
        self.conn.execute(
            f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            values)
        row = self.conn.execute(f"SELECT {id_col} FROM {table} WHERE {where}", values).fetchone()
        self.cache[key] = row[0]
        return row[0]


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------
def existing_sources(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT source FROM fact_listings")}


def check_source(conn: sqlite3.Connection, source: str, allow_mixed: bool = False) -> None:
    """Never let synthetic and real listings share a database (they would mix in Power BI)."""
    other = existing_sources(conn) - {source}
    if other and not allow_mixed:
        raise MixedSourceError(
            f"This database already holds '{', '.join(sorted(other))}' listings; refusing to add "
            f"'{source}'. Use a separate --db (sample data defaults to car_deals_sample.db).")


def upsert_listings(conn: sqlite3.Connection, records: Iterable[dict], *, source: str,
                    scope: str, today: date, spec_ids: dict | None = None) -> dict:
    """Insert new ads / update known ones (by URL), and snapshot today's price.

    Keeps first_seen and first_price; refreshes everything else. Returns counts.
    """
    records = list(records)
    dims = _DimCache(conn)
    today_id = date_id(today)
    stats = {"loaded": 0, "new": 0, "price_changes": 0}
    published_dates = [_as_date(r["listing_date"]) for r in records if r.get("listing_date")]
    ensure_dates(conn, min([today, *published_dates]), max([today, *published_dates]))
    for rec in records:
        car_id = dims.get("dim_car", "car_id",
                          ("brand", "model", "model_year", "fuel_type", "gearbox"),
                          (str(rec["brand"]).strip(), str(rec["model"]).strip(), int(rec["year"]),
                           _clean(rec.get("fuel_type")), _clean(rec.get("gearbox"))))
        location_id = dims.get("dim_location", "location_id", ("city", "county"),
                               (_clean(rec.get("city")), _clean(rec.get("county"))))
        seller_id = dims.get("dim_seller", "seller_id", ("seller_type", "dealer_name"),
                             (_clean(rec.get("seller_type")), _clean(rec.get("dealer_name"), "")))
        published = _as_date(rec["listing_date"]) if rec.get("listing_date") else None
        days_on_market = max(0, (today - published).days) if published else None
        price = int(rec["price"])
        prev = conn.execute("SELECT listing_id, price_sek FROM fact_listings WHERE url=?",
                            (rec["url"],)).fetchone()
        values = {
            "source": source, "ad_id": rec.get("ad_id"), "url": rec["url"], "car_id": car_id,
            "location_id": location_id, "seller_id": seller_id,
            "spec_id": (spec_ids or {}).get(rec["url"]),
            "published_date_id": date_id(published) if published else None,
            "last_seen_date_id": today_id, "is_active": 1,
            "title": rec.get("title"), "model_spec": rec.get("model_spec"),
            "regnr": rec.get("regnr"), "color": rec.get("color"), "body_type": rec.get("body_type"),
            "drivetrain": rec.get("drivetrain"), "power_hp": rec.get("power_hp"),
            "mileage_km": rec.get("mileage"), "price_sek": price,
            "damage_flag": int(bool(rec.get("damage_flag"))), "days_on_market": days_on_market,
            "lat": rec.get("lat"), "lon": rec.get("lon"), "image_url": rec.get("image_url"),
            "scope": scope,
        }
        if prev is None:
            values.update(first_seen_date_id=today_id, first_price_sek=price)
            cols = ", ".join(values)
            conn.execute(f"INSERT INTO fact_listings ({cols}) VALUES "
                         f"({', '.join(':' + k for k in values)})", values)
            listing_id = conn.execute("SELECT listing_id FROM fact_listings WHERE url=?",
                                      (rec["url"],)).fetchone()[0]
            stats["new"] += 1
        else:
            listing_id = prev["listing_id"]
            if prev["price_sek"] != price:
                stats["price_changes"] += 1
            conn.execute(f"UPDATE fact_listings SET {', '.join(f'{k}=:{k}' for k in values)} "
                         "WHERE listing_id=:listing_id", {**values, "listing_id": listing_id})
        conn.execute("INSERT OR REPLACE INTO fact_price_snapshots (listing_id, date_id, price_sek) "
                     "VALUES (?, ?, ?)", (listing_id, today_id, price))
        stats["loaded"] += 1
    conn.commit()
    return stats


def deactivate_missing(conn: sqlite3.Connection, scope: str, today: date) -> int:
    """Mark ads of a *completely scanned* search that weren't seen today as inactive."""
    cur = conn.execute(
        "UPDATE fact_listings SET is_active = 0 WHERE scope = ? AND last_seen_date_id < ? "
        "AND is_active = 1", (scope, date_id(today)))
    conn.commit()
    return cur.rowcount


def write_valuations(conn: sqlite3.Connection, rows: Iterable[tuple[int, object]]) -> int:
    """rows: (listing_id, Valuation | None)."""
    n = 0
    for listing_id, v in rows:
        if v is None:
            conn.execute("""UPDATE fact_listings SET market_value_sek=NULL, value_low_sek=NULL,
                            value_high_sek=NULL, discount_pct=NULL, deal_z=NULL, value_method=NULL,
                            value_confidence=NULL, value_n=NULL WHERE listing_id=?""", (listing_id,))
            continue
        conn.execute(
            """UPDATE fact_listings SET market_value_sek=?, value_low_sek=?, value_high_sek=?,
                   discount_pct=?, deal_z=?, value_method=?, value_confidence=?, value_n=?
               WHERE listing_id=?""",
            (v.value, v.low, v.high, v.discount_pct, v.deal_z, v.method, v.confidence, v.n,
             listing_id))
        n += 1
    conn.commit()
    return n


def write_valuation_models(conn: sqlite3.Connection, summaries: list[dict], fitted: date) -> int:
    did = date_id(fitted)
    ensure_dates(conn, fitted, fitted)
    conn.execute("DELETE FROM valuation_models WHERE fitted_date_id=?", (did,))
    conn.executemany(
        """INSERT INTO valuation_models (fitted_date_id, level, brand, model, n_listings,
               value_age3_sek, value_age8_sek, depreciation_pct_per_year,
               mileage_effect_pct_per_10k_km, residual_sd_pct)
           VALUES (:fitted_date_id, :level, :brand, :model, :n_listings, :value_age3_sek,
                   :value_age8_sek, :depreciation_pct_per_year, :mileage_effect_pct_per_10k_km,
                   :residual_sd_pct)""",
        [{**s, "fitted_date_id": did} for s in summaries])
    conn.commit()
    return len(summaries)


def log_run(conn: sqlite3.Connection, **fields) -> int:
    cols = ", ".join(fields)
    cur = conn.execute(f"INSERT INTO etl_runs ({cols}) VALUES ({', '.join('?' * len(fields))})",
                       tuple(fields.values()))
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Reading back
# ---------------------------------------------------------------------------
LISTING_COLUMNS = """
    v.listing_id, v.source, v.ad_id, v.url, v.is_active, v.brand, v.model,
    v.model_year AS year, v.fuel_type, v.gearbox, v.city, v.county, v.seller_type,
    v.dealer_name, v.published_date AS listing_date, v.first_seen_date, v.last_seen_date,
    v.title, v.model_spec, v.regnr, v.color, v.mileage_km AS mileage, v.price_sek AS price,
    v.first_price_sek AS first_price, v.market_value_sek, v.value_low_sek, v.value_high_sek,
    v.discount_pct, v.deal_z, v.value_method, v.value_confidence, v.value_n, v.damage_flag,
    v.days_on_market, v.body_type AS listing_body_type, v.drivetrain AS listing_drivetrain,
    v.power_hp AS listing_power_hp, v.lat, v.lon, v.image_url
"""


def fetch_listings(conn: sqlite3.Connection, *, active_only: bool = True,
                   seen_since: date | None = None, source: str | None = None) -> list[dict]:
    """Listings as plain dicts in the shape the valuer/matcher use."""
    where, params = [], []
    if active_only:
        where.append("v.is_active = 1")
    if seen_since:
        where.append("v.last_seen_date >= ?")
        params.append(seen_since.isoformat())
    if source:
        where.append("v.source = ?")
        params.append(source)
    sql = f"SELECT {LISTING_COLUMNS} FROM vw_listings v"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = [dict(r) for r in conn.execute(sql, params)]
    for r in rows:
        # fact_listings stores what the ad said; the view falls back to specs. Keep only
        # ad-stated values so the matcher can tell the two apart.
        r["drivetrain"] = r.pop("listing_drivetrain")
        r["body_type"] = r.pop("listing_body_type")
        r["power_hp"] = r.pop("listing_power_hp")
        r["seller_type"] = None if r["seller_type"] == "unknown" else r["seller_type"]
        r["dealer_name"] = r["dealer_name"] or None
        for key in ("fuel_type", "gearbox"):
            r[key] = None if r[key] == "unknown" else r[key]
    return rows


# ---------------------------------------------------------------------------
# Reference-data load (specs + known issues)
# ---------------------------------------------------------------------------
SPEC_FIELDS = ("body_type", "drivetrain", "power_hp", "primary_fuel", "fuel_l_per_100km",
               "energy_kwh_per_100km", "annual_tax_sek", "reliability", "is_default")


def load_specs(conn: sqlite3.Connection, specs: Iterable[dict]) -> int:
    n = 0
    for s in specs:
        row = {**{k: None for k in SPEC_FIELDS}, "is_default": 1, **s}
        conn.execute(
            """INSERT INTO car_specs
                   (brand, model, body_type, drivetrain, power_hp, primary_fuel,
                    fuel_l_per_100km, energy_kwh_per_100km, annual_tax_sek, reliability, is_default)
               VALUES (:brand, :model, :body_type, :drivetrain, :power_hp, :primary_fuel,
                       :fuel_l_per_100km, :energy_kwh_per_100km, :annual_tax_sek, :reliability,
                       :is_default)
               ON CONFLICT(brand, model, primary_fuel) DO UPDATE SET
                   body_type=excluded.body_type, drivetrain=excluded.drivetrain,
                   power_hp=excluded.power_hp, fuel_l_per_100km=excluded.fuel_l_per_100km,
                   energy_kwh_per_100km=excluded.energy_kwh_per_100km,
                   annual_tax_sek=excluded.annual_tax_sek, reliability=excluded.reliability,
                   is_default=excluded.is_default""",
            {k: row[k] for k in ("brand", "model", *SPEC_FIELDS)})
        n += 1
    conn.commit()
    return n


def spec_id_map(conn: sqlite3.Connection) -> dict[tuple[str, str, str], int]:
    return {(r["brand"].lower(), r["model"].lower(), r["primary_fuel"]): r["spec_id"]
            for r in conn.execute("SELECT spec_id, brand, model, primary_fuel FROM car_specs")}


def load_known_issues(conn: sqlite3.Connection, issues: Iterable[dict]) -> int:
    from reference.lookup import issue_fuels   # same fuel logic as the Python briefing

    n = 0
    for it in issues:
        fuels = issue_fuels(it.get("engine"))
        conn.execute(
            """INSERT INTO known_issues
                   (brand, model, year_from, year_to, engine, category, severity,
                    issue, what_to_check, negotiation_leverage_sek, applies_to_fuels)
               VALUES (:brand, :model, :year_from, :year_to, :engine, :category, :severity,
                       :issue, :what_to_check, :negotiation_leverage_sek, :applies_to_fuels)
               ON CONFLICT(brand, model, issue) DO UPDATE SET
                   year_from=excluded.year_from, year_to=excluded.year_to,
                   engine=excluded.engine, category=excluded.category,
                   severity=excluded.severity, what_to_check=excluded.what_to_check,
                   negotiation_leverage_sek=excluded.negotiation_leverage_sek,
                   applies_to_fuels=excluded.applies_to_fuels""",
            {**{k: None for k in (
                "year_from", "year_to", "engine", "category", "severity",
                "what_to_check", "negotiation_leverage_sek")}, **it,
             "applies_to_fuels": ",".join(sorted(fuels)) if fuels else None},
        )
        n += 1
    conn.commit()
    return n
