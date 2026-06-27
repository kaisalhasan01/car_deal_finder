"""Insurance premium ESTIMATOR (heuristic, calibrated to real Swedish data).

There is no free public API for Swedish car-insurance premiums (insurers need a
personnummer, address, annual mileage and driver history in a form). So this is
a transparent rule-of-thumb for a *helförsäkring*, but it is CALIBRATED against
real published figures rather than guessed:

  * average helförsäkring ≈ 584 kr/month (Hedvig)              [1]
  * common range ≈ 500–830 kr/month                            [1][2]
  * Stockholm ≈ +40 % vs countryside                           [1]
  * driver under 25 ≈ ~2× the premium                          [1][2]
  * claims-free bonus up to ~55 % discount                     [1]

Sources:
  [1] Hedvig — "Vad kostar bilförsäkring?"  https://www.hedvig.com/se/forsakringar/vad-kostar-forsakring
  [2] Konsumenten.se — "Vad kostar bilförsäkring?"  https://konsumenten.se/forsakring/bilforsakring/vad-kostar-bilforsakring/

Defaults (no city/age/bonus given) represent a typical experienced adult driver,
and land near the ~584 kr/month national average for a normal car. The result is
an ESTIMATE — let the user override it with a real quote.
"""
from __future__ import annotations

from datetime import date

# Base model — calibrated so a ~150 000 kr / 150 hp car ≈ 555 kr/month.
BASE = 300
VALUE_RATE = 0.0014          # kr/month per SEK of car value (kasko component)
POWER_THRESHOLD_HP = 120
POWER_RATE = 1.5             # kr/month per hp above threshold

# Location loading (owner's city). National-average base already bakes in cities,
# so these are modest relative loadings.
CITY_MULTIPLIER = {
    "stockholm": 1.20, "göteborg": 1.10, "goteborg": 1.10, "malmö": 1.10, "malmo": 1.10,
}


def _location_multiplier(city: str | None) -> float:
    if not city:
        return 1.0
    return CITY_MULTIPLIER.get(str(city).strip().lower(), 1.0)


def _age_multiplier(driver_age: int | None) -> float:
    if driver_age is None:
        return 1.0                      # assume experienced adult
    if driver_age < 25:
        return 1.8
    if driver_age < 30:
        return 1.3
    if driver_age >= 65:
        return 1.1
    return 1.0


def _bonus_multiplier(claims_free_years: int | None) -> float:
    """5 claims-free years ≈ typical (1.0). Fewer costs more, more is cheaper."""
    if claims_free_years is None:
        return 1.0
    return max(0.55, min(1.4, 1.4 - 0.08 * claims_free_years))


def estimate_monthly_premium(
    car_value: int | float | None,
    power_hp: int | None = None,
    year: int | None = None,
    city: str | None = None,
    driver_age: int | None = None,
    claims_free_years: int | None = None,
) -> int:
    """Estimated monthly helförsäkring premium (SEK, rounded to nearest 10)."""
    value = float(car_value) if car_value else 80_000.0

    monthly = BASE + value * VALUE_RATE
    if power_hp:
        monthly += max(0, power_hp - POWER_THRESHOLD_HP) * POWER_RATE
    if year and (date.today().year - year) >= 12:
        monthly += 40                   # older car: harder-to-source parts

    monthly *= _location_multiplier(city)
    monthly *= _age_multiplier(driver_age)
    monthly *= _bonus_multiplier(claims_free_years)

    return int(round(monthly / 10) * 10)
