# Car Deal Finder — notes for Claude Code

On a new machine or a first session, read **`HANDOFF.md`** (vision, decisions, history) and
the latest session log **`docs/SESSIONSLOGG_2026-09-26.md`** (what changed since). This file
is the short version.

## What it is

A personal **car-buying advisor for private buyers** on Blocket. A buyer profile goes in:
budget, insurance ceiling, drivetrain, body type, L/100km, fuel, mileage, year, seller type.
A ranked shortlist comes out, with market value and interval, TCO per year and a known-issues
"check / haggle on" briefing. Python + SQLite star schema + hedonic valuation, with a
Streamlit app, a FastAPI service and a Power BI kit. It's a CV/portfolio project for Kais
(mechanical engineering, LiU).

## Non-negotiables

- **Never rank by discount alone.** The match score weighs deal, reliability, economy and
  budget headroom. This was Kais's explicit pivot.
- **Never present sample data as real listings.** Sample → `car_deals_sample.db`, real →
  `car_deals.db`; the ETL refuses to mix them. Every UI/API output carries a demo flag. Label
  estimates (valuation, insurance, specs, negotiation SEK) as estimates.
- Talk to Kais in **Swedish**, narrate as you go. Code, comments and commits in **English**.
- Keep the repo **out of OneDrive-synced folders** (it vanished from one once).
- Front-ends start via `.claude/launch.json` (Streamlit 8501, API 8000). Never give manual
  multi-terminal instructions.

## Commands

Windows (Git Bash): `PY=.venv/Scripts/python.exe` · macOS/Linux: `PY=.venv/bin/python`

```bash
$PY -m pip install -r requirements-dev.txt                        # setup
$PY -m pytest                                                     # 72 offline tests
$PY -m pipeline.run --source sample                               # demo DB
$PY -m scrapers.blocket --probe --query "volvo v60"               # FIRST real-data step
$PY -m pipeline.run --source blocket --query "volvo v60" --pages 5
$PY -m pipeline.run --source replay --replay data/raw/blocket/<date>
$PY -m pipeline.recommend --budget 220000 --body Kombi,SUV --seller private   # reads the DB
$PY -m analysis.sql_runner --list
$PY -m analysis.evaluate_valuation --write
$PY -m pipeline.export --format parquet                           # -> powerbi/data/
```

## Status (2026-09-26, after the cloud session)

- ✅ Blocket client rewritten for the post-2025 public JSON API
  (`mobility/search/api/search/SEARCH_ID_CAR_USED`), which needs no key. Bright Data is optional.
- ✅ Hierarchical hedonic valuation (LOO, intervals, guards) beats the old cohort medians
  (`docs/VALUATION_EVAL.md`). Schema v2 with price history and sold detection. The advisor
  reads the DB. Streamlit app, FastAPI, SQL catalog and exercises, Power BI kit. 72 tests.
- ⛔ **Live Blocket never fetched from here.** The cloud sandbox blocks blocket.se. Fixtures are
  constructed from documentation. Run the probe on a normal connection before trusting real
  runs, then replace `tests/fixtures/` with a real capture.
- ⚠️ Reference data is approximate (76 models / 126 variants / 47 issues). `.claude/launch.json`
  and `powerbi/theme.json` are untested in their host apps.

## Conventions

- Every source returns the `Listing` shape (`scrapers/blocket.py`). A new transport subclasses
  `BlocketScraper` and overrides `_fetch_page(url)` only.
- Mileage is **km internally**. Blocket reports *mil* (×10), and `_mileage_factor` checks
  plausibility per page.
- Reference data lives in `reference/*.py` as the single source of truth; the DB loaders read
  the same lists. What the ad states (fuel, AWD, hp) beats the curated spec.
- `matcher.py`: hard filters exclude, the score ranks. Keep the two separate.
- Valuation happens in the ETL over every ad seen in the last 90 days. The app/API refit the
  valuer per ETL run (cached).
- Schema changes: bump `SCHEMA_VERSION` in `database/db.py`. Views are recreated on init.
- Secrets live in `.env` (gitignored). The template is `.env.example`.
