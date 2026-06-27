"""Synthetic Blocket-style listings so the whole pipeline runs end-to-end
without touching the live site. A configurable share of cars are deliberately
underpriced so the deal-ranking has something to find.

NOTE: mileage is stored in KILOMETRES here for simplicity. Real Blocket lists
mileage in Swedish "mil" (1 mil = 10 km); convert when wiring the live scraper.
"""
from __future__ import annotations

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

GEARBOXES = ["Manuell", "Automat"]
COLORS = ["Svart", "Vit", "Silver", "Blå", "Grå", "Röd"]


def generate(n: int = 200, seed: int = 42, deal_share: float = 0.18) -> list[dict]:
    rng = random.Random(seed)
    today = date.today()
    listings: list[dict] = []

    for i in range(n):
        brand, model, base_new, dep = rng.choice(MODELS)
        model_year = rng.randint(2013, 2022)
        age = max(0, today.year - model_year)

        fair_value = base_new * (dep ** age)
        # Realistic-ish mileage: ~1 500 mil/yr = 15 000 km/yr, with noise.
        mileage = int(rng.gauss(age * 15_000, 20_000))
        mileage = max(1_000, mileage)
        fair_value -= (mileage - age * 15_000) * 0.8

        price = fair_value * rng.uniform(0.95, 1.06)
        if rng.random() < deal_share:                 # inject deliberate deals
            price *= rng.uniform(0.80, 0.90)

        price = max(20_000, int(round(price / 1000) * 1000))
        city, county = rng.choice(LOCATIONS)
        listed = today - timedelta(days=rng.randint(0, 45))

        listings.append({
            "brand": brand, "model": model, "year": model_year,
            "mileage": mileage, "price": price,
            "city": city, "county": county,
            "fuel_type": None,            # the spec table is the authority for fuel/body/etc.
            "gearbox": rng.choice(GEARBOXES), "color": rng.choice(COLORS),
            "url": f"https://www.blocket.se/annons/sample-{i:05d}",
            "listing_date": today, "days_on_market": (today - listed).days,
        })

    return listings


if __name__ == "__main__":
    for row in generate(5):
        print(row)
