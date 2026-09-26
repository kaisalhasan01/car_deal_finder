# Briefing for the reviewing model (Kimi)

You are being asked to **review this project and suggest improvements**. This
document is written by the AI assistant (Claude) that built the project together
with its owner, and it is intentionally self-contained: you should be able to
understand the idea, every design decision, the current state, and the known
weaknesses **without the owner explaining anything**. Be as critical as you
like — honest, specific feedback is exactly what we want.

---

## 1. The idea (and an important pivot)

**"Swedish Car Deal Finder & Buyer Advisor"** — a Python data project that helps
a **private person** buy the right used car on Blocket (Sweden's biggest
classifieds site), visualized in Power BI later.

It started as a pure arbitrage tool: scrape Blocket listings, compare each
asking price against an estimated market value, rank by
`discount_pct = (value - price) / value * 100`.

The owner then made a deliberate **ethical/product pivot**: he'd rather help
private buyers than build a margin-squeezing tool. The product is now a
**personal buying advisor**:

- The buyer states preferences: budget, max insurance cost/month, drivetrain
  (FWD/RWD/AWD), body type (kombi/sedan/SUV/...), fuel economy ceiling
  (L/100km), fuel type, mileage/year limits.
- The tool returns a **ranked personal shortlist**, where the "deal" (discount)
  is only one factor among reliability, running economy and budget headroom.
- Each recommended car comes with an estimated **total cost of ownership per
  year** (insurance + fuel + vehicle tax + a reliability-driven repair reserve)
  and an auto-generated **viewing briefing**: known common faults for that
  model/year range, what to inspect, and an indicative **negotiation leverage
  in SEK** (e.g. "Audi A4 2008–2012 2.0 TFSI burns oil — check if the piston
  ring fix was done; ~15 000 kr leverage").

A hard product rule from the owner: **never rank cars by discount alone.**

Context that matters for your review: the owner is a mechanical engineering
student building this as a **CV/portfolio project**. So architectural clarity,
honest data-quality reasoning and demonstrable end-to-end function are worth
more than raw feature count. It should eventually run on real data.

## 2. Tech stack and the three chosen strategies

Stack: **Python** (no framework yet), **SQLite** star schema (PostgreSQL
planned later), **Power BI** planned as dashboard, plain **requests +
BeautifulSoup** for scraping, **Bright Data Web Unlocker** for real fetches.

Three explicit strategy decisions were made by the owner when offered options:

1. **Market value = hybrid.** car.info (a Swedish vehicle-data site) has no
   public valuation API and its valuation needs a registration number, which
   Blocket listings don't expose. So: try car.info by regnr (currently a
   **stub** that returns None, off by default), and fall back to
   **comparables**: median price of the same brand+model+year cohort from the
   scraped listings themselves, adjusted for mileage. The comparables path is
   what actually produces every number today.
2. **Sample-data first.** The whole pipeline runs end-to-end on realistic
   synthetic listings (`scrapers/sample_data.py`), so everything is
   demonstrable offline; the real scraper is a pluggable module.
3. **requests + BeautifulSoup** rather than Playwright for the scraper itself,
   with the heavy lifting delegated to Bright Data (below).

## 3. Repository tour

```
car-deal-finder/
├── scrapers/
│   ├── blocket.py             # Blocket scraper draft. Parses the __NEXT_DATA__
│   │                          # JSON blob (Blocket is a Next.js app) instead of
│   │                          # CSS selectors. FIELD PATHS ARE UNVERIFIED (TODO
│   │                          # markers) — see §6. Listing dataclass = the
│   │                          # normalized shape every scraper must return.
│   ├── blocket_brightdata.py  # Real-data path. Subclasses BlocketScraper and
│   │                          # overrides ONLY _fetch_page to call Bright Data's
│   │                          # Web Unlocker REST API (geo-targeted country=se).
│   │                          # Includes a --probe CLI that fetches one real page,
│   │                          # saves HTML+screenshot to debug/, and dumps the
│   │                          # __NEXT_DATA__ structure so the TODO field paths
│   │                          # can be confirmed against reality.
│   ├── carinfo.py             # The hybrid valuer (CarInfoValuer). Builds tiered
│   │                          # cohorts: (brand,model,year) → (brand,model) →
│   │                          # (brand,year), uses the first with ≥3 prices,
│   │                          # median price ± 1.0 kr/km mileage adjustment.
│   └── sample_data.py         # Synthetic listings: 10 models × 2013–2022,
│                              # price = new_price·depreciation^age ± noise,
│                              # ~18% of cars deliberately underpriced 10–20%.
├── reference/                 # Curated domain knowledge (NOT scraped)
│   ├── specs_data.py          # One spec row per (brand, model): body type,
│   │                          # drivetrain, hp, fuel, L/100km or kWh/100km,
│   │                          # annual tax, reliability 1–5. Approximate values.
│   ├── known_issues_data.py   # 14 curated common faults with year ranges,
│   │                          # severity, what-to-check text, negotiation SEK.
│   └── lookup.py              # get_spec(brand,model), get_issues(brand,model,year)
├── database/
│   ├── schema.sql             # Star schema: fact_listings + dim_car,
│   │                          # dim_location, dim_time (date_id=YYYYMMDD) +
│   │                          # reference tables car_specs, known_issues.
│   │                          # fact.url is UNIQUE → re-runs upsert, not dupe.
│   │                          # fact.value_method records 'carinfo'|'comparables'.
│   └── db.py                  # Connection, schema init, dimension get-or-create
│                              # upserts, fact load (ON CONFLICT(url) DO UPDATE),
│                              # loaders for the two reference tables.
├── pipeline/
│   ├── run.py                 # ETL entry: --source sample|blocket|blocket-bd,
│   │                          # fetch → value → discount → load SQLite.
│   ├── insurance.py           # Heuristic monthly premium estimator, calibrated
│   │                          # against published Swedish figures (see §5).
│   ├── matcher.py             # The advisor engine. BuyerProfile dataclass →
│   │                          # hard filters → TCO → 0–100 match score →
│   │                          # briefing (issues, red flags, negotiation room).
│   └── recommend.py           # CLI: buyer preferences as flags → printed
│                              # ranked shortlist with full briefing per car.
├── analysis/queries.sql       # 8 ready SQL queries for Power BI (top deals,
│                              # discount by brand/county, spec-enriched base
│                              # table, per-listing issue briefing, negotiation
│                              # room per model/year).
├── requirements.txt           # requests, beautifulsoup4, lxml, pandas, python-dotenv
└── .env.example               # BRIGHTDATA_API_KEY + BRIGHTDATA_UNLOCKER_ZONE
```

Environment note: developed on macOS with system Python 3.9. All modules use
`from __future__ import annotations`, so the `X | None` annotations are fine
on 3.9.

## 4. The matcher in detail (the heart of the product)

`pipeline/matcher.py`:

- **Hard filters** (fail → car excluded): budget, max mileage, min year,
  drivetrain set, body-type set, fuel set, max L/100km, max insurance/month.
- **TCO/year** = insurance·12 + fuel cost (from spec consumption × annual km ×
  fuel price constants: petrol 18.5, diesel 19.5 kr/l, el 2.8 kr/kWh) +
  vehicle tax + repair reserve. Repair reserve = `(6 − reliability) × 2000`
  kr/yr, so a 5★ Toyota reserves 2 000 and a 2★ car 8 000.
- **Match score 0–100** = weighted normalized sum, default weights:
  deal 0.35, reliability 0.25, economy 0.20, budget headroom 0.20.
  Normalizations are linear clamps, e.g. deal: −5% → 0, +30% → 1.
- **Briefing**: known issues sorted by severity, total negotiation leverage
  summed in SEK, red flags ("discount > 35% — too good to be true, suspect
  hidden faults or scam", "mileage > 3 000 mil/yr for its age").

`pipeline/insurance.py` (see §5 for calibration): base 300 + 0.0014·car_value
+ 1.5 kr/hp above 120 hp, ×1.2 Stockholm / ×1.1 Gbg+Malmö, ×1.8 under-25 /
×1.3 under-30, ×0.55–1.4 claims-free bonus factor, +40 kr if car ≥12 years.

## 5. What is verified working (actual observed outputs)

All commands below were run and their output inspected.

**ETL:** `python -m pipeline.run --source sample --limit 200` →
"loaded 200 listings, 10 specs, 14 known issues", creates `car_deals.db` with
all 6 tables populated.

**Advisor CLI:**
`python -m pipeline.recommend --budget 220000 --min-year 2016 --body Kombi,Halvkombi --max-insurance 800 --max-lphmil 6.0`
produced (excerpt):

```
[1] Toyota Corolla 2021   — Match 67/100
    Pris 128 000 kr  (värde ~161 206 kr  rabatt +21%)  ·  78 838 km
    Halvkombi · FWD · Hybrid · 122 hk · pålitlighet 5/5
    Kostnad/år ~20 070 kr  (försäkring 430/mån  bränsle 12 210, skatt 700, reparationsreserv 2000)
    Att kolla / pruta på:
      🟡 Hybridbatteriets hälsa på äldre exemplar
    💬 Förhandlingsutrymme att verifiera: ~8 000 kr
```

Filter correctness spot-checks: an AWD-only profile returns only Volvo XC60
(the sole AWD model in specs); a Golf 2019 correctly shows "no known issues"
because the Golf faults are registered for 2008–2016 (year-range filtering
works).

**Insurance calibration** (against published Swedish figures: average
helförsäkring ≈ 584 kr/month [Hedvig], common range 500–830, Stockholm ≈ +40%,
under-25 ≈ 2×, claims-free bonus up to ~55% off):

```
Typical car (150k SEK, 150 hp), adult:       560 kr/mo   (target ≈ 584 avg)
Stockholm, age 23, 0 bonus years:           1680 kr/mo
Rural, age 45, 10 bonus years:               330 kr/mo
Tesla (380k, 283 hp), adult:                1080 kr/mo
Old cheap car (50k, 110 hp, 13 yrs):         410 kr/mo
```

**Git:** 3 clean commits, working tree clean. (The `.git` folder is excluded
from this export.)

## 6. Honest weaknesses — the things we most want your opinion on

1. **The valuation has a known structural flaw.** With ~200 listings across
   10 models × 10 model years, the exact (brand, model, year) cohort rarely
   reaches MIN_COHORT_SIZE=3, so the valuer falls back to (brand, model)
   pooling — which compares a 2013 car against a median dominated by newer,
   more expensive cars. Result: old cars show absurd "discounts" (we observed
   40–62% on sample data). The Power BI queries mask this with a
   `discount BETWEEN 5 AND 40` filter, but that treats the symptom. Planned
   fix: make the comparable value **year/age-aware** (either a per-model
   depreciation bridge, or a small hedonic regression of price on age +
   mileage within brand+model). **Question to you: what's the best
   lightweight approach at n≈200–2 000 listings, and would you structure the
   fallback tiers differently?**
2. **Blocket's JSON shape is unverified.** The agent's environment cannot
   reach blocket.se at all (fetch refused), so `_iter_raw_ads`/`_normalize` in
   `scrapers/blocket.py` guess field names behind `TODO` markers. The
   `--probe` tool exists precisely to close this gap, but it needs the owner's
   Bright Data API key and has **not been run yet**. Until then, `--source
   blocket-bd` returns real HTML whose parsing may yield zero listings.
3. **Reference data is approximate.** `car_specs` has one representative row
   per (brand, model) — it ignores generations, engines and trim levels (a
   "Golf" row claims 125 hp petrol regardless of generation). `known_issues`
   has 14 hand-curated entries; the facts are real, community-known issues,
   but negotiation SEK values are rough. **Is one-spec-per-model an acceptable
   v1 simplification, or would you restructure (e.g. per-generation rows keyed
   by year ranges) now before more data is added?**
4. **The insurance model is a heuristic**, not a quote. No public Swedish
   premium API exists (quotes require personnummer). We calibrated against
   published averages and made it transparent + overridable. Improvements
   welcome.
5. **Units:** mileage is kilometres internally, but Blocket displays Swedish
   "mil" (1 mil = 10 km). Conversion must happen in the live scraper's
   normalize step — flagged in comments, easy to get wrong.
6. **No tests.** There are no unit tests at all; verification has been manual
   CLI runs. If you suggest a test strategy, the valuer cohort logic, the
   matcher filters and the insurance multipliers are the highest-value
   targets.
7. **Sample data realism**: prices come from a depreciation curve the valuer
   partially re-discovers, so sample-data discounts are somewhat circular —
   fine for demos, useless for validating the valuation method itself.

## 7. Where we are / what's next (owner's open decisions)

Done: structure, star schema + reference tables, ETL, hybrid valuer, advisor
engine + CLI, calibrated insurance, Bright Data integration + probe tool,
git history, README with roadmap.

Immediate next actions, in intended order:
1. Owner creates a Bright Data account, fills `.env`, runs the probe →
   paste output back → finalize the real Blocket parser.
2. Fix the year-aware valuation (§6.1).
3. Choose and build the front-end: **Power BI dashboard** (original plan,
   queries are ready) vs **Streamlit app** (the advisor is naturally
   interactive). The owner said "whatever is highest level" — an argued
   recommendation from you would genuinely help.
4. Expand specs/known-issues coverage once real listings show which models
   dominate the market.
5. SQLite → PostgreSQL later (schema is portable on purpose).

## 8. What we'd like from you

Concretely:
1. **Critique the valuation approach** and propose the year/mileage-aware
   method you'd use at this data scale (§6.1).
2. **Sanity-check the match-score design** — weights, linear clamps, whether
   score components should be user-adjustable, anything conceptually wrong.
3. **Review the schema** — the star design, dim_car granularity (color in the
   natural key?), the (brand, model) reference-table keying vs generations.
4. **Assess the scraping architecture** — the __NEXT_DATA__ strategy, the
   subclass-only-fetch Bright Data design, error handling, politeness.
5. **Recommend the front-end** (Power BI vs Streamlit vs both, and why).
6. **Point out anything to cut or simplify** — over-engineering is a real
   risk in a portfolio project.
7. Any bugs you can spot by reading the code.

Everything runs offline: `python3 -m venv .venv && source .venv/bin/activate &&
pip install -r requirements.txt`, then
`python -m pipeline.run --source sample --limit 200` and
`python -m pipeline.recommend --budget 220000 --min-year 2016`.

Thank you — be blunt.
