---
name: car-deal-digest
description: Run the Swedish Car Deal Finder pipeline and produce a personalized top-deals digest with TCO and known-issues briefing. Use when Kais wants fresh Blocket deals or to test the pipeline.
---

# Car deal digest

**When to use:** Kais wants car deals from Blocket, or wants to run or verify this project's
pipeline. Run everything from the repo root.

**Interpreter:** Windows (Git Bash) uses `PY=.venv/Scripts/python.exe`; macOS uses
`PY=.venv/bin/python`. If `.venv` is missing, run `py -3 -m venv .venv && $PY -m pip install -r requirements.txt` first.

## Steps, in order

1. Check `.env` for `BRIGHTDATA_API_KEY` and `BRIGHTDATA_UNLOCKER_ZONE`. **Don't print the
   values.** If they're missing, only **sample mode** works. Say so explicitly, and never
   present its output as real listings. (As of 2026-09-26 there is no `.env`.)
2. The first real run ever must be the probe, to confirm the parser:
   `$PY -m scrapers.blocket_brightdata --probe "https://www.blocket.se/bilar/sok?q=volvo"`
   It saves HTML + a screenshot to `debug/` and reveals Blocket's actual `__NEXT_DATA__`
   paths, so the `TODO`s in `scrapers/blocket.py` (`_iter_raw_ads` / `_normalize`) can be
   finalized. Don't run the full pipeline on real data before the paths are confirmed.
3. Run the ETL:
   - real: `$PY -m pipeline.run --source blocket-bd --query "volvo v60" --pages 2`
   - demo: `$PY -m pipeline.run --source sample --limit 200`
4. Ask for (or reuse) Kais's buyer profile, then generate the shortlist:
   `$PY -m pipeline.recommend --budget 220000 --min-year 2016 --drivetrain AWD,FWD --body Kombi,SUV --max-insurance 800`
   Optional personal insurance factors: `--driver-age`, `--claims-free-years`, `--home-city`.
   **Caveat:** `recommend.py` currently always generates sample data and does not read
   `car_deals.db` (HANDOFF.md §8.2). Until that's fixed, its shortlist is sample-only even
   after a real ETL run. Say so.
5. Relay the shortlist with all four layers intact: match score, price vs value, cost of
   ownership per year, and the known-issues briefing with negotiation room.

## Real output (captured 2026-09-26, sample mode)

Command: `recommend --budget 220000 --min-year 2016 --body Kombi,Halvkombi --max-insurance 800 --max-lphmil 6.0 --top 3`

```
==========================================================================
  DINA TOPPMATCHNINGAR
  Profil: budget ≤ 220 000 kr, kaross Halvkombi/Kombi, ≤ 6.0 L/100km, försäkring ≤ 800/mån, ≥ 2016
==========================================================================

[1] Toyota Corolla 2021   — Match 67/100
    Pris 128 000 kr  (värde ~161 206 kr  rabatt +21%)  ·  78 838 km
    Halvkombi · FWD · Hybrid · 122 hk · pålitlighet 5/5
    Kostnad/år ~21 870 kr  (försäkring 580/mån  bränsle 12 210, skatt 700, reparationsreserv 2000)
    Att kolla / pruta på:
      🟡 Hybridbatteriets hälsa på äldre exemplar
         → Be om hybridbatteri-hälsotest hos Toyota. I övrigt mycket pålitlig modell.
    💬 Förhandlingsutrymme att verifiera: ~8 000 kr
```

Severity markers: 🔴 high · 🟠 medium · 🟡 low. 🚩 marks red flags ("too good to be true"
discounts > 35 %, high mileage for the car's age).

## Mistakes to avoid

- **Ranking by discount alone.** This was Kais's explicit mid-project correction: he'd rather
  help private people than margin hunters. The tool matches cars to *a person*.
- **Presenting sample data as real deals.** Sample mode is an offline demo. Label it.
- **Dropping the known-issues briefing.** "Att kolla / pruta på" is the product's
  differentiator.
- **Trusting the discount % blindly.** The comparables fallback inflates discounts on older
  cars until year-aware valuation lands (HANDOFF.md §8.1). Caveat it.
- **Skipping the probe.** Unconfirmed JSON paths produce silently empty or wrong data.
