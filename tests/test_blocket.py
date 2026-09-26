"""Blocket client: URL building, pagination, normalization, units, retries, replay."""
from __future__ import annotations

import json
import urllib.parse

import pytest

from conftest import FakeResponse, FakeSession
from scrapers.blocket import (
    CAR_SEARCH_URL, BlocketScraper, SearchFilters, iter_snapshot_listings, normalize_ad,
)
from scrapers.blocket_codes import (
    canonical_brand, canonical_fuel, canonical_regnr, canonical_seller, drivetrain_from_text,
    power_hp_from_text,
)


def _params(url: str) -> list[tuple[str, str]]:
    return urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)


def _search(session, pages=5, **filters):
    scraper = BlocketScraper(session=session, delay=0)
    return scraper, list(scraper.search(pages=pages, filters=SearchFilters(**filters)))


# --------------------------------------------------------------------- URLs
def test_url_uses_json_endpoint_and_encodes_filters():
    f = SearchFilters(query="volvo v60", makes=["Volvo", "vw"], counties=["Stockholms län"],
                      price_to=200_000, year_from=2016, mileage_km_to=150_000)
    url = BlocketScraper(session=FakeSession())._page_url(f, 3)
    assert url.startswith(CAR_SEARCH_URL + "?")
    params = _params(url)
    assert ("q", "volvo v60") in params and ("page", "3") in params
    assert ("make", "0.818") in params and ("make", "0.817") in params     # Volvo, VW alias
    assert ("location", "0.300001") in params                               # Stockholms län
    assert ("mileage_to", "15000") in params                                # km -> mil
    assert ("sales_form", "1") in params                                    # used cars only
    assert ("price_to", "200000") in params and ("year_from", "2016") in params


def test_unknown_make_or_county_fails_loudly():
    with pytest.raises(ValueError):
        SearchFilters(makes=["Batmobile"]).to_params(1)
    with pytest.raises(ValueError):
        SearchFilters(counties=["Narnia län"]).to_params(1)


def test_scope_key_ignores_page_but_not_filters():
    a, b = SearchFilters(query="x"), SearchFilters(query="x", price_to=1)
    assert a.scope_key() == SearchFilters(query="x").scope_key()
    assert a.scope_key() != b.scope_key()
    assert "page" not in a.scope_key()


# --------------------------------------------------------------- pagination
def test_paginates_until_end_of_paging(fake_session):
    scraper, items = _search(fake_session, pages=10)
    assert len(fake_session.urls) == 2                     # stopped at is_end_of_paging
    assert scraper.stats.reached_end and scraper.stats.pages_fetched == 2
    assert scraper.stats.match_count == 11
    assert len(items) == 8
    assert scraper.stats.skipped == {"monthly_price": 1, "placeholder_price": 1, "no_year": 1}


def test_page_cap_is_respected(fake_session):
    scraper, items = _search(fake_session, pages=1)
    assert len(fake_session.urls) == 1 and not scraper.stats.reached_end
    assert len(items) == 6


def test_client_side_filters_catch_params_blocket_ignored(fake_session):
    _, items = _search(fake_session, price_to=150_000)
    assert items and all(it.price <= 150_000 for it in items)


# ------------------------------------------------------------ normalization
def test_normalized_listing_fields(fake_session):
    _, items = _search(fake_session)
    v60 = next(it for it in items if it.model == "V60")
    assert (v60.brand, v60.year, v60.price) == ("Volvo", 2018, 179_900)
    assert v60.mileage == 123_450                                # 12 345 mil -> km
    assert v60.regnr == "ABC123" and v60.seller_type == "private"
    assert (v60.city, v60.county) == ("Linköping", "Östergötlands län")
    assert v60.drivetrain == "AWD" and v60.power_hp == 190
    assert v60.url == "https://www.blocket.se/mobility/item/20101001"
    assert v60.listing_date.isoformat() == "2026-08-30"          # from ms timestamp
    golf = next(it for it in items if it.model == "Golf")
    assert golf.seller_type == "dealer" and golf.dealer_name == "Bilhallen Solna AB"
    audi = next(it for it in items if it.brand == "Audi")
    assert audi.city == "unknown" and audi.county == "Stockholms län"


def test_year_is_parsed_from_date_strings_not_concatenated():
    raw = {"price": 100000, "regDate": "2019-05-01", "make": "Volvo", "model": "V70",
           "canonical_url": "https://x/1"}
    listing, reason = normalize_ad(raw)
    assert reason == "" and listing.year == 2019               # the old parser gave 20190501


def test_ads_without_price_or_year_are_skipped_with_reason():
    assert normalize_ad({"make": "Volvo", "model": "V70", "year": 2015})[1] == "no_price"
    assert normalize_ad({"make": "Volvo", "model": "V70", "price": 90000})[1] == "no_year"
    assert normalize_ad({"make": "Volvo", "model": "V70", "price": {"amount": 3990,
                         "price_unit": "kr/mån"}, "year": 2023})[1] == "monthly_price"


# --------------------------------------------------------------- mileage unit
def _unit_docs(mileage_per_year: int, n: int = 6) -> list[dict]:
    return [{"price": 100000, "year": 2016, "make": "Volvo", "model": "V70",
             "mileage": mileage_per_year * 10, "canonical_url": f"https://x/{i}"}
            for i in range(n)]


@pytest.mark.parametrize("per_year,expected_km", [(1_500, 150_000), (15_000, 150_000)])
def test_mileage_unit_heuristic_handles_mil_and_km(per_year, expected_km, monkeypatch):
    import scrapers.blocket as b

    class _D(b.date):
        @classmethod
        def today(cls):
            return b.date(2026, 9, 26)
    monkeypatch.setattr(b, "date", _D)
    scraper = BlocketScraper(session=FakeSession(), delay=0)
    out = scraper._normalize_page(_unit_docs(per_year), {})
    assert {it.mileage for it in out} == {expected_km}


def test_mileage_unit_can_be_forced():
    scraper = BlocketScraper(session=FakeSession(), mileage_unit="km")
    out = scraper._normalize_page(_unit_docs(1_500), {})
    assert out[0].mileage == 15_000


# ------------------------------------------------------------------- retries
def test_retries_on_429_then_succeeds(monkeypatch, fixtures_dir):
    import scrapers.blocket as b
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    body = (fixtures_dir / "blocket_search_p2.json").read_text(encoding="utf-8")
    session = FakeSession({1: [FakeResponse("", 429, {"Retry-After": "1"}),
                               FakeResponse("", 503), FakeResponse(body)]})
    scraper, items = _search(session, pages=1)
    assert len(session.urls) == 3 and len(items) == 2


def test_gives_up_after_max_retries(monkeypatch):
    import scrapers.blocket as b
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    session = FakeSession({1: [FakeResponse("", 503)] * 3})
    scraper, items = _search(session, pages=3)
    assert items == [] and scraper.stats.errors


def test_generic_walk_finds_ads_in_unknown_shape():
    body = json.dumps({"data": {"search": {"hits": [
        {"price": 50000, "year": 2012, "make": "Saab", "model": "9-3", "canonical_url": "https://x/1"},
        {"price": 60000, "year": 2013, "make": "Saab", "model": "9-3", "canonical_url": "https://x/2"},
    ]}}})
    scraper = BlocketScraper(session=FakeSession())
    ads, _ = scraper._parse_payload(body)
    assert len(ads) == 2 and scraper.stats.adapter == "generic-walk"


# ---------------------------------------------------------------- snapshots
def test_snapshots_round_trip_through_replay(tmp_path, fake_session):
    scraper = BlocketScraper(session=fake_session, delay=0, snapshot_dir=tmp_path)
    live = list(scraper.search(pages=5))
    files = sorted(tmp_path.rglob("*.json"))
    assert len(files) == 2
    replayed = list(iter_snapshot_listings([tmp_path]))
    assert [it.url for it in replayed] == [it.url for it in live]


# ---------------------------------------------------------------- code maps
def test_value_normalizers():
    assert canonical_brand("VOLVO") == "Volvo" and canonical_brand("vw") == "Volkswagen"
    assert canonical_brand("bmw") == "BMW" and canonical_brand("mercedes") == "Mercedes-Benz"
    assert canonical_fuel("Diesel") == "Diesel" and canonical_fuel("El") == "El"
    assert canonical_fuel("Elhybrid") == "Hybrid" and canonical_fuel("Laddhybrid") == "Laddhybrid"
    assert canonical_fuel("Miljöbränsle/Hybrid") == "Hybrid"
    assert canonical_regnr("abc 12d") == "ABC12D" and canonical_regnr("hello") is None
    assert canonical_seller("Privat") == "private" and canonical_seller("Företag") == "dealer"
    assert canonical_seller(None, None, "Bilhallen AB") == "dealer"
    assert drivetrain_from_text("320d xDrive") == "AWD" and drivetrain_from_text("1.6 TDI") is None
    assert drivetrain_from_text("Recharge T8", brand="Volvo") == "AWD"
    assert power_hp_from_text("D4 190hk") == 190 and power_hp_from_text("150 kW") == 204
