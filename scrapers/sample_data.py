"""Synthetic Blocket-style listings so the whole pipeline runs end-to-end
without touching the live site. A configurable share of cars are deliberately
underpriced so the deal-ranking has something to find.

NOTE: mileage is stored in KILOMETRES here for simplicity. Real Blocket lists
mileage in Swedish "mil" (1 mil = 10 km); convert when wiring the live scraper.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

# (brand, model, base_price_new, yearly_depreciation_factor)
MODELS = [
    ("Volvo", "V60", 380_000, 0.88),
    ("Volvo", "XC60", 480_000, 0.89),
    ("Volkswagen", "Golf", 290_000, 0.86),
    ("Volkswagen", "Passat", 360_000, 0.86),
    ("Audi", "A4", 410_000, 0.87),
    ("BMW", "3-serie", 450_000, 0.87),
    ("Toyota", "Corolla", 280_000, 0.90),
    ("Kia", "Ceed", 250_000, 0.85),
    ("Skoda", "Octavia", 300_000, 0.87),
    ("Tesla", "Model 3", 560_000, 0.85),
]

LOCATIONS = [
    ("Stockholm", "Stockholms län"), ("Göteborg", "Västra Götalands län"),
    ("Malmö", "Skåne län"), ("Linköping", "Östergötlands län"),
    ("Uppsala", "Uppsala län"), ("Norrköping", "Östergötlands län"),
    ("Västerås", "Västmanlands län"), ("Örebro", "Örebro län"),
    ("Umeå", "Västerbottens län"),
]

# First model year sold in Sweden under that name (Model 3 deliveries began 2019; the
# European Corolla hatchback replaced the Auris in 2019). Clamped, not re-drawn, so the
# random stream (and every other car) stays identical.
FIRST_YEAR = {("Tesla", "Model 3"): 2019, ("Toyota", "Corolla"): 2019}

GEARBOXES = ["Manuell", "Automat"]
COLORS = ["Svart", "Vit", "Silver", "Blå", "Grå", "Röd"]


def generate(n: int = 200, seed: int = 42, deal_share: float = 0.18,
             mileage_effect: str = "proportional") -> list[dict]:
    """Synthetic listings. Fields prefixed `_` are hidden ground truth for evaluation
    (`analysis/evaluate_valuation.py`) and are never loaded into the database.

    mileage_effect: 'proportional' (~3 % per 10 000 km above normal, the default) or
    'additive' (the original flat 0.8 kr/km, kept to test the valuer against a
    world it was not designed for)."""
    rng = random.Random(seed)
    extra = random.Random(seed + 1)   # separate stream: keeps the original 200 cars identical
    today = date.today()
    listings: list[dict] = []

    for i in range(n):
        brand, model, base_new, dep = rng.choice(MODELS)
        model_year = max(rng.randint(2013, 2022), FIRST_YEAR.get((brand, model), 0))
        age = max(0, today.year - model_year)

        fair_value = base_new * (dep ** age)
        # Realistic-ish mileage: ~1 500 mil/yr = 15 000 km/yr, with noise.
        mileage = int(rng.gauss(age * 15_000, 20_000))
        mileage = max(1_000, mileage)
        # Each 10 000 km above what is normal for the age costs ~3 % (proportional, so an
        # old cheap car can't turn negative the way the earlier flat 0.8 kr/km did).
        if mileage_effect == "additive":
            fair_value -= (mileage - age * 15_000) * 0.8
        else:
            fair_value *= math.exp(-0.03 * (mileage - age * 15_000) / 10_000)

        price = fair_value * rng.uniform(0.95, 1.06)
        injected = rng.random() < deal_share
        if injected:                                  # inject deliberate deals
            price *= rng.uniform(0.80, 0.90)

        price = max(20_000, int(round(price / 1000) * 1000))
        city, county = rng.choice(LOCATIONS)
        listed = today - timedelta(days=rng.randint(0, 45))
        gearbox, color = rng.choice(GEARBOXES), rng.choice(COLORS)
        dealer = extra.random() < 0.3

        listings.append({
            "brand": brand, "model": model, "year": model_year,
            "mileage": mileage, "price": price,
            "city": city, "county": county,
            "fuel_type": None,            # the spec table is the authority for fuel/body/etc.
            "gearbox": gearbox, "color": color,
            "url": f"https://www.blocket.se/annons/sample-{i:05d}",
            "ad_id": f"sample-{i:05d}",
            "title": f"{brand} {model} {model_year} (exempeldata)",
            "seller_type": "dealer" if dealer else "private",
            "dealer_name": "Exempelbilar AB" if dealer else None,
            "listing_date": listed,       # publish date; days on market derives from it
            "days_on_market": (today - listed).days,
            "source": "sample",
            "_fair_value": round(fair_value),
            "_injected_deal": injected,
        })

    return listings


if __name__ == "__main__":
    for row in generate(5):
        print(row)
