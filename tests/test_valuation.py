"""Hierarchical hedonic valuer: bias, leave-one-out, fallbacks, robustness."""
from __future__ import annotations

import statistics
from datetime import date

import pytest

from analysis.evaluate_valuation import _cohort, _hedonic, score
from pipeline.valuation import HedonicValuer, looks_damaged, value_listings
from scrapers import sample_data


@pytest.fixture(scope="module")
def sample():
    return sample_data.generate(n=400, seed=7)


@pytest.fixture(scope="module")
def fitted(sample):
    return value_listings(sample)


def test_every_listing_gets_a_value_with_interval(sample, fitted):
    _, vals = fitted
    assert all(v is not None for v in vals)
    assert all(v.low < v.value < v.high for v in vals)
    assert {v.method for v in vals} == {"hedonic-model"}


def test_no_systematic_bias_by_age(sample, fitted):
    """The old cohort valuer drifted to -27 % mean discount on the oldest cars."""
    _, vals = fitted
    by_age: dict[int, list[float]] = {}
    for it, v in zip(sample, vals):
        if not it["_injected_deal"] and it["price"] > 20_000:
            by_age.setdefault(date.today().year - it["year"], []).append(v.discount_pct)
    for age, discounts in by_age.items():
        assert abs(statistics.mean(discounts)) < 7, (age, statistics.mean(discounts))


def test_listing_cannot_vouch_for_its_own_price(sample):
    """Leave-one-out: doubling one car's asking price barely moves its own value."""
    base = value_listings(sample)[1][5].value
    tweaked = [dict(it) for it in sample]
    tweaked[5]["price"] *= 2
    assert abs(value_listings(tweaked)[1][5].value - base) / base < 0.02


def test_unseen_model_falls_back_to_brand_then_global(sample):
    valuer = HedonicValuer().fit(sample)
    brand_level = valuer.value({"brand": "Volvo", "model": "V90", "year": 2019, "mileage": 90_000})
    global_level = valuer.value({"brand": "Saab", "model": "9-5", "year": 2010, "mileage": 200_000})
    assert brand_level.method == "hedonic-brand" and brand_level.confidence == "low"
    assert global_level.method == "hedonic-global"


def test_newer_and_lower_mileage_is_worth_more(sample):
    valuer = HedonicValuer().fit(sample)
    car = {"brand": "Volvo", "model": "V60", "mileage": 100_000}
    assert valuer.value({**car, "year": 2021}).value > valuer.value({**car, "year": 2016}).value
    v_low = valuer.value({**car, "year": 2018, "mileage": 60_000}).value
    v_high = valuer.value({**car, "year": 2018, "mileage": 200_000}).value
    assert v_low > v_high


def test_damaged_ads_are_valued_but_not_learned_from(sample):
    broken = [dict(it) for it in sample]
    broken[0] = {**broken[0], "title": "Volvo V60 — motorhaveri, säljes som reparationsobjekt",
                 "price": 5_000}
    valuer = HedonicValuer().fit(broken)
    assert not valuer._inlier[0]
    v = valuer.value_training()[0]
    assert v.discount_pct > 50                    # flagged as an (explainable) huge "deal"
    assert looks_damaged("Motorfel, startar ej") and not looks_damaged("Nybesiktigad, fin")


def test_too_little_data_means_no_valuation():
    few = sample_data.generate(n=5)
    valuer, vals = value_listings(few)
    assert not valuer.fitted and vals == [None] * 5


def test_hedonic_beats_cohort_on_synthetic_truth():
    listings = sample_data.generate(n=200, seed=42)
    old, new = score(listings, _cohort(listings)), score(listings, _hedonic(listings))
    assert new["mape"] < old["mape"]
    assert new["f1"] > old["f1"]


def test_summaries_and_curve_are_sane(sample):
    valuer = HedonicValuer().fit(sample)
    rows = valuer.summaries()
    levels = {r["level"] for r in rows}
    assert levels == {"global", "brand", "model"}
    v60 = next(r for r in rows if r["model"] == "V60")
    assert 3 < v60["depreciation_pct_per_year"] < 30
    assert v60["value_age3_sek"] > v60["value_age8_sek"]
    curve = valuer.curve("Volvo", "V60", ages=range(0, 12))
    assert all(a["value"] > b["value"] for a, b in zip(curve, curve[1:]))
