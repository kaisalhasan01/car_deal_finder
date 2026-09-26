"""LEGACY cohort-median valuer, kept as the baseline in analysis/evaluate_valuation.py.

The production valuer is `pipeline/valuation.py` (hierarchical hedonic regression).
This version pools all model years whenever a (brand, model, year) cohort has
fewer than 3 prices, which biased discounts by age (HANDOFF §8.1).

  1. car.info lookup by registration number (stub, off by default). Since 2025 Blocket
     ads do carry `regno`, so a licensed valuation source can plug in here.
  2. Comparables fallback: median price of the same brand+model+year cohort,
     adjusted by a flat 1 kr/km.

estimate() -> (value:int|None, method:'carinfo'|'comparables'|None)
"""
from __future__ import annotations

import statistics
from collections import defaultdict

MILEAGE_DEPRECIATION_PER_KM = 1.0   # SEK lost per extra km vs cohort median
MIN_COHORT_SIZE = 3


class CarInfoValuer:
    def __init__(self, listings: list[dict], enable_carinfo: bool = False):
        self.enable_carinfo = enable_carinfo
        self._cohorts = self._build_cohorts(listings)

    def estimate(self, car: dict) -> tuple[int | None, str | None]:
        if self.enable_carinfo and car.get("regnr"):
            value = self._lookup_carinfo(car["regnr"])
            if value is not None:
                return value, "carinfo"
        value = self._comparable_value(car)
        if value is not None:
            return value, "comparables"
        return None, None

    def _lookup_carinfo(self, regnr: str) -> int | None:
        """Best-effort car.info valuation by regnr. Stub: returns None today.
        car.info has no public valuation API and blocks scrapers — implement here
        later (politely, after checking their ToS) if you obtain regnr data."""
        return None

    def _comparable_value(self, car: dict) -> int | None:
        brand, model, year = _norm(car.get("brand")), _norm(car.get("model")), car.get("year")
        for key in (("bmy", brand, model, year), ("bm", brand, model, None), ("by", brand, None, year)):
            cohort = self._cohorts.get(key)
            if cohort and len(cohort["prices"]) >= MIN_COHORT_SIZE:
                base = statistics.median(cohort["prices"])
                return int(round(self._adjust_for_mileage(base, car.get("mileage"), cohort["median_mileage"])))
        return None

    @staticmethod
    def _adjust_for_mileage(base_price: float, mileage, cohort_mileage) -> float:
        if mileage is None or cohort_mileage is None:
            return base_price
        return base_price + (cohort_mileage - mileage) * MILEAGE_DEPRECIATION_PER_KM

    @staticmethod
    def _build_cohorts(listings: list[dict]) -> dict:
        buckets: dict[tuple, dict] = defaultdict(lambda: {"prices": [], "mileages": []})
        for it in listings:
            brand, model, year = _norm(it.get("brand")), _norm(it.get("model")), it.get("year")
            price, mileage = it.get("price"), it.get("mileage")
            if price is None:
                continue
            for key in (("bmy", brand, model, year), ("bm", brand, model, None), ("by", brand, None, year)):
                buckets[key]["prices"].append(price)
                if mileage is not None:
                    buckets[key]["mileages"].append(mileage)
        for b in buckets.values():
            b["median_mileage"] = statistics.median(b["mileages"]) if b["mileages"] else None
        return buckets


def _norm(value) -> str:
    return str(value).strip().lower() if value is not None else ""
