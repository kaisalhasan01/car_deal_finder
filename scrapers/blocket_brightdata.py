"""Optional transport: fetch Blocket through the Bright Data **Web Unlocker** API.

Since Blocket's 2025 platform move, car search is a plain JSON endpoint that works
with an ordinary GET (see scrapers/blocket.py), so this transport is a *fallback*
for when direct requests get rate-limited or blocked. It overrides only
`_fetch_page`; URL building, parsing and normalization are inherited.

SETUP (only if you need it):
  1. Bright Data account -> add a **Web Unlocker** zone.
  2. `cp .env.example .env` and fill in BRIGHTDATA_API_KEY + BRIGHTDATA_UNLOCKER_ZONE.
  3. python -m scrapers.blocket --probe --transport brightdata
  4. python -m pipeline.run --source blocket --transport brightdata --query "volvo v60"

API: POST https://api.brightdata.com/request, `Authorization: Bearer <API_KEY>`,
body {zone, url, format:"raw", country}. Never combine Web Unlocker with a
headless browser (Bright Data's Browser API exists for that).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from scrapers.blocket import BlocketScraper

try:  # optional convenience: load a local .env
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

UNLOCKER_ENDPOINT = "https://api.brightdata.com/request"
DEFAULT_COUNTRY = "se"   # geo-target Sweden


class BrightDataConfigError(RuntimeError):
    pass


def _config() -> tuple[str, str]:
    api_key = os.environ.get("BRIGHTDATA_API_KEY")
    zone = os.environ.get("BRIGHTDATA_UNLOCKER_ZONE")
    if not api_key or not zone:
        raise BrightDataConfigError(
            "Set BRIGHTDATA_API_KEY and BRIGHTDATA_UNLOCKER_ZONE (see .env.example).")
    return api_key, zone


def unlock(url: str, *, country: str = DEFAULT_COUNTRY, timeout: int = 90) -> str:
    """Fetch a URL through Web Unlocker and return the raw response body."""
    api_key, zone = _config()
    resp = requests.post(
        UNLOCKER_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"zone": zone, "url": url, "format": "raw", "country": country},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


class BlocketBrightDataScraper(BlocketScraper):
    """Same parsing as BlocketScraper, but fetches via Web Unlocker."""

    def __init__(self, delay: float = 1.0, country: str = DEFAULT_COUNTRY, **kwargs):
        super().__init__(delay=delay, **kwargs)
        self.country = country

    def _fetch_page(self, url: str) -> str | None:
        for attempt in range(1, self.max_retries + 1):
            try:
                return unlock(url, country=self.country)
            except BrightDataConfigError as exc:
                print(f"[blocket-bd] {exc}")
                return None
            except requests.RequestException as exc:
                print(f"[blocket-bd] fetch failed (attempt {attempt}/{self.max_retries}): {exc}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        return None
