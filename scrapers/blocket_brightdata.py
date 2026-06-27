"""Blocket scraper via the Bright Data **Web Unlocker** API.

Web Unlocker is an HTTP scraping proxy that auto-bypasses bot detection and
CAPTCHAs, so we can fetch real Blocket pages that a plain `requests` call (or
this agent's sandbox) cannot reach. We only override the *fetch* step — all the
`__NEXT_DATA__` parsing is inherited from `BlocketScraper`.

SETUP (one-time, on your machine):
  1. Create a Bright Data account → add a **Web Unlocker** zone.
  2. Copy `.env.example` to `.env` and fill in:
         BRIGHTDATA_API_KEY=...          (Control Panel → Account Settings)
         BRIGHTDATA_UNLOCKER_ZONE=...    (your Web Unlocker zone name)
  3. Confirm it works and inspect the real page structure:
         python -m scrapers.blocket_brightdata --probe "https://www.blocket.se/bilar/sok?q=volvo"
     That saves the HTML + a screenshot and prints the __NEXT_DATA__ keys, so we
     can finalize the field paths in blocket.py against the *actual* response.
  4. Then run the pipeline on real data:
         python -m pipeline.run --source blocket-bd --query "volvo v60" --pages 2

Docs: Web Unlocker → POST https://api.brightdata.com/request, auth via
`Authorization: Bearer <API_KEY>`, body {zone, url, format:"raw", country}.
Note: never combine Web Unlocker with Playwright/Selenium (use the Browser API).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

from scrapers.blocket import BlocketScraper

# Load a local .env if python-dotenv is installed (optional convenience).
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

UNLOCKER_ENDPOINT = "https://api.brightdata.com/request"
DEFAULT_COUNTRY = "se"   # geo-target Sweden — Blocket is a Swedish site


class BrightDataConfigError(RuntimeError):
    pass


def _config() -> tuple[str, str]:
    api_key = os.environ.get("BRIGHTDATA_API_KEY")
    zone = os.environ.get("BRIGHTDATA_UNLOCKER_ZONE")
    if not api_key or not zone:
        raise BrightDataConfigError(
            "Set BRIGHTDATA_API_KEY and BRIGHTDATA_UNLOCKER_ZONE (see .env.example)."
        )
    return api_key, zone


def unlock(url: str, *, country: str = DEFAULT_COUNTRY, data_format: str | None = None,
           timeout: int = 90) -> str:
    """Fetch a URL through Bright Data Web Unlocker and return the response body.

    `data_format="screenshot"` returns PNG bytes (handled by the caller);
    `data_format="markdown"` returns markdown. Default returns raw HTML.
    """
    api_key, zone = _config()
    payload = {"zone": zone, "url": url, "format": "raw", "country": country}
    if data_format:
        payload["data_format"] = data_format

    resp = requests.post(
        UNLOCKER_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.content if data_format == "screenshot" else resp.text


class BlocketBrightDataScraper(BlocketScraper):
    """Same parsing as BlocketScraper, but fetches via Web Unlocker."""

    def __init__(self, delay: float = 1.0, country: str = DEFAULT_COUNTRY):
        super().__init__(delay=delay)
        self.country = country

    def _fetch_page(self, query: str, page: int) -> str | None:
        url = self._page_url(query, page)
        try:
            return unlock(url, country=self.country)
        except (requests.RequestException, BrightDataConfigError) as exc:
            print(f"[blocket-bd] fetch failed for page {page}: {exc}")
            return None


# ---------------------------------------------------------------------------
# Probe: fetch one real page and reveal its structure so we can finalize parsing
# ---------------------------------------------------------------------------
def probe(url: str) -> None:
    print(f"[probe] fetching via Web Unlocker: {url}")
    html = unlock(url)
    out_dir = Path(__file__).resolve().parent.parent / "debug"
    out_dir.mkdir(exist_ok=True)

    (out_dir / "blocket_page.html").write_text(html, encoding="utf-8")
    print(f"[probe] saved HTML -> {out_dir / 'blocket_page.html'} ({len(html):,} bytes)")

    # Optional screenshot for visual confirmation.
    try:
        png = unlock(url, data_format="screenshot")
        (out_dir / "blocket_page.png").write_bytes(png)
        print(f"[probe] saved screenshot -> {out_dir / 'blocket_page.png'}")
    except Exception as exc:  # screenshot is best-effort
        print(f"[probe] screenshot skipped: {exc}")

    data = BlocketScraper._extract_next_data(html)
    if data is None:
        print("[probe] No __NEXT_DATA__ found. Inspect the saved HTML/screenshot — "
              "the page may use a different structure than expected.")
        return

    page_props = data.get("props", {}).get("pageProps", {})
    print(f"[probe] __NEXT_DATA__ pageProps keys: {sorted(page_props.keys())}")
    ads = list(BlocketScraper._iter_raw_ads(data))
    print(f"[probe] candidate ads found: {len(ads)}")
    if ads:
        print("[probe] first ad's keys:", sorted(ads[0].keys())[:40])
        print("[probe] first ad (truncated):")
        print(json.dumps(ads[0], ensure_ascii=False, indent=2)[:1500])
    else:
        print("[probe] Save the JSON and locate the ads array; update "
              "BlocketScraper._iter_raw_ads / _normalize accordingly.")


def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Blocket via Bright Data Web Unlocker")
    ap.add_argument("--probe", metavar="URL", help="fetch one real page and dump its structure")
    ap.add_argument("--query", default="volvo v60")
    ap.add_argument("--pages", type=int, default=1)
    args = ap.parse_args()

    if args.probe:
        probe(args.probe)
        return

    scraper = BlocketBrightDataScraper()
    for i, item in enumerate(scraper.search(query=args.query, pages=args.pages)):
        print(item)
        if i >= 19:
            break


if __name__ == "__main__":
    # Allow `python -m scrapers.blocket_brightdata` and `python scrapers/blocket_brightdata.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    _main()
