"""Blocket scraper (first draft) — requests + BeautifulSoup.

Blocket is a JavaScript-rendered (Next.js) site, so instead of brittle CSS
selectors we parse the JSON embedded in the ``<script id="__NEXT_DATA__">`` tag,
which holds the structured listing data the page hydrates from.

STATUS: BEST-EFFORT DRAFT. The JSON field paths marked `TODO` must be confirmed
against a live response. Blocket actively blocks bots and changes its markup, so
use ``--source sample`` for the working end-to-end demo. Personal/educational
use only: respect robots.txt, keep REQUEST_DELAY high, set a real User-Agent.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterator

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.blocket.se"
SEARCH_PATH = "/bilar/sok"   # TODO: confirm current search path / query params
REQUEST_DELAY = 3.0          # seconds between requests
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 (car-deal-finder; educational)"
)


@dataclass
class Listing:
    brand: str
    model: str
    year: int
    mileage: int | None
    price: int
    city: str
    url: str
    fuel_type: str | None = None
    gearbox: str | None = None
    color: str | None = None
    county: str | None = None
    listing_date: date = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.listing_date is None:
            self.listing_date = date.today()

    def as_dict(self) -> dict:
        return asdict(self)


class BlocketScraper:
    def __init__(self, delay: float = REQUEST_DELAY, session: requests.Session | None = None):
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "sv-SE"})

    def search(self, query: str = "", pages: int = 1) -> Iterator[Listing]:
        for page in range(1, pages + 1):
            html = self._fetch_page(query=query, page=page)
            if html is None:
                break
            yield from self._parse_listings(html)
            if page < pages:
                time.sleep(self.delay)

    def _fetch_page(self, query: str, page: int) -> str | None:
        params = {"q": query, "page": page}  # TODO: confirm real param names
        try:
            resp = self.session.get(f"{BASE_URL}{SEARCH_PATH}", params=params, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            print(f"[blocket] request failed for page {page}: {exc}")
            return None

    def _parse_listings(self, html: str) -> Iterator[Listing]:
        data = self._extract_next_data(html)
        if data is None:
            print("[blocket] no __NEXT_DATA__ found — page changed or blocked")
            return
        for raw in self._iter_raw_ads(data):
            listing = self._normalize(raw)
            if listing is not None:
                yield listing

    @staticmethod
    def _extract_next_data(html: str) -> dict | None:
        soup = BeautifulSoup(html, "lxml")
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag and tag.string:
            try:
                return json.loads(tag.string)
            except json.JSONDecodeError:
                pass
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _iter_raw_ads(data: dict) -> Iterator[dict]:
        # TODO: confirm the JSON path to the ads array against a live response.
        page_props = data.get("props", {}).get("pageProps", {})
        for key in ("ads", "listings", "results", "items"):
            ads = page_props.get(key)
            if isinstance(ads, list):
                yield from ads
                return
        search = page_props.get("search") or page_props.get("data") or {}
        ads = search.get("ads") if isinstance(search, dict) else None
        if isinstance(ads, list):
            yield from ads

    @staticmethod
    def _normalize(raw: dict) -> Listing | None:
        try:
            price = _to_int(_dig(raw, "price", "amount") or raw.get("price"))
            year = _to_int(raw.get("regDate") or raw.get("modelYear") or raw.get("year"))
            brand = raw.get("brand") or _dig(raw, "car", "brand") or "unknown"
            model = raw.get("model") or _dig(raw, "car", "model") or "unknown"
            if price is None or year is None:
                return None
            ad_id = raw.get("ad_id") or raw.get("id") or ""
            url = raw.get("share_url") or raw.get("url") or f"{BASE_URL}/annons/{ad_id}"
            return Listing(
                brand=str(brand).strip().title(),
                model=str(model).strip(),
                year=year,
                mileage=_to_int(raw.get("mileage") or _dig(raw, "car", "mileage")),
                price=price,
                city=(raw.get("location") or _dig(raw, "location", "name") or "unknown"),
                url=url,
                fuel_type=raw.get("fuel") or _dig(raw, "car", "fuel"),
                gearbox=raw.get("gearbox") or _dig(raw, "car", "gearbox"),
                color=raw.get("color"),
                county=raw.get("region") or _dig(raw, "location", "region"),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _dig(d: dict, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _to_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


if __name__ == "__main__":
    scraper = BlocketScraper()
    for i, item in enumerate(scraper.search(query="volvo v60", pages=1)):
        print(item)
        if i >= 9:
            break
