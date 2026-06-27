"""The buyer-advisor engine: turn a buyer's preferences into a ranked, annotated
shortlist of cars — with estimated total cost of ownership, a reliability read,
and an auto-generated "what to check / haggle on" briefing per car.

Flow per listing:
  1. enrich with reference spec (drivetrain, body, economy, power, tax, reliability)
  2. estimate insurance, yearly fuel, vehicle tax, repair reserve -> TCO/year
  3. apply the buyer's HARD filters (budget, mileage, year, drivetrain, body,
     economy, fuel, max insurance)
  4. score 0-100 (deal + reliability + economy + budget headroom)
  5. build the known-issues briefing + red flags + negotiation room
"""
from __future__ import annotations

from dataclasses import dataclass, field

from reference.lookup import get_issues, get_spec
from pipeline.insurance import estimate_monthly_premium

# Energy prices (SEK) — adjust as needed.
PETROL_PRICE = 18.5      # kr/litre
DIESEL_PRICE = 19.5      # kr/litre
ELECTRICITY_PRICE = 2.8  # kr/kWh

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass
class BuyerProfile:
    """All constraints are optional — None/empty means 'no preference'."""
    budget_max: int | None = None              # max asking price (SEK)
    max_mileage: int | None = None             # km
    min_year: int | None = None
    drivetrains: set[str] | None = None        # {'AWD'}, {'FWD','AWD'} ...
    body_types: set[str] | None = None         # {'Kombi','SUV'} ...
    fuel_types: set[str] | None = None         # {'Diesel','El'} ...
    max_l_per_100km: float | None = None       # economy ceiling (combustion)
    max_insurance_monthly: int | None = None   # SEK/month
    annual_km: int = 15_000                    # for fuel/TCO (≈1 500 mil/yr)
    # Scoring weights (need not sum to 1; normalized internally).
    weights: dict = field(default_factory=lambda: {
        "deal": 0.35, "reliability": 0.25, "economy": 0.20, "headroom": 0.20})


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------
def _fuel_cost_per_year(spec: dict | None, annual_km: int) -> int | None:
    if not spec:
        return None
    fuel = (spec.get("primary_fuel") or "").lower()
    if spec.get("energy_kwh_per_100km"):
        return int(spec["energy_kwh_per_100km"] / 100 * annual_km * ELECTRICITY_PRICE)
    if spec.get("fuel_l_per_100km"):
        price = DIESEL_PRICE if fuel == "diesel" else PETROL_PRICE
        return int(spec["fuel_l_per_100km"] / 100 * annual_km * price)
    return None


def _repair_reserve_per_year(spec: dict | None) -> int:
    """Yearly maintenance/repair reserve, driven by reliability (1..5)."""
    reliability = (spec or {}).get("reliability") or 3
    return (6 - reliability) * 2000   # 5★ -> 2 000 kr, 2★ -> 8 000 kr


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _match_score(deal_pct, spec, fuel_year, price, profile) -> int:
    deal = _clamp(((deal_pct or 0) + 5) / 35)                  # -5%→0, 30%→1
    reliability = ((spec or {}).get("reliability") or 3) / 5
    economy = _clamp(1 - (fuel_year or 12_000) / 20_000)        # 0 kr→1, 20k→0
    headroom = _clamp((profile.budget_max - price) / profile.budget_max) if profile.budget_max else 0.5

    w = profile.weights
    total_w = sum(w.values()) or 1
    score = (w["deal"] * deal + w["reliability"] * reliability
             + w["economy"] * economy + w["headroom"] * headroom) / total_w
    return int(round(score * 100))


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------
def _build_briefing(brand, model, year, deal_pct, mileage, spec) -> dict:
    issues = sorted(
        get_issues(brand, model, year),
        key=lambda it: SEVERITY_RANK.get(it.get("severity"), 0), reverse=True,
    )
    leverage = sum(it.get("negotiation_leverage_sek") or 0 for it in issues)

    red_flags = []
    if deal_pct is not None and deal_pct > 35:
        red_flags.append("Priset är ovanligt lågt — kan dölja fel eller vara bluff. Var extra noggrann.")
    if mileage is not None and year is not None:
        from datetime import date
        age = max(1, date.today().year - year)
        if mileage > age * 30_000:   # > ~3 000 mil/år
            red_flags.append("Högt miltal för årsmodellen — räkna med mer slitage.")

    return {"issues": issues, "negotiation_room_sek": leverage, "red_flags": red_flags}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def evaluate(listing: dict, deal_value: int | None, deal_pct: float | None,
             profile: BuyerProfile) -> dict | None:
    """Enrich + score one listing. Returns None if it fails the buyer's filters."""
    brand, model, year = listing["brand"], listing["model"], listing["year"]
    price, mileage = listing["price"], listing.get("mileage")
    spec = get_spec(brand, model)

    # --- hard filters ------------------------------------------------------
    if profile.budget_max and price > profile.budget_max:
        return None
    if profile.max_mileage and mileage is not None and mileage > profile.max_mileage:
        return None
    if profile.min_year and year < profile.min_year:
        return None
    if profile.drivetrains and (not spec or spec.get("drivetrain") not in profile.drivetrains):
        return None
    if profile.body_types and (not spec or spec.get("body_type") not in profile.body_types):
        return None
    if profile.fuel_types and (not spec or spec.get("primary_fuel") not in profile.fuel_types):
        return None
    if profile.max_l_per_100km and spec and spec.get("fuel_l_per_100km") \
            and spec["fuel_l_per_100km"] > profile.max_l_per_100km:
        return None

    # --- cost model --------------------------------------------------------
    car_value = deal_value or price
    insurance_month = estimate_monthly_premium(
        car_value, power_hp=(spec or {}).get("power_hp"), year=year)
    if profile.max_insurance_monthly and insurance_month > profile.max_insurance_monthly:
        return None

    fuel_year = _fuel_cost_per_year(spec, profile.annual_km)
    tax_year = (spec or {}).get("annual_tax_sek") or 0
    repair_year = _repair_reserve_per_year(spec)
    tco_year = insurance_month * 12 + (fuel_year or 0) + tax_year + repair_year

    score = _match_score(deal_pct, spec, fuel_year, price, profile)
    briefing = _build_briefing(brand, model, year, deal_pct, mileage, spec)

    return {
        **listing,
        "carinfo_value": deal_value,
        "discount_pct": deal_pct,
        "spec": spec,
        "insurance_monthly": insurance_month,
        "fuel_cost_year": fuel_year,
        "tax_year": tax_year,
        "repair_reserve_year": repair_year,
        "tco_year": tco_year,
        "match_score": score,
        "briefing": briefing,
    }


def rank(listings_with_deals: list[tuple[dict, int | None, float | None]],
         profile: BuyerProfile, top_n: int | None = None) -> list[dict]:
    """Evaluate many (listing, deal_value, deal_pct) tuples and rank by score."""
    results = []
    for listing, value, pct in listings_with_deals:
        r = evaluate(listing, value, pct, profile)
        if r is not None:
            results.append(r)
    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results[:top_n] if top_n else results
