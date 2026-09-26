"""Advisor engine: hard filters, attribute resolution, scoring, briefing, insurance."""
from __future__ import annotations

from datetime import date

import pytest

from pipeline.insurance import estimate_monthly_premium
from pipeline.matcher import BuyerProfile, attach_valuations, deal_component, evaluate, rank
from pipeline.valuation import value_listings
from reference.lookup import get_issues, get_spec, match_model
from scrapers import sample_data


def _car(**kw):
    base = {"brand": "Volvo", "model": "V60", "year": 2019, "price": 180_000, "mileage": 90_000,
            "city": "Linköping", "url": "https://x/1"}
    return {**base, **kw}


@pytest.fixture(scope="module")
def market():
    listings = sample_data.generate(n=300)
    return attach_valuations(listings, value_listings(listings)[1])


# ------------------------------------------------------------------ filters
def test_awd_profile_returns_only_awd_models(market):
    results = rank(market, BuyerProfile(budget_max=300_000, drivetrains={"AWD"}))
    assert results and {(r["brand"], r["model"]) for r in results} == {("Volvo", "XC60")}


def test_ad_stated_awd_beats_the_spec(market):
    """A 'V60 D4 AWD' ad is AWD even though the curated V60 row says FWD."""
    profile = BuyerProfile(drivetrains={"AWD"})
    assert evaluate(_car(drivetrain="AWD"), profile) is not None
    assert evaluate(_car(), profile) is None


def test_ad_stated_fuel_selects_consumption():
    phev = evaluate(_car(fuel_type="Laddhybrid"), BuyerProfile())
    assert phev["attributes"]["fuel"] == "Laddhybrid"
    assert phev["attributes"]["consumption_source"] == "typical"
    assert phev["attributes"]["kwh_per_100km"] and phev["attributes"]["l_per_100km"]
    diesel = evaluate(_car(fuel_type="Diesel"), BuyerProfile())
    assert diesel["attributes"]["consumption_source"] == "spec"


def test_seller_and_damage_filters():
    assert evaluate(_car(seller_type="dealer"), BuyerProfile(seller_types={"private"})) is None
    assert evaluate(_car(seller_type="private"), BuyerProfile(seller_types={"private"}))
    assert evaluate(_car(damage_flag=1), BuyerProfile()) is None
    assert evaluate(_car(damage_flag=1), BuyerProfile(include_damaged=True))


def test_budget_year_mileage_filters():
    assert evaluate(_car(price=250_000), BuyerProfile(budget_max=200_000)) is None
    assert evaluate(_car(year=2014), BuyerProfile(min_year=2016)) is None
    assert evaluate(_car(mileage=250_000), BuyerProfile(max_mileage=200_000)) is None
    assert evaluate(_car(mileage=None), BuyerProfile(max_mileage=200_000))   # unknown passes


# ------------------------------------------------------------------ scoring
def test_deal_component_uses_z_and_trust():
    strong = deal_component({"deal_z": 2.0, "value_confidence": "high"})
    shaky = deal_component({"deal_z": 2.0, "value_confidence": "low"})
    assert strong == pytest.approx(1.0) and shaky < strong
    assert deal_component({"discount_pct": None}) < 0.2


def test_score_is_not_discount_alone(market):
    """Kais's rule: an unreliable car with a big discount must not auto-win."""
    cheap_unreliable = _car(brand="Audi", model="A4", deal_z=2.5, value_confidence="high")
    reliable = _car(brand="Toyota", model="Corolla", deal_z=0.8, value_confidence="high",
                    fuel_type="Hybrid")
    profile = BuyerProfile(budget_max=250_000)
    assert evaluate(reliable, profile)["match_score"] >= evaluate(cheap_unreliable, profile)["match_score"] - 5


# ------------------------------------------------------------------ briefing
def test_briefing_contents():
    r = evaluate(_car(regnr="ABC123", seller_type="private", first_price=195_000,
                      days_on_market=60, discount_pct=15, value_confidence="low"), BuyerProfile())
    b = r["briefing"]
    assert any("car.info" in link["url"] for link in b["history_links"])
    assert "köplagen" in b["seller_note"]
    assert any("sänkts 15 000 kr" in s for s in b["signals"])
    assert any("60 dagar" in s for s in b["signals"])
    assert any("osäker" in f for f in b["red_flags"])


def test_known_issue_year_ranges():
    assert get_issues("Volkswagen", "Golf", 2019) == []
    assert get_issues("Volkswagen", "Golf", 2011)
    assert any("olje" in it["issue"].lower() for it in get_issues("Audi", "A4", 2010))


def test_model_matching_handles_real_blocket_names():
    assert match_model("Volvo", "V60 Cross Country") == ("Volvo", "V60")
    assert match_model("Tesla", "Model3") == ("Tesla", "Model 3")
    assert match_model("Volvo", "V6") is None
    assert get_spec("Volvo", "V60 Cross Country")["model"] == "V60"


# ------------------------------------------------------------------ insurance
@pytest.mark.parametrize("kwargs,expected", [
    ({"car_value": 150_000, "power_hp": 150}, 560),                       # national average-ish
    ({"car_value": 150_000, "power_hp": 150, "city": "Stockholm", "driver_age": 23,
      "claims_free_years": 0}, 1_680),
    ({"car_value": 150_000, "power_hp": 150, "driver_age": 45, "claims_free_years": 10}, 330),
    ({"car_value": 380_000, "power_hp": 283}, 1_080),                     # Tesla Model 3
])
def test_insurance_calibration_points(kwargs, expected):
    """The calibration documented in HANDOFF.md §4 must not drift."""
    assert estimate_monthly_premium(year=date.today().year - 5, **kwargs) == expected
