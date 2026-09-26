"""REST API for the Car Deal Finder.

    uvicorn api.main:app --port 8000          # docs at http://localhost:8000/docs

Reads the database named by the CAR_DEALS_DB environment variable (default
car_deals.db). Without real data it serves a demo market, and every response says so
(`"demo": true`).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from pipeline import service
from pipeline.matcher import BuyerProfile
from reference.known_issues_data import ISSUES
from reference.lookup import get_issues
from reference.specs_data import SPECS

API_VERSION = "2.0.0"
app = FastAPI(
    title="Swedish Car Deal Finder API",
    version=API_VERSION,
    description=(
        "Personal used-car advisor for Blocket: market valuation (hierarchical hedonic model), "
        "buyer-profile matching with total cost of ownership, and a known-issues briefing. "
        "Values are **estimates** from comparable asking prices, not transaction prices."),
)


def _db_path() -> Path:
    return Path(os.environ.get("CAR_DEALS_DB", db.DEFAULT_DB_PATH))


def _market() -> service.Market:
    return service.load_market(_db_path(), allow_demo=os.environ.get("CAR_DEALS_NO_DEMO") != "1")


@contextmanager
def _conn():
    market = _market()
    if market.db_path is None:
        raise HTTPException(503, "No database with listings yet — run the ETL "
                                 "(python -m pipeline.run --source blocket ...).")
    conn = db.connect(market.db_path)
    try:
        yield conn
    finally:
        conn.close()


def _envelope(market: service.Market, **payload) -> dict:
    return {"data": market.label, "demo": market.demo, **payload}


# ------------------------------------------------------------------ schemas
class ProfileIn(BaseModel):
    budget_max: int | None = Field(None, examples=[220_000], description="max asking price, SEK")
    max_mileage_km: int | None = Field(None, examples=[150_000])
    min_year: int | None = Field(None, examples=[2016])
    drivetrains: list[Literal["FWD", "RWD", "AWD"]] | None = None
    body_types: list[str] | None = Field(None, examples=[["Kombi", "SUV"]])
    fuel_types: list[str] | None = Field(None, examples=[["Diesel", "Hybrid"]])
    max_l_per_100km: float | None = None
    max_insurance_monthly: int | None = Field(None, examples=[800])
    seller_types: list[Literal["private", "dealer"]] | None = None
    include_damaged: bool = False
    annual_km: int = 15_000
    driver_age: int | None = None
    claims_free_years: int | None = None
    home_city: str | None = None
    top_n: int = Field(10, ge=1, le=100)

    def to_profile(self) -> BuyerProfile:
        as_set = lambda v: set(v) if v else None       # noqa: E731
        return BuyerProfile(
            budget_max=self.budget_max, max_mileage=self.max_mileage_km, min_year=self.min_year,
            drivetrains=as_set(self.drivetrains), body_types=as_set(self.body_types),
            fuel_types=as_set(self.fuel_types), max_l_per_100km=self.max_l_per_100km,
            max_insurance_monthly=self.max_insurance_monthly, seller_types=as_set(self.seller_types),
            include_damaged=self.include_damaged, annual_km=self.annual_km,
            driver_age=self.driver_age, claims_free_years=self.claims_free_years,
            home_city=self.home_city)


class CarIn(BaseModel):
    brand: str = Field(..., examples=["Audi"])
    model: str = Field(..., examples=["A4"])
    year: int = Field(..., examples=[2011])
    mileage_km: int | None = Field(None, examples=[200_000])
    price: int | None = Field(None, examples=[50_000], description="asking price, for the discount")
    fuel_type: str | None = None
    gearbox: Literal["Automat", "Manuell"] | None = None
    seller_type: Literal["private", "dealer"] | None = None
    drivetrain: Literal["FWD", "RWD", "AWD"] | None = None


# ------------------------------------------------------------------ routes
@app.get("/health", tags=["meta"])
def health():
    market = _market()
    last_run = None
    if market.db_path:
        with _conn() as conn:
            row = conn.execute("SELECT * FROM etl_runs ORDER BY run_id DESC LIMIT 1").fetchone()
            last_run = dict(row) if row else None
    return _envelope(market, status="ok", api_version=API_VERSION,
                     schema_version=db.SCHEMA_VERSION, active_listings=len(market.listings),
                     last_run=last_run)


@app.post("/recommend", tags=["advisor"])
def recommend(profile: ProfileIn):
    """Ranked shortlist for a buyer profile. The score blends deal, reliability, economy and
    budget headroom, never the discount alone."""
    market = _market()
    results = service.recommend(market, profile.to_profile(), top_n=profile.top_n)
    # Keep the payload lean, and never leak the demo generator's hidden ground truth (_*).
    results = [{k: v for k, v in r.items() if not k.startswith("_") and k not in ("spec", "lat", "lon")}
               for r in results]
    return _envelope(market, count=len(results), results=results)


@app.post("/valuate", tags=["advisor"])
def valuate(car: CarIn):
    """Market value of any car against current Blocket comparables, with an 80 % interval."""
    market = _market()
    result = service.valuate(market, {**car.model_dump(), "mileage": car.mileage_km})
    if result is None:
        raise HTTPException(422, "Not enough market data to value this car yet.")
    return _envelope(market, valuation=result,
                     known_issues=get_issues(car.brand, car.model, car.year))


@app.get("/listings", tags=["market"])
def listings(brand: str | None = None, model: str | None = None,
             max_price: int | None = None, min_year: int | None = None,
             max_mileage_km: int | None = None, county: str | None = None,
             seller_type: Literal["private", "dealer"] | None = None,
             sort: Literal["deal_z", "discount_pct", "price_sek", "published_date"] = "deal_z",
             limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Active listings from the database, filterable and sortable."""
    where, params = ["is_active = 1"], []
    for col, val in (("lower(brand)", brand and brand.lower()), ("lower(model)", model and model.lower()),
                     ("county", county), ("seller_type", seller_type)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    for clause, val in (("price_sek <= ?", max_price), ("model_year >= ?", min_year),
                        ("mileage_km <= ?", max_mileage_km)):
        if val is not None:
            where.append(clause)
            params.append(val)
    order = "price_sek ASC" if sort == "price_sek" else f"{sort} DESC"
    sql_where = " AND ".join(where)
    with _conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM vw_listings WHERE {sql_where}", params).fetchone()[0]
        rows = conn.execute(f"SELECT * FROM vw_listings WHERE {sql_where} ORDER BY {order} "
                            "NULLS LAST LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return _envelope(_market(), total=total, items=[dict(r) for r in rows])


@app.get("/listings/{listing_id}", tags=["market"])
def listing(listing_id: int):
    """One listing with its known-issue briefing and price history."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM vw_listings WHERE listing_id = ?", (listing_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "listing not found")
        issues = conn.execute("SELECT * FROM vw_listing_issues WHERE listing_id = ?",
                              (listing_id,)).fetchall()
        history = conn.execute("SELECT date, price_sek FROM vw_price_history WHERE listing_id = ? "
                               "ORDER BY date", (listing_id,)).fetchall()
    return _envelope(_market(), listing=dict(row), issues=[dict(r) for r in issues],
                     price_history=[dict(r) for r in history])


@app.get("/market/models", tags=["market"])
def market_models():
    """Per-model overview: supply, average price, discount, time on market, dealer share."""
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM vw_model_market ORDER BY active_listings DESC").fetchall()
    return _envelope(_market(), items=[dict(r) for r in rows])


@app.get("/market/deals", tags=["market"])
def market_deals(limit: int = Query(25, ge=1, le=200)):
    """Credible deals: active, no damage wording, trustworthy valuation, ≥ 5 % below value."""
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM vw_deal_board ORDER BY deal_z DESC LIMIT ?",
                            (limit,)).fetchall()
    return _envelope(_market(), items=[dict(r) for r in rows])


@app.get("/market/depreciation", tags=["market"])
def depreciation(brand: str, model: str, km_per_year: int = 15_000):
    """Typical value by age for a model, plus the latest fitted summary."""
    market = _market()
    summary = next((s for s in market.valuer.summaries()
                    if s["level"] == "model" and s["brand"].lower() == brand.lower()
                    and s["model"].lower() == model.lower()), None)
    return _envelope(market, summary=summary,
                     curve=service.model_curve(market, brand, model, km_per_year))


@app.get("/reference/specs", tags=["reference"])
def reference_specs():
    return {"items": SPECS, "note": "Approximate, representative values per model/fuel variant."}


@app.get("/reference/issues", tags=["reference"])
def reference_issues(brand: str | None = None, model: str | None = None, year: int | None = None):
    items = get_issues(brand, model, year) if brand and model else ISSUES
    return {"items": items, "note": "Indicative community-known faults — verify on the actual car."}
