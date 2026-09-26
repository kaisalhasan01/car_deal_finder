# Car Deal Finder — notes for Claude Code

On a new machine or a first session, read **`HANDOFF.md`** once: the full vision, decisions,
history and weaknesses. This file is the short version.

## What it is

A personal **car-buying advisor for private buyers** on Blocket. A buyer profile goes in:
budget, insurance ceiling, drivetrain, body type, L/100km, fuel, mileage, year. A ranked
shortlist comes out, with the market-value discount, estimated TCO per year, and a
known-issues "check / haggle on" briefing. Python + SQLite star schema, with real data via
Bright Data Web Unlocker. It's a CV/portfolio project for Kais (mechanical engineering, LiU).

## Non-negotiables

- **Never rank by discount alone.** The match score weighs deal, reliability, economy and
  budget headroom. This was Kais's explicit pivot.
- **Never present sample data as real listings.** Label estimates (valuation, insurance,
  specs, negotiation SEK) as estimates.
- Talk to Kais in **Swedish**, narrate as you go. Code, comments and commits in **English**.
- Keep the repo **out of OneDrive-synced folders** (it vanished from one once).
- No dev server exists. If a front-end is added, use `.claude/launch.json` + `preview_start`
  and never give manual terminal instructions.

## Commands

Windows (Git Bash): `PY=.venv/Scripts/python.exe` · macOS: `PY=.venv/bin/python`

```bash
py -3 -m venv .venv && $PY -m pip install -r requirements.txt     # setup
$PY -m pipeline.run --source sample --limit 200                    # ETL, offline demo
$PY -m pipeline.recommend --budget 220000 --min-year 2016 --drivetrain AWD,FWD \
    --body Kombi,SUV --max-insurance 800 --driver-age 30 --home-city Stockholm
$PY -m scrapers.blocket_brightdata --probe "https://www.blocket.se/bilar/sok?q=volvo"  # needs .env
$PY -m pipeline.run --source blocket-bd --query "volvo v60" --pages 2   # only after probe
```

The verification baseline (exact expected output) is in `HANDOFF.md` §6.

## Status (2026-09-26)

- ✅ Sample ETL, star schema + reference tables, advisor CLI, calibrated insurance,
  Bright Data integration code.
- ⛔ Real data blocked: Kais hasn't created a Bright Data Web Unlocker zone / `.env` yet.
  Blocket `__NEXT_DATA__` paths in `scrapers/blocket.py` are unverified `TODO`s.
- ⚠️ `recommend.py` only uses sample data (never reads the DB). The comparables valuation
  inflates discounts on older cars. No tests.
- Next steps, in order: set up on PC → private GitHub → probe + finalize parser →
  advisor-from-DB → year-aware valuation → pytest → front-end (Claude's call: Streamlit
  advisor + Power BI overview).

## Conventions

- Scrapers return the `Listing` dataclass shape. A new source = subclass `BlocketScraper` and
  override `_fetch_page` only.
- Reference data lives in `reference/*.py` as the single source of truth; the DB loaders read
  the same lists.
- `matcher.py`: hard filters exclude, the score ranks. Keep the two separate.
- Mileage is **km internally**. Blocket shows *mil* (×10).
- Secrets live in `.env` (gitignored). The template is `.env.example`.
