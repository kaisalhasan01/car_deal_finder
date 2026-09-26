"""REST API (FastAPI TestClient) against a freshly built sample database."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pipeline import run, service


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dbfile = tmp_path_factory.mktemp("api") / "api.db"
    assert run.main(["--source", "sample", "--limit", "200", "--db", str(dbfile)]) == 0
    mp = pytest.MonkeyPatch()
    mp.setenv("CAR_DEALS_DB", str(dbfile))
    service.clear_cache()
    from api.main import app
    yield TestClient(app)
    mp.undo()
    service.clear_cache()


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["demo"] is True and body["active_listings"] == 200
    assert body["last_run"]["listings_loaded"] == 200


def test_recommend(client):
    body = client.post("/recommend", json={"budget_max": 220000, "min_year": 2016,
                                           "body_types": ["Kombi", "Halvkombi"], "top_n": 3}).json()
    assert body["count"] == 3
    scores = [r["match_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(r["price"] <= 220000 and r["year"] >= 2016 for r in body["results"])


def test_recommend_validates_input(client):
    assert client.post("/recommend", json={"drivetrains": ["4x4"]}).status_code == 422


def test_valuate_kais_audi_example(client):
    low = client.post("/valuate", json={"brand": "Audi", "model": "A4", "year": 2016,
                                        "mileage_km": 100_000, "price": 120_000}).json()
    high = client.post("/valuate", json={"brand": "Audi", "model": "A4", "year": 2016,
                                         "mileage_km": 200_000, "price": 120_000}).json()
    assert low["valuation"]["value"] > high["valuation"]["value"]
    assert low["valuation"]["low"] < low["valuation"]["value"] < low["valuation"]["high"]


def test_listings_filter_sort_and_detail(client):
    body = client.get("/listings", params={"brand": "volvo", "max_price": 250000,
                                           "sort": "price_sek", "limit": 5}).json()
    prices = [it["price_sek"] for it in body["items"]]
    assert body["total"] >= len(prices) > 0 and prices == sorted(prices)
    assert all(it["brand"] == "Volvo" for it in body["items"])
    detail = client.get(f"/listings/{body['items'][0]['listing_id']}").json()
    assert detail["listing"]["listing_id"] == body["items"][0]["listing_id"]
    assert len(detail["price_history"]) == 1
    assert client.get("/listings/999999").status_code == 404


def test_market_endpoints(client):
    models = client.get("/market/models").json()["items"]
    assert len(models) == 10 and sum(m["active_listings"] for m in models) == 200
    deals = client.get("/market/deals", params={"limit": 5}).json()["items"]
    assert all(d["discount_pct"] >= 5 and d["damage_flag"] == 0 for d in deals)
    curve = client.get("/market/depreciation", params={"brand": "Volvo", "model": "V60"}).json()
    values = [p["value"] for p in curve["curve"]]
    assert values == sorted(values, reverse=True) and curve["summary"]["n_listings"] > 0


def test_reference(client):
    assert len(client.get("/reference/specs").json()["items"]) >= 10
    issues = client.get("/reference/issues", params={"brand": "Audi", "model": "A4",
                                                     "year": 2010}).json()["items"]
    assert issues


def test_demo_mode_is_labelled_and_never_leaks_ground_truth(tmp_path, monkeypatch):
    """Without a database the API serves generated demo data: labelled demo, and the
    generator's hidden truth (_fair_value, _injected_deal) must not reach the client."""
    monkeypatch.setenv("CAR_DEALS_DB", str(tmp_path / "missing.db"))
    service.clear_cache()
    from api.main import app
    body = TestClient(app).post("/recommend", json={"top_n": 5}).json()
    service.clear_cache()
    assert body["demo"] is True and body["results"]
    assert not any(k.startswith("_") for r in body["results"] for k in r)
