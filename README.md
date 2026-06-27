# Swedish Car Deal Finder & Buyer Advisor

Help a **private buyer** find the right used car on **Blocket** — not just the
cheapest. The tool compares each listing's price to an estimated market value,
then ranks cars by how well they fit *that buyer's* preferences, shows the real
**total cost of ownership**, and generates a **"what to check / haggle on"**
briefing from a curated knowledge base of common faults.

> Example: an Audi A4 (2.0 TFSI, ~2008–2011) is a known oil-burner — the advisor
> flags it, tells you what to inspect, and gives you ~15 000 kr of negotiation
> leverage to verify.

## How it works

```
Blocket listings ─▶ market value (hybrid) ─▶ discount_pct ─┐
                                                           ├─▶ SQLite (star schema + reference tables) ─▶ Power BI
car_specs (curated)  ─▶ drivetrain / body / L100 / tax  ───┤
known_issues (curated) ─▶ faults / checks / haggling room ─┘
                                                           └─▶ buyer-advisor engine ─▶ personalized shortlist (CLI)
```

- **Market value (hybrid):** car.info-by-regnr lookup (best-effort, off by
  default) → **comparables fallback** (mileage-adjusted cohort median).
- **Buyer advisor:** hard filters (budget, mileage, year, drivetrain, body type,
  fuel economy, fuel, max insurance) + a 0–100 match score (deal · reliability ·
  economy · budget headroom) + estimated TCO + a known-issues briefing.

## Project structure

```
car-deal-finder/
├── scrapers/
│   ├── blocket.py          # requests + BeautifulSoup (parses __NEXT_DATA__ JSON)
│   ├── carinfo.py          # hybrid market-value estimator
│   └── sample_data.py      # synthetic listings (offline demo)
├── reference/
│   ├── specs_data.py       # curated technical specs per model
│   ├── known_issues_data.py# curated 'vanliga fel' knowledge base
│   └── lookup.py           # spec / issue lookup helpers
├── database/
│   ├── schema.sql          # star schema + car_specs + known_issues
│   └── db.py               # connection, loaders
├── pipeline/
│   ├── run.py              # ETL: listings -> value -> discount -> SQLite
│   ├── insurance.py        # heuristic monthly-premium estimator
│   ├── matcher.py          # the buyer-advisor engine (filters, scoring, TCO, briefing)
│   └── recommend.py        # personalized advisor CLI
├── analysis/queries.sql    # ranking + buyer-advisor SQL for Power BI
├── requirements.txt · README.md
```

## Setup

```bash
cd ~/Projects/car-deal-finder
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run it

```bash
# 1) Build the database from synthetic listings (+ load reference tables)
python -m pipeline.run --source sample --limit 200

# 2) Get a personalized shortlist
python -m pipeline.recommend --budget 220000 --min-year 2016 \
    --drivetrain AWD,FWD --body Kombi,SUV --max-insurance 800
```

Then open `car_deals.db` in Power BI / DB Browser and use `analysis/queries.sql`
(query 5 is the enriched base table for buyer slicers).

## ⚠️ Notes & honesty

- **Scraping:** the Blocket scraper is a best-effort draft (JSON paths marked
  `TODO`). Blocket blocks bots and changes markup — personal/educational use only,
  respect robots.txt and their ToS. The sample-data mode demonstrates everything
  without touching the live site.
- **Insurance** is a transparent *estimate* (no public premium API exists in SE).
- **Known issues** are indicative, community-known faults — a guide for asking the
  right questions, **not** a substitute for a professional inspection/test drive.
- **Specs / tax** values are approximate and representative; refine from car.info.

## Roadmap

- [x] Star-schema SQLite, end-to-end pipeline on sample data
- [x] Hybrid valuer (comparables + car.info stub)
- [x] Buyer-advisor engine: specs, known-issues KB, insurance estimate, TCO, scoring
- [ ] Year/age-aware comparable valuation (current cohort fallback inflates discounts)
- [ ] Confirm Blocket `__NEXT_DATA__` field paths against live responses
- [ ] Power BI dashboard (.pbix) + optional interactive front-end (Streamlit)
- [ ] Expand specs & known-issues coverage; migrate SQLite → PostgreSQL
```
