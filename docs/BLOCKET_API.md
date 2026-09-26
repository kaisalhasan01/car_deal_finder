# Blocket car-search API — what we know and how we know it

*Researched 2026-09-26. The development sandbox could not reach blocket.se (egress policy),
so everything below comes from published sources, not from a response captured by this
project. The first run from a normal connection must be the probe (bottom of this page).*

## TL;DR

In **Nov–Dec 2025 Blocket moved onto the Vend (FINN.no) marketplace platform.** The old
`/bilar/sok` pages with a `__NEXT_DATA__` blob and the token-protected
`api.blocket.se/motor-search-service` are gone. Car search is now a public JSON endpoint that
the website itself calls:

```
GET https://www.blocket.se/mobility/search/api/search/SEARCH_ID_CAR_USED?q=volvo+v60&page=1
```

- **No token, no browser, no unblocker needed**: a plain GET works. Bright Data is now a
  fallback, not a requirement.
- `SEARCH_ID_CAR_USED` is the only valid search key. New cars and leasing are included unless
  you pass `sales_form` (1 = used, 2 = new, 5 = leasing). This project sends `sales_form=1`,
  because leasing ads carry a **monthly** price.
- **Unknown query parameters are silently ignored.** Check `metadata.selected_filters` (the
  probe prints it) and keep client-side filtering as a safety net (`SearchFilters.accepts`).

## Response shape

```jsonc
{
  "docs": [ /* one page of ads */ ],
  "filters": [ /* every facet with hit counts at the current scope */ ],
  "metadata": {
    "result_size": { "match_count": 12345, ... },
    "paging": { "param": "page", "current": 1, "last": 50 },
    "is_end_of_paging": false,
    "selected_filters": [ ... ]           // proof of which params were applied
  }
}
```

### Fields of one ad in `docs[]`

| Field | Example | Notes |
|---|---|---|
| `id` / `ad_id` | `20101001` | stable ad id |
| `main_search_key` | `"SEARCH_ID_CAR_USED"` | |
| `heading` | `"Volvo V60 D4 AWD Momentum"` | listing title |
| `price.amount` | `179900` | SEK; `price.price_unit` may be `kr/mån` for leasing |
| `year` | `2018` | model year |
| `mileage` | `12345` | **Swedish mil** (1 mil = 10 km), see below |
| `make`, `model` | `"Volvo"`, `"V60"` | |
| `model_specification` | `"1.6 HDi FAP Manuell"` | trim/engine; we parse AWD + hp from it |
| `fuel`, `transmission` | `"Diesel"`, `"Automat"` | |
| `regno` | `"XWN111"` | Swedish registration number |
| `dealer_segment` | `"Privat"` / `"Företag"` | private seller vs dealer |
| `organisation_name` | `"Bilhallen AB"` | only for dealers |
| `location` | `"Linköping"` | free text; mapped to municipality + county in `reference/geo_data.py` |
| `coordinates` | `{"lat": .., "lon": ..}` | |
| `timestamp` | `1776254289000` | publish time, epoch **milliseconds** |
| `canonical_url` | `https://www.blocket.se/mobility/item/<id>` | |
| `image` / `image_urls` | | |

**Mileage unit:** sources state that mileage is reported in mil, with
`mileage_unit: "SCANDINAVIAN_MILE"`, and that the `mileage_from`/`mileage_to` params also take mil.
The parser multiplies by 10 and runs a plausibility check on every page. A Swedish car drives
about 1 000–2 000 mil a year, so a median over 5 000 per year of age means the values are
already km. You can force the unit with `--mileage-unit`.

## Query parameters used by this project

| Param | Meaning |
|---|---|
| `q` | free text |
| `page`, `rows` | paging (`rows` optional) |
| `sort` | `PUBLISHED_DESC` (default here), `RELEVANCE`, `PRICE_ASC/DESC`, `MILEAGE_ASC/DESC`, `YEAR_ASC/DESC` |
| `price_from/_to`, `year_from/_to` | ranges |
| `mileage_from/_to` | range in **mil**. blocket-api spells it `milage_*`; browse.sh documents `mileage_*`. Verify with `selected_filters` |
| `make` (repeatable) | e.g. Volvo `0.818`, Volkswagen `0.817` (`scrapers/blocket_codes.py`) |
| `location` (repeatable) | county, e.g. Stockholms län `0.300001` |
| `transmission` | 1 manual, 2 automatic |
| `wheel_drive` | 1 RWD, 2 AWD, 3 FWD |
| `sales_form` | 1 used, 2 new, 5 leasing |

## Sources

- `blocket-api` 0.5.2 (PyPI, 2026-07-19, WTFPL). Its source contains the endpoint URLs, the
  param names and the make/county codes. Versions ≤ 0.3.7 (Nov 2025) still used the old
  `api.blocket.se` endpoints, which dates the migration. <https://pypi.org/project/blocket-api/>
- browse.sh skill *"Blocket Car Search by Filters"*: bare GET works, `sales_form` semantics,
  `selected_filters` caveat, response keys. <https://browse.sh/skills/blocket.se/search-cars-by-filters-we89jq>
- Apify actor listings for Blocket scrapers (field names such as `regno`, `dealer_segment`,
  `organisation_name`, `model_specification`, `timestamp`, and mil → km):
  <https://apify.com/devilscrapes/blocket-sweden-cars>,
  <https://apify.com/memo23/blocket-scraper>
- The same platform (and identical make codes) runs FINN.no in Norway.

## Verifying on a real connection (do this first)

```bash
python -m scrapers.blocket --probe --query "volvo v60"
```

The probe saves the raw JSON to `debug/`, prints the top-level and metadata keys,
`selected_filters`, the field coverage across ads, the first raw ad, the normalized listings,
the mileage-unit decision and a PASS/CHECK verdict. If it says CHECK, the saved file shows what
changed. Adapt `normalize_ad()` / `_find_raw_ads()` in `scrapers/blocket.py`, then replace the
constructed fixtures in `tests/fixtures/` with the real capture.

## Politeness and terms

Personal, low-volume use: a 2 s delay between pages, retries with backoff (honouring
`Retry-After`), a page cap, and raw snapshots under `data/raw/` so re-runs can **replay** instead
of re-fetching (`--source replay`). Read Blocket's terms of use before running anything
scheduled.
