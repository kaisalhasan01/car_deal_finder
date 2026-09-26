"""Blocket car-search client — plain `requests`, no browser, no API key.

In Nov–Dec 2025 Blocket moved onto the Vend (FINN.no) marketplace platform. The
old `/bilar/sok` pages and their `__NEXT_DATA__` JSON are gone; car search is now
served as JSON by the same endpoint the website itself calls:

    GET https://www.blocket.se/mobility/search/api/search/SEARCH_ID_CAR_USED

    {"docs":     [ {ad}, ... ],        one page of listings
     "filters":  [ ... ],              available facets with hit counts
     "metadata": {"result_size": {...}, "paging": {"current": 1, "last": 20},
                  "selected_filters": [...], "is_end_of_paging": false, ...}}

Facts baked in below (sources in docs/BLOCKET_API.md):
  * mileage is reported in Swedish mil (1 mil = 10 km) and converted to km here;
    a page-level plausibility check catches a silent unit change;
  * Blocket silently ignores unknown query params, so results are also filtered
    client-side and `--probe` prints `metadata.selected_filters` as proof;
  * `sales_form=1` keeps used cars only (2 = new, 5 = leasing; leasing ads carry a
    monthly price that would poison the valuation).

STATUS: the field names come from published documentation of this endpoint, not
yet from a response captured by this project (the dev sandbox cannot reach
blocket.se). Run `python -m scrapers.blocket --probe` once from a normal internet
connection to confirm; the parser falls back to a generic JSON walk if needed.
Personal/educational use: keep the delay, respect Blocket's terms of use.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import sys
import time
import urllib.parse
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:          # allow `python scrapers/blocket.py`
    sys.path.insert(0, str(PROJECT_ROOT))

from reference.geo_data import BLOCKET_COUNTY_CODES, resolve_location   # noqa: E402
from scrapers.blocket_codes import (                                     # noqa: E402
    canonical_brand, canonical_drivetrain, canonical_fuel, canonical_gearbox,
    canonical_regnr, canonical_seller, drivetrain_from_text, make_code, power_hp_from_text,
)

BASE_URL = "https://www.blocket.se"
CAR_SEARCH_URL = f"{BASE_URL}/mobility/search/api/search/SEARCH_ID_CAR_USED"
AD_URL = BASE_URL + "/mobility/item/{ad_id}"
REQUEST_DELAY = 2.0          # seconds between pages — be polite
MAX_RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 (car-deal-finder; personal research)"
)
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "raw" / "blocket"
MIN_PLAUSIBLE_PRICE = 5_000  # SEK; below this is a placeholder ("1 kr", "ring för pris")
KM_PER_MIL = 10


@dataclass
class Listing:
    """The normalized shape every source (Blocket, sample, replay) returns."""
    brand: str
    model: str
    year: int
    mileage: int | None            # km (Blocket reports mil -> converted)
    price: int                     # SEK
    city: str
    url: str
    fuel_type: str | None = None
    gearbox: str | None = None
    color: str | None = None
    county: str | None = None
    listing_date: date = None      # type: ignore[assignment]  # date the ad was published
    ad_id: str | None = None
    title: str | None = None
    model_spec: str | None = None
    regnr: str | None = None
    seller_type: str | None = None  # 'private' | 'dealer'
    dealer_name: str | None = None
    body_type: str | None = None
    drivetrain: str | None = None   # only set when the ad states it (e.g. 'AWD')
    power_hp: int | None = None
    lat: float | None = None
    lon: float | None = None
    image_url: str | None = None
    source: str = "blocket"

    def __post_init__(self):
        if self.listing_date is None:
            self.listing_date = date.today()

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchFilters:
    """A car search. Mileage bounds are in km (converted to Blocket's mil)."""
    query: str = ""
    makes: list[str] = field(default_factory=list)       # brand names, e.g. ["Volvo"]
    counties: list[str] = field(default_factory=list)    # e.g. ["Stockholms län"]
    price_from: int | None = None
    price_to: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    mileage_km_from: int | None = None
    mileage_km_to: int | None = None
    sales_form: int | None = 1                            # 1 used · 2 new · 5 leasing · None all
    sort: str = "PUBLISHED_DESC"
    rows: int | None = None

    def to_params(self, page: int) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        if self.query:
            params.append(("q", self.query))
        params += [("page", str(page)), ("sort", self.sort)]
        for key, value in (
            ("price_from", self.price_from), ("price_to", self.price_to),
            ("year_from", self.year_from), ("year_to", self.year_to),
            ("mileage_from", _km_to_mil(self.mileage_km_from)),
            ("mileage_to", _km_to_mil(self.mileage_km_to)),
            ("sales_form", self.sales_form), ("rows", self.rows),
        ):
            if value is not None:
                params.append((key, str(value)))
        for brand in self.makes:
            code = make_code(brand)
            if code is None:
                raise ValueError(f"unknown make {brand!r} (see scrapers/blocket_codes.py)")
            params.append(("make", code))
        for county in self.counties:
            code = BLOCKET_COUNTY_CODES.get(county)
            if code is None:
                raise ValueError(f"unknown county {county!r} (use e.g. 'Stockholms län')")
            params.append(("location", code))
        return params

    def scope_key(self) -> str:
        """Stable id of the search itself (all filters, no page)."""
        return urllib.parse.urlencode(sorted(p for p in self.to_params(1) if p[0] != "page"))

    def accepts(self, it: Listing) -> bool:
        """Client-side re-check, because Blocket silently drops params it doesn't know."""
        if self.price_from is not None and it.price < self.price_from:
            return False
        if self.price_to is not None and it.price > self.price_to:
            return False
        if self.year_from is not None and it.year < self.year_from:
            return False
        if self.year_to is not None and it.year > self.year_to:
            return False
        if it.mileage is not None:
            if self.mileage_km_from is not None and it.mileage < self.mileage_km_from:
                return False
            if self.mileage_km_to is not None and it.mileage > self.mileage_km_to:
                return False
        if self.makes and it.brand not in {canonical_brand(m) for m in self.makes}:
            return False
        return True


@dataclass
class RunStats:
    pages_fetched: int = 0
    ads_seen: int = 0
    ads_parsed: int = 0
    ads_rejected_by_filters: int = 0
    skipped: Counter = field(default_factory=Counter)
    match_count: int | None = None
    last_page: int | None = None
    reached_end: bool = False
    adapter: str | None = None
    mileage_unit: str | None = None
    mileage_unit_basis: str | None = None
    selected_filters: object = None
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        skipped = ", ".join(f"{k}={v}" for k, v in self.skipped.items()) or "none"
        return (f"pages={self.pages_fetched} ads_seen={self.ads_seen} parsed={self.ads_parsed} "
                f"filtered_out={self.ads_rejected_by_filters} skipped[{skipped}] "
                f"match_count={self.match_count} reached_end={self.reached_end} "
                f"mileage_unit={self.mileage_unit}({self.mileage_unit_basis})")


class BlocketScraper:
    """Search Blocket cars and yield normalized `Listing`s.

    A new transport (e.g. Bright Data) subclasses this and overrides `_fetch_page`
    only — URL building, parsing and normalization are shared.
    """

    source_name = "blocket"

    def __init__(self, delay: float = REQUEST_DELAY, session: requests.Session | None = None,
                 max_retries: int = MAX_RETRIES, timeout: float = 30,
                 snapshot_dir: Path | str | None = None, mileage_unit: str = "auto"):
        if mileage_unit not in ("auto", "mil", "km"):
            raise ValueError("mileage_unit must be auto|mil|km")
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        self.mileage_unit = mileage_unit
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Language": "sv-SE",
        })
        self.stats = RunStats()

    # ------------------------------------------------------------------ search
    def search(self, query: str = "", pages: int = 1,
               filters: SearchFilters | None = None) -> Iterator[Listing]:
        filters = filters or SearchFilters(query=query)
        if query and not filters.query:
            filters.query = query
        self.stats = RunStats()
        seen: set[str] = set()
        for page in range(1, pages + 1):
            body = self._fetch_page(self._page_url(filters, page))
            if body is None:
                self.stats.errors.append(f"page {page}: fetch failed")
                break
            self.stats.pages_fetched += 1
            self._save_snapshot(filters, page, body)
            raw_ads, meta = self._parse_payload(body)
            self._update_paging_stats(meta, page)
            for it in self._normalize_page(raw_ads, meta):
                if it.url in seen:                 # an ad can shift across page borders
                    continue
                seen.add(it.url)
                if filters.accepts(it):
                    yield it
                else:
                    self.stats.ads_rejected_by_filters += 1
            if not raw_ads or self._is_last_page(meta, page):
                self.stats.reached_end = True
                break
            if page < pages:
                time.sleep(self.delay)

    def _page_url(self, filters: SearchFilters, page: int) -> str:
        return f"{CAR_SEARCH_URL}?{urllib.parse.urlencode(filters.to_params(page))}"

    # --------------------------------------------------------------- transport
    def _fetch_page(self, url: str) -> str | None:
        """GET with retries + exponential backoff on 429/5xx (honours Retry-After)."""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                wait = 2 ** attempt
                print(f"[blocket] network error (attempt {attempt}/{self.max_retries}): {exc}")
            else:
                if resp.status_code not in RETRY_STATUSES:
                    if resp.ok:
                        return resp.text
                    print(f"[blocket] HTTP {resp.status_code} for {url} — giving up")
                    return None
                wait = _retry_after(resp) or 2 ** attempt
                print(f"[blocket] HTTP {resp.status_code} (attempt {attempt}/{self.max_retries})")
            if attempt < self.max_retries:
                time.sleep(wait)
        return None

    # ----------------------------------------------------------------- parsing
    def _parse_payload(self, body: str) -> tuple[list[dict], dict]:
        """Return (raw ad dicts, metadata) from a JSON body (or HTML with embedded JSON)."""
        data = _load_json(body)
        if data is None:
            data = _extract_embedded_json(body)
        if data is None:
            self.stats.adapter = "none"
            return [], {}
        ads, adapter = _find_raw_ads(data)
        self.stats.adapter = adapter
        meta = data.get("metadata") if isinstance(data, dict) else None
        return ads, meta if isinstance(meta, dict) else {}

    def _normalize_page(self, raw_ads: list[dict], meta: dict) -> list[Listing]:
        factor = self._mileage_factor(raw_ads, meta)
        out = []
        for raw in raw_ads:
            self.stats.ads_seen += 1
            listing, reason = normalize_ad(raw, mileage_factor=factor)
            if listing is None:
                self.stats.skipped[reason] += 1
                continue
            listing.source = self.source_name
            self.stats.ads_parsed += 1
            out.append(listing)
        return out

    def _mileage_factor(self, raw_ads: list[dict], meta: dict) -> int:
        """km per reported mileage unit: 10 when Blocket reports mil, 1 when km."""
        if self.mileage_unit != "auto":
            self.stats.mileage_unit, self.stats.mileage_unit_basis = self.mileage_unit, "config"
            return KM_PER_MIL if self.mileage_unit == "mil" else 1
        declared = next((str(r["mileage_unit"]) for r in raw_ads if r.get("mileage_unit")),
                        meta.get("mileage_unit"))
        if declared:
            is_mil = "MILE" in declared.upper() or declared.strip().lower() == "mil"
            self.stats.mileage_unit = "mil" if is_mil else "km"
            self.stats.mileage_unit_basis = "declared"
            return KM_PER_MIL if is_mil else 1
        # Plausibility: Swedish cars drive ~1 000–2 000 mil (10 000–20 000 km) a year.
        per_year = []
        for raw in raw_ads:
            year, mileage = _parse_year(raw), _to_int(raw.get("mileage"))
            if year and mileage and (age := date.today().year - year) >= 2:
                per_year.append(mileage / age)
        if len(per_year) >= 5:
            is_km = statistics.median(per_year) > 5_000
            self.stats.mileage_unit = "km" if is_km else "mil"
            self.stats.mileage_unit_basis = f"heuristic(median {statistics.median(per_year):,.0f}/yr)"
            return 1 if is_km else KM_PER_MIL
        self.stats.mileage_unit, self.stats.mileage_unit_basis = "mil", "default"
        return KM_PER_MIL

    def _update_paging_stats(self, meta: dict, page: int) -> None:
        size = meta.get("result_size")
        if isinstance(size, dict):
            self.stats.match_count = _to_int(size.get("match_count")) or self.stats.match_count
        elif size is not None:
            self.stats.match_count = _to_int(size)
        paging = meta.get("paging") if isinstance(meta.get("paging"), dict) else {}
        self.stats.last_page = _to_int(paging.get("last")) or self.stats.last_page
        if "selected_filters" in meta:
            self.stats.selected_filters = meta["selected_filters"]

    @staticmethod
    def _is_last_page(meta: dict, page: int) -> bool:
        if meta.get("is_end_of_paging") is True:
            return True
        paging = meta.get("paging") if isinstance(meta.get("paging"), dict) else {}
        last = _to_int(paging.get("last"))
        return last is not None and page >= last

    # --------------------------------------------------------------- snapshots
    def _save_snapshot(self, filters: SearchFilters, page: int, body: str) -> None:
        if not self.snapshot_dir:
            return
        day_dir = self.snapshot_dir / date.today().isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        slug = hashlib.sha1(filters.scope_key().encode()).hexdigest()[:10]
        payload = _load_json(body)
        record = {
            "url": self._page_url(filters, page), "scope": filters.scope_key(), "page": page,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "payload": payload if payload is not None else body,
        }
        (day_dir / f"{slug}_p{page:03d}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Normalization of one raw ad
# ---------------------------------------------------------------------------
def normalize_ad(raw: dict, mileage_factor: int = KM_PER_MIL) -> tuple[Listing | None, str]:
    """Map one raw Blocket ad to a `Listing`. Returns (listing, '') or (None, reason)."""
    if not isinstance(raw, dict):
        return None, "not_a_dict"
    price, price_reason = _parse_price(raw)
    if price is None:
        return None, price_reason
    year = _parse_year(raw)
    if year is None:
        return None, "no_year"
    brand = canonical_brand(raw.get("make") or raw.get("brand") or _dig(raw, "car", "brand"))
    model = str(raw.get("model") or _dig(raw, "car", "model") or "").strip() or None
    title = _str(raw.get("heading") or raw.get("title") or raw.get("subject"))
    if not brand or not model:
        brand, model = brand or _brand_from_title(title), model or _model_from_title(title, brand)
    if not brand or not model:
        return None, "no_make_model"

    mileage_raw = _to_int(raw.get("mileage") if raw.get("mileage") is not None
                          else _dig(raw, "car", "mileage"))
    mileage = mileage_raw * mileage_factor if mileage_raw is not None else None

    ad_id = _str(raw.get("ad_id") or raw.get("id") or raw.get("dealId"))
    url = raw.get("canonical_url") or raw.get("share_url") or raw.get("url") or raw.get("link")
    if not (isinstance(url, str) and url.startswith("http")):
        url = AD_URL.format(ad_id=ad_id) if ad_id else None
    if not url:
        return None, "no_url"

    location = raw.get("location")
    if isinstance(location, dict):
        location = location.get("name") or location.get("municipality") or location.get("area")
    municipality, county = resolve_location(_str(location))
    model_spec = _str(raw.get("model_specification") or raw.get("variant"))
    coords = raw.get("coordinates") if isinstance(raw.get("coordinates"), dict) else {}

    listing = Listing(
        brand=brand,
        model=model,
        year=year,
        mileage=mileage,
        price=price,
        # A bare county name ("Stockholms län") is not a city: keep it only as county.
        city=municipality or (None if county else _str(location)) or "unknown",
        url=url,
        fuel_type=canonical_fuel(raw.get("fuel") or _dig(raw, "car", "fuel")),
        gearbox=canonical_gearbox(raw.get("transmission") or raw.get("gearbox")
                                  or _dig(raw, "car", "gearbox")),
        color=_str(raw.get("exterior_colour") or raw.get("color") or raw.get("colour")),
        county=county,
        listing_date=_parse_published(raw),
        ad_id=ad_id,
        title=title,
        model_spec=model_spec,
        regnr=canonical_regnr(raw.get("regno") or raw.get("registration_number")
                              or raw.get("regNo")),
        seller_type=canonical_seller(raw.get("dealer_segment") or _dig(raw, "seller", "type"),
                                     raw.get("flags"), raw.get("organisation_name")),
        dealer_name=_str(raw.get("organisation_name") or _dig(raw, "seller", "name")),
        body_type=_str(raw.get("body_type") or raw.get("car_type")),
        drivetrain=(canonical_drivetrain(raw.get("wheel_drive"))
                    or drivetrain_from_text(model_spec, title, brand=brand)),
        power_hp=(_to_int(raw.get("engine_effect") or raw.get("horsepower"))
                  or power_hp_from_text(model_spec, title)),
        lat=_to_float(coords.get("lat") or coords.get("latitude")),
        lon=_to_float(coords.get("lon") or coords.get("lng") or coords.get("longitude")),
        image_url=_image_url(raw),
    )
    return listing, ""


def _parse_price(raw: dict) -> tuple[int | None, str]:
    price = raw.get("price")
    unit = ""
    if isinstance(price, dict):
        unit = str(price.get("price_unit") or price.get("billingPeriod") or "").lower()
        price = price.get("amount") if price.get("amount") is not None else price.get("value")
    if price is None:
        price = raw.get("price_amount")
    value = _to_int(price)
    if value is None:
        return None, "no_price"
    if "mån" in unit or "month" in unit:
        return None, "monthly_price"            # leasing / rental, not a sale price
    if value < MIN_PLAUSIBLE_PRICE:
        return None, "placeholder_price"
    return value, ""


def _parse_year(raw: dict) -> int | None:
    for key in ("year", "model_year", "modelYear", "regDate", "registration_year"):
        value = raw.get(key)
        if value is None:
            value = _dig(raw, "car", key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            year = int(value)
        else:
            m = re.search(r"(19|20)\d{2}", str(value))   # '2019-05-01' -> 2019, not 20190501
            year = int(m.group(0)) if m else None
        if year and 1950 <= year <= date.today().year + 1:
            return year
    return None


def _parse_published(raw: dict) -> date:
    ts = raw.get("timestamp") or raw.get("published") or raw.get("listTime") or raw.get("created")
    if isinstance(ts, (int, float)) and ts > 0:
        seconds = ts / 1000 if ts > 1e11 else ts            # ms or s epoch
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date()
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return date.today()


def _image_url(raw: dict) -> str | None:
    image = raw.get("image")
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]
    urls = raw.get("image_urls") or raw.get("images")
    if isinstance(urls, list) and urls:
        first = urls[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("image")
    return None


def _brand_from_title(title: str | None) -> str | None:
    if not title:
        return None
    brand = canonical_brand(title.split()[0])
    return brand if make_code(brand or "") else None


def _model_from_title(title: str | None, brand: str | None) -> str | None:
    if not title or not brand:
        return None
    words = title.split()
    return words[1] if len(words) > 1 else None


# ---------------------------------------------------------------------------
# Locating the ads array (JSON API first, then legacy shapes, then generic walk)
# ---------------------------------------------------------------------------
def _find_raw_ads(data) -> tuple[list[dict], str]:
    if isinstance(data, dict) and isinstance(data.get("docs"), list):
        return [d for d in data["docs"] if isinstance(d, dict)], "json-api:docs"
    if isinstance(data, dict):
        page_props = _dig(data, "props", "pageProps") or {}
        for key in ("ads", "listings", "results", "items"):
            if isinstance(page_props.get(key), list):
                return page_props[key], f"next-data:{key}"
        if isinstance(data.get("cars"), list):                       # pre-2025 motor API
            return data["cars"], "legacy:cars"
    found = _largest_ad_like_list(data)
    return (found, "generic-walk") if found else ([], "none")


def _looks_like_ad(obj) -> bool:
    return isinstance(obj, dict) and "price" in obj and any(
        k in obj for k in ("year", "heading", "model", "make", "subject", "title"))


def _largest_ad_like_list(data, depth: int = 0) -> list[dict]:
    if depth > 8:
        return []
    best: list[dict] = []
    children = data.values() if isinstance(data, dict) else data if isinstance(data, list) else []
    if isinstance(data, list) and data and sum(map(_looks_like_ad, data)) >= max(1, len(data) // 2):
        best = [d for d in data if isinstance(d, dict)]
    for child in children:
        if isinstance(child, (dict, list)):
            cand = _largest_ad_like_list(child, depth + 1)
            if len(cand) > len(best):
                best = cand
    return best


def _extract_embedded_json(html: str):
    """Fallback for HTML pages: __NEXT_DATA__ or other inline JSON state."""
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        return _load_json(m.group(1))
    m = re.search(r'JSON\.parse\("(.+?)"\)', html, re.DOTALL)
    if m:
        try:
            return json.loads(json.loads(f'"{m.group(1)}"'))
        except (json.JSONDecodeError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------
# Replay saved snapshots (offline re-runs without hitting Blocket)
# ---------------------------------------------------------------------------
def iter_snapshot_listings(paths: Iterable[Path | str],
                           mileage_unit: str = "auto") -> Iterator[Listing]:
    """Re-parse raw pages saved by `snapshot_dir` — same code path as a live run."""
    parser = BlocketScraper(snapshot_dir=None, mileage_unit=mileage_unit)
    seen: set[str] = set()
    files: list[Path] = []
    for p in map(Path, paths):
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    for f in files:
        record = json.loads(f.read_text(encoding="utf-8"))
        payload = record.get("payload", record) if isinstance(record, dict) else record
        body = payload if isinstance(payload, str) else json.dumps(payload)
        raw_ads, meta = parser._parse_payload(body)
        for it in parser._normalize_page(raw_ads, meta):
            if it.url not in seen:
                seen.add(it.url)
                yield it


# ---------------------------------------------------------------------------
# Probe: fetch one real page and report exactly what the parser sees
# ---------------------------------------------------------------------------
PROBE_FIELDS = ("ad_id", "id", "heading", "price", "year", "mileage", "make", "model",
                "model_specification", "fuel", "transmission", "regno", "dealer_segment",
                "organisation_name", "location", "coordinates", "timestamp", "canonical_url",
                "image", "mileage_unit", "wheel_drive", "body_type")


def probe(filters: SearchFilters, scraper: BlocketScraper | None = None,
          out_dir: Path | str = PROJECT_ROOT / "debug") -> int:
    scraper = scraper or BlocketScraper()
    url = scraper._page_url(filters, 1)
    print(f"[probe] GET {url}")
    body = scraper._fetch_page(url)
    if body is None:
        print("[probe] FAILED to fetch. Blocked network? Try --transport brightdata.")
        return 2
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw_path = out / f"blocket_probe_{stamp}.json"
    raw_path.write_text(body, encoding="utf-8")
    print(f"[probe] saved raw response -> {raw_path} ({len(body):,} bytes)")

    data = _load_json(body)
    if isinstance(data, dict):
        print(f"[probe] top-level keys: {sorted(data)}")
        meta = data.get("metadata") or {}
        if isinstance(meta, dict):
            print(f"[probe] metadata keys: {sorted(meta)}")
            for k in ("result_size", "paging", "is_end_of_paging", "mileage_unit"):
                if k in meta:
                    print(f"[probe]   {k}: {json.dumps(meta[k], ensure_ascii=False)[:300]}")
            print("[probe]   selected_filters (proves which params Blocket applied):")
            print("          " + json.dumps(meta.get("selected_filters"), ensure_ascii=False)[:800])
    raw_ads, meta = scraper._parse_payload(body)
    print(f"[probe] adapter: {scraper.stats.adapter} · raw ads on page: {len(raw_ads)}")
    if not raw_ads:
        print("[probe] No ads found — inspect the saved file and update _find_raw_ads().")
        return 1

    print("[probe] field coverage across raw ads:")
    for key in PROBE_FIELDS:
        n = sum(1 for r in raw_ads if r.get(key) not in (None, "", [], {}))
        print(f"          {key:22s} {n:3d}/{len(raw_ads)}")
    extra = sorted({k for r in raw_ads for k in r} - set(PROBE_FIELDS))
    print(f"[probe] other keys seen: {extra}")
    print("[probe] first raw ad:")
    print(json.dumps(raw_ads[0], ensure_ascii=False, indent=2)[:2500])

    listings = scraper._normalize_page(raw_ads, meta)
    st = scraper.stats
    print(f"[probe] normalized {len(listings)}/{len(raw_ads)} · skipped {dict(st.skipped)} · "
          f"mileage unit {st.mileage_unit} ({st.mileage_unit_basis})")
    for it in listings[:8]:
        km = f"{it.mileage:,} km" if it.mileage is not None else "? km"
        print(f"   {it.brand} {it.model} {it.year} · {it.price:,} kr · {km} · {it.fuel_type} · "
              f"{it.seller_type} · {it.city}/{it.county} · regnr={it.regnr}")
    county_hits = sum(1 for it in listings if it.county)
    print(f"[probe] county resolved for {county_hits}/{len(listings)} listings")
    ok = len(listings) >= 0.8 * len(raw_ads)
    print("[probe] VERDICT: " + ("PASS — parser matches the live response." if ok else
                                 "CHECK — fewer than 80% of ads normalized; see skipped reasons."))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _dig(d, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _to_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _to_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_json(text: str):
    stripped = text.lstrip() if isinstance(text, str) else ""
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _km_to_mil(km: int | None) -> int | None:
    return None if km is None else km // KM_PER_MIL


def _retry_after(resp: requests.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    try:
        return min(float(value), 120.0) if value else None
    except ValueError:
        return None


def build_scraper(transport: str = "direct", **kwargs) -> BlocketScraper:
    if transport == "direct":
        return BlocketScraper(**kwargs)
    if transport == "brightdata":
        from scrapers.blocket_brightdata import BlocketBrightDataScraper
        return BlocketBrightDataScraper(**kwargs)
    raise ValueError(f"unknown transport {transport!r} (direct|brightdata)")


def _main() -> int:
    import argparse

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Blocket car search (JSON API)")
    ap.add_argument("--probe", action="store_true", help="fetch one page and report its structure")
    ap.add_argument("--query", default="", help='free text, e.g. "volvo v60"')
    ap.add_argument("--make", default="", help="comma list of brands, e.g. Volvo,Audi")
    ap.add_argument("--county", default="", help="comma list, e.g. 'Stockholms län'")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--transport", choices=["direct", "brightdata"], default="direct")
    ap.add_argument("--mileage-unit", choices=["auto", "mil", "km"], default="auto")
    args = ap.parse_args()

    filters = SearchFilters(
        query=args.query,
        makes=[m.strip() for m in args.make.split(",") if m.strip()],
        counties=[c.strip() for c in args.county.split(",") if c.strip()],
    )
    scraper = build_scraper(args.transport, mileage_unit=args.mileage_unit)
    if args.probe:
        return probe(filters, scraper)
    for i, item in enumerate(scraper.search(pages=args.pages, filters=filters)):
        print(item)
        if i >= 19:
            break
    print(f"[blocket] {scraper.stats.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
