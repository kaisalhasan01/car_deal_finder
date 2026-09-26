---
name: car-deal-digest
description: Run the Swedish Car Deal Finder pipeline and produce a personalized top-deals digest with TCO and known-issues briefing. Use when Kais wants fresh Blocket deals or to test the pipeline.
---

# Car deal digest

**When to use:** Kais wants car deals from Blocket, or wants to run or verify this project's
pipeline. Run everything from the repo root.

**Interpreter:** Windows (Git Bash) uses `PY=.venv/Scripts/python.exe`; macOS/Linux uses
`PY=.venv/bin/python`. If `.venv` is missing, create it and run
`$PY -m pip install -r requirements-dev.txt`.

## Steps, in order

1. **Probe first, on a new machine or when results look odd.** Blocket's public JSON API needs
   no key:
   `$PY -m scrapers.blocket --probe --query "volvo v60"`
   It saves the raw JSON to `debug/` and prints field coverage, `selected_filters` (which
   params Blocket applied) and a **PASS/CHECK** verdict. On CHECK, read the saved file and
   adapt `normalize_ad()` / `_find_raw_ads()` in `scrapers/blocket.py` before running the ETL.
   If direct requests are blocked, add `--transport brightdata` (needs `.env`).
2. **Run the ETL** into `car_deals.db`:
   - real: `$PY -m pipeline.run --source blocket --query "volvo v60" --pages 5`
     (or `--make Volvo,Toyota --county "Östergötlands län"`, `--price-max`, `--year-min` …)
   - offline re-run from saved pages: `$PY -m pipeline.run --source replay --replay data/raw/blocket/<date>`
   - demo only: `$PY -m pipeline.run --source sample` → `car_deals_sample.db` (never mixed with real)
3. **Ask for (or reuse) Kais's buyer profile**, then:
   `$PY -m pipeline.recommend --budget 220000 --min-year 2016 --body Kombi,SUV --max-insurance 800 --seller private`
   It reads `car_deals.db` automatically. Without real data it prints a loud **DEMO** banner.
   Optional: `--driver-age`, `--claims-free-years`, `--home-city`, `--drivetrain AWD`,
   `--fuel Hybrid`, and `--json` for machine-readable output.
4. **Relay the shortlist** with every layer intact: match score, price vs value (with interval
   and confidence), cost per year, known issues + negotiation room, general checks, seller
   rights (köplagen/konsumentköplagen) and the car.info history link when a regnr exists.

## Mistakes to avoid

- **Ranking by discount alone.** This was Kais's explicit correction. The tool matches cars to
  *a person*.
- **Presenting sample/demo data as real deals.** Check the `Data:` line and the demo flag.
- **Trusting a big discount with `säkerhet låg`.** Few comparables mean the discount can be an
  artefact. Say so.
- **Dropping the briefing.** "Att kolla / pruta på" is the product's differentiator.
- **Skipping the probe after a Blocket site change.** Unverified fields produce silently wrong data.
