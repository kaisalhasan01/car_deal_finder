"""Insurance premium ESTIMATOR (heuristic).

There is no free public API for Swedish car-insurance premiums (insurers need a
personnummer, location, annual mileage, driver history, etc.). So this is a
transparent rule-of-thumb for a *helförsäkring*, driven by the factors that
actually move premiums: car value, engine power and age. Treat it as an estimate
and let the user override it with a real quote.

Rough calibration (monthly, helförsäkring):
  ~300 kr for an old cheap car, ~450–700 for a normal car, ~900+ for a powerful
  or high-value car.
"""
from __future__ import annotations

from datetime import date

BASE_TRAFFIC = 250          # trafikförsäkring floor
VALUE_RATE = 0.0011         # kr/month per SEK of car value (kasko component)
POWER_THRESHOLD_HP = 120    # power above this adds load
POWER_RATE = 1.2            # kr/month per hp above threshold


def estimate_monthly_premium(
    car_value: int | float | None,
    power_hp: int | None = None,
    year: int | None = None,
) -> int:
    """Estimated monthly helförsäkring premium in SEK (rounded to nearest 10)."""
    value = float(car_value) if car_value else 80_000.0

    monthly = BASE_TRAFFIC + value * VALUE_RATE
    if power_hp:
        monthly += max(0, power_hp - POWER_THRESHOLD_HP) * POWER_RATE

    # Older cars: lower hull value already captured via `value`; tiny age bump
    # for harder-to-source parts on the oldest cars.
    if year:
        age = max(0, date.today().year - year)
        if age >= 12:
            monthly += 40

    return int(round(monthly / 10) * 10)
