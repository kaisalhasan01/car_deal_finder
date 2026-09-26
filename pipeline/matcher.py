"""The buyer-advisor engine: turn a buyer's preferences into a ranked, annotated
shortlist of cars, with estimated total cost of ownership, a reliability read,
and an auto-generated "what to check / haggle on" briefing per car.

Flow per listing (hard filters exclude, the score ranks; the two stay separate):
  1. resolve attributes: what the ad states (fuel, AWD, hp) wins over the curated spec
  2. HARD filters: budget, mileage, year, drivetrain, body, fuel, L/100km, seller type,
     damage wording, max insurance
  3. cost model: insurance + energy + vehicle tax + repair reserve -> TCO/year
  4. score 0-100: deal (valuation z-score weighted by its confidence) + reliability
     + economy + budget headroom. Never the discount alone.
  5. briefing: known issues + negotiation room, red flags, seller-type rights,
     price drops / time on market, and history links for the registration number
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pipeline.insurance import estimate_monthly_premium
from reference.lookup import get_issues, get_spec

# Energy prices (SEK), approximate 2025–26 levels. Adjust as needed.
PETROL_PRICE = 18.5      # kr/litre
DIESEL_PRICE = 19.5      # kr/litre
E85_PRICE = 15.0         # kr/litre
ELECTRICITY_PRICE = 2.8  # kr/kWh incl. grid fee and tax (home charging)

# Typical consumption when no curated spec matches the ad's fuel (labelled as such).
TYPICAL_CONSUMPTION = {  # fuel -> (L/100km, kWh/100km, annual tax SEK)
    "Bensin": (6.5, None, 1500), "Diesel": (5.5, None, 3500), "Hybrid": (4.8, None, 1000),
    "Laddhybrid": (2.5, 10.0, 800), "El": (None, 17.0, 360), "Etanol": (9.0, None, 1500),
    "Gas": (6.5, None, 1000),
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.85, "low": 0.6}
LONG_ON_MARKET_DAYS = 45


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
    seller_types: set[str] | None = None       # {'private'} / {'dealer'}
    include_damaged: bool = False              # ads whose text mentions defects/damage
    annual_km: int = 15_000                    # for fuel/TCO (≈1 500 mil/yr)
    # Personal factors for the insurance estimate (constant across the shortlist).
    driver_age: int | None = None              # None = experienced adult
    claims_free_years: int | None = None       # None = typical; more = cheaper
    home_city: str | None = None               # owner's city (else listing city)
    # Scoring weights (need not sum to 1; normalized internally).
    weights: dict = field(default_factory=lambda: {
        "deal": 0.35, "reliability": 0.25, "economy": 0.20, "headroom": 0.20})


# ---------------------------------------------------------------------------
# Attributes and cost model
# ---------------------------------------------------------------------------
def resolve_attributes(listing: dict, spec: dict | None) -> dict:
    """What we believe about the car, and where each value came from."""
    s = spec or {}
    fuel = listing.get("fuel_type") or s.get("primary_fuel")
    spec_fits_fuel = bool(spec) and (listing.get("fuel_type") in (None, s.get("primary_fuel")))
    typical = TYPICAL_CONSUMPTION.get(fuel, (None, None, None))
    if spec_fits_fuel:
        l100, kwh100, tax = s.get("fuel_l_per_100km"), s.get("energy_kwh_per_100km"), s.get("annual_tax_sek")
        consumption_source = "spec"
    else:
        l100, kwh100, tax = typical
        consumption_source = "typical" if fuel in TYPICAL_CONSUMPTION else "unknown"
    return {
        "fuel": fuel,
        "drivetrain": listing.get("drivetrain") or s.get("drivetrain"),
        "body_type": listing.get("body_type") or s.get("body_type"),
        "power_hp": listing.get("power_hp") or s.get("power_hp"),
        "l_per_100km": l100, "kwh_per_100km": kwh100, "annual_tax_sek": tax,
        "reliability": s.get("reliability"),
        "consumption_source": consumption_source,
    }


def _energy_cost_per_year(attrs: dict, annual_km: int) -> int | None:
    fuel = (attrs.get("fuel") or "").lower()
    cost, known = 0.0, False
    if attrs.get("kwh_per_100km"):
        cost += attrs["kwh_per_100km"] / 100 * annual_km * ELECTRICITY_PRICE
        known = True
    if attrs.get("l_per_100km"):
        price = DIESEL_PRICE if fuel == "diesel" else E85_PRICE if fuel == "etanol" else PETROL_PRICE
        cost += attrs["l_per_100km"] / 100 * annual_km * price
        known = True
    return int(cost) if known else None


def _repair_reserve_per_year(reliability: int | None) -> int:
    """Yearly maintenance/repair reserve, driven by reliability (1..5)."""
    return (6 - (reliability or 3)) * 2000   # 5★ -> 2 000 kr, 2★ -> 8 000 kr


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def deal_component(listing: dict) -> float:
    """0..1. Uses deal_z (discount relative to the model's own price spread) when the
    valuation provides it, damped by how much we trust that valuation."""
    z = listing.get("deal_z")
    if z is not None:
        base = _clamp((z + 0.5) / 2.5)                                   # z=-0.5 -> 0, z=2 -> 1
    else:
        base = _clamp(((listing.get("discount_pct") or 0) + 5) / 35)    # -5 % -> 0, +30 % -> 1
    return base * CONFIDENCE_WEIGHT.get(listing.get("value_confidence"), 0.6)


def _match_score(listing: dict, attrs: dict, energy_year: int | None, profile: BuyerProfile) -> int:
    price = listing["price"]
    deal = deal_component(listing)
    reliability = (attrs.get("reliability") or 3) / 5
    economy = _clamp(1 - (energy_year if energy_year is not None else 12_000) / 20_000)
    headroom = _clamp((profile.budget_max - price) / profile.budget_max) if profile.budget_max else 0.5
    w = profile.weights
    total_w = sum(w.values()) or 1
    score = (w["deal"] * deal + w["reliability"] * reliability
             + w["economy"] * economy + w["headroom"] * headroom) / total_w
    return int(round(score * 100))


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------
def history_links(regnr: str | None) -> list[dict]:
    """Where a buyer can check owners, inspections and odometer history for a plate."""
    if not regnr:
        return []
    return [
        {"label": "car.info (historik, besiktningar, mätarställning)",
         "url": f"https://www.car.info/sv-se/license-plate/S/{regnr}"},
        {"label": "biluppgifter.se (ägare, skatt, körförbud)",
         "url": f"https://biluppgifter.se/fordon/{regnr}"},
    ]


def seller_note(seller_type: str | None) -> str | None:
    if seller_type == "dealer":
        return ("Handlare: konsumentköplagen gäller (bl.a. 3 års reklamationsrätt) — starkare skydd "
                "än privatköp. Fråga om garanti och vad som ingår.")
    if seller_type == "private":
        return ("Privatperson: köplagen gäller — bilen säljs normalt i befintligt skick och ditt "
                "skydd är svagare. Gör en köpbesiktning och kontrollera att säljaren är ägare.")
    return None


def general_checks(listing: dict, attrs: dict) -> list[str]:
    """Model-independent things every buyer should verify, driven by age, km and fuel."""
    age = max(0, date.today().year - listing["year"])
    km, fuel = listing.get("mileage"), attrs.get("fuel")
    checks = ["Be om servicebok och jämför mätarställningen med besiktningshistoriken."]
    if age >= 10:
        checks.append("Äldre bil: kolla rost (trösklar, hjulhus, bromsrör) och slitna bussningar.")
    if km is not None and km >= 150_000:
        checks.append("Höga mil: fråga om kamrem/kamkedja, koppling och stötdämpare.")
    if fuel == "Diesel" and km is not None and km >= 100_000:
        checks.append("Diesel: fråga om körmönstret — mycket kortkörning belastar DPF/EGR.")
    if fuel in ("El", "Laddhybrid"):
        checks.append("Be om en batterihälsorapport (SOH) och testa laddningen.")
    elif fuel == "Hybrid" and age >= 8:
        checks.append("Äldre hybrid: be om test av hybridbatteriet.")
    return checks


def _build_briefing(listing: dict, attrs: dict) -> dict:
    brand, model, year = listing["brand"], listing["model"], listing["year"]
    issues = sorted(get_issues(brand, model, year),
                    key=lambda it: SEVERITY_RANK.get(it.get("severity"), 0), reverse=True)
    leverage = sum(it.get("negotiation_leverage_sek") or 0 for it in issues)

    red_flags, signals = [], []
    pct, z = listing.get("discount_pct"), listing.get("deal_z")
    if (pct is not None and pct > 35) or (z is not None and z > 3.5):
        red_flags.append("Priset är ovanligt lågt för bilen — kan dölja fel eller vara bluff. "
                         "Var extra noggrann.")
    if listing.get("damage_flag"):
        red_flags.append("Annonstexten nämner fel/skada (t.ex. motorfel, reparationsobjekt).")
    mileage = listing.get("mileage")
    if mileage is not None and year is not None:
        age = max(1, date.today().year - year)
        if mileage > age * 30_000:   # > ~3 000 mil/år
            red_flags.append("Högt miltal för årsmodellen — räkna med mer slitage.")
    if listing.get("value_confidence") == "low" and (pct or 0) > 10:
        red_flags.append("Värderingen är osäker (få jämförbara bilar) — rabatten kan vara skenbar.")

    first_price, price = listing.get("first_price"), listing["price"]
    if first_price and first_price > price:
        signals.append(f"Priset har sänkts {first_price - price:,} kr sedan annonsen först sågs "
                       "— säljaren vill sälja.".replace(",", " "))
    dom = listing.get("days_on_market")
    if dom is not None and dom >= LONG_ON_MARKET_DAYS:
        signals.append(f"Legat ute i {dom} dagar — mer förhandlingsutrymme än vanligt.")

    return {
        "issues": issues, "negotiation_room_sek": leverage,
        "red_flags": red_flags, "signals": signals,
        "general_checks": general_checks(listing, attrs),
        "seller_note": seller_note(listing.get("seller_type")),
        "history_links": history_links(listing.get("regnr")),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def evaluate(listing: dict, profile: BuyerProfile) -> dict | None:
    """Enrich + score one listing. Returns None if it fails the buyer's filters.

    `listing` may carry valuation fields (market_value_sek, value_low_sek,
    value_high_sek, discount_pct, deal_z, value_confidence, value_n).
    """
    year, price, mileage = listing["year"], listing["price"], listing.get("mileage")
    spec = get_spec(listing["brand"], listing["model"], listing.get("fuel_type"))
    attrs = resolve_attributes(listing, spec)

    # --- hard filters ------------------------------------------------------
    if profile.budget_max and price > profile.budget_max:
        return None
    if profile.max_mileage and mileage is not None and mileage > profile.max_mileage:
        return None
    if profile.min_year and year < profile.min_year:
        return None
    if profile.drivetrains and attrs["drivetrain"] not in profile.drivetrains:
        return None
    if profile.body_types and attrs["body_type"] not in profile.body_types:
        return None
    if profile.fuel_types and attrs["fuel"] not in profile.fuel_types:
        return None
    if profile.max_l_per_100km and attrs["l_per_100km"] \
            and attrs["l_per_100km"] > profile.max_l_per_100km:
        return None
    if profile.seller_types and listing.get("seller_type") not in profile.seller_types:
        return None
    if not profile.include_damaged and listing.get("damage_flag"):
        return None

    # --- cost model --------------------------------------------------------
    insurance_month = estimate_monthly_premium(
        listing.get("market_value_sek") or price, power_hp=attrs["power_hp"], year=year,
        city=(profile.home_city or listing.get("city")),
        driver_age=profile.driver_age, claims_free_years=profile.claims_free_years)
    if profile.max_insurance_monthly and insurance_month > profile.max_insurance_monthly:
        return None

    energy_year = _energy_cost_per_year(attrs, profile.annual_km)
    tax_year = attrs["annual_tax_sek"] or 0
    repair_year = _repair_reserve_per_year(attrs["reliability"])
    tco_year = insurance_month * 12 + (energy_year or 0) + tax_year + repair_year

    return {
        **listing,
        "spec": spec,
        "attributes": attrs,
        "insurance_monthly": insurance_month,
        "fuel_cost_year": energy_year,
        "tax_year": tax_year,
        "repair_reserve_year": repair_year,
        "tco_year": tco_year,
        "match_score": _match_score(listing, attrs, energy_year, profile),
        "briefing": _build_briefing(listing, attrs),
    }


def attach_valuations(listings: list[dict], valuations: list) -> list[dict]:
    """Copy Valuation objects onto listing dicts (the shape `evaluate` expects)."""
    out = []
    for it, v in zip(listings, valuations):
        row = dict(it)
        if v is not None:
            row.update(market_value_sek=v.value, value_low_sek=v.low, value_high_sek=v.high,
                       discount_pct=v.discount_pct, deal_z=v.deal_z,
                       value_confidence=v.confidence, value_n=v.n, value_method=v.method)
        out.append(row)
    return out


def rank(listings: list[dict], profile: BuyerProfile, top_n: int | None = None) -> list[dict]:
    """Evaluate many listings and rank the survivors by match score."""
    results = [r for r in (evaluate(it, profile) for it in listings) if r is not None]
    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results[:top_n] if top_n else results
