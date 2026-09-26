# Swedish Car Deal Finder & Buyer Advisor — complete project handoff

**Written:** 2026-09-26, when Kais moved development from his Mac to his PC.
**State at handoff:** commit `d484c8d` + this handoff commit. Working tree clean, **no git remote**.

> **To Claude Code on the new machine:** read this whole file once, on your first session.
> It replaces the entire earlier conversation — Kais should never have to re-explain the
> project. After that, `CLAUDE.md` is the short version loaded every session.
> Talk to Kais in **Swedish**; code, comments and commits in **English**.

---

## 1. TL;DR

- A **personal car-buying advisor for private buyers** on Blocket (Sweden's largest
  classifieds site). Given a buyer profile — budget, max insurance per month, drivetrain,
  body type, fuel economy, fuel, mileage, model year — it ranks used cars *for that person*,
  with estimated **total cost of ownership per year** and a **"what to check / haggle on"
  briefing** from a curated known-faults knowledge base.
- It began as a pure deal finder (Blocket price vs market value). Kais pivoted it: he wants to
  help private people, not margin hunters. **Hard rule: never rank by discount alone.**
- **Works end-to-end on synthetic sample data:** ETL → SQLite star schema → advisor CLI.
  Exact verification baseline in §6.
- **The real-data path is built but has never run:** a Bright Data Web Unlocker scraper and a
  probe tool are waiting for Kais's Bright Data account/key. Blocket's JSON field paths are
  still unverified guesses (`TODO`).
- **Biggest known flaws:** the comparables valuation inflates discounts on older cars (§8.1),
  and `recommend.py` only ever uses sample data and never reads the database (§8.2).
- Stack: Python 3.9+ · requests · BeautifulSoup/lxml · pandas · python-dotenv · SQLite ·
  Bright Data. The front-end (Power BI and/or Streamlit) is not built yet.
- **First job on the PC:** set up and verify against the baseline (§6), then offer a private
  GitHub repo — today the project exists on one laptop only.

---

## 2. The vision

### Brief 1 — the original idea (2026-06-17, verbatim, trimmed)

> Hej! Jag vill bygga ett end-to-end data-projekt som jag kallar "Swedish Car Deal Finder".
> Målet är att hitta undervärderade bilar på Blocket genom att jämföra listningspriset mot
> marknadsvärdet från car.info – och visualisera allt i Power BI.
>
> En bil som ligger ute på Blocket för 90 000 kr men värderas till 100 000 kr på car.info
> har en "rabatt" på 10%. Jag vill hitta och ranka dessa deals automatiskt.
>
> Tech stack: Python (scraping + databearbetning), SQLite till en början (senare
> PostgreSQL), Power BI för dashboard och visualisering.
>
> [Star schema: `fact_listings`(listing_id, car_id, location_id, date_id, blocket_price,
> carinfo_value, discount_pct, mileage, days_on_market, url) · `dim_car`(brand, model, year,
> fuel_type, gearbox, color) · `dim_location`(city, county) · `dim_time`(date, week, month, year)]
>
> Bygg: Blocket-scraper (märke, modell, år, miltal, pris, stad, url) · car.info-uppslag
> (märke + modell + år → marknadsvärde) · discount_pct = (carinfo_value − blocket_price) /
> carinfo_value × 100 · spara till SQLite · SQL-queries som rankar de bästa deals.

### Brief 2 — the pivot (verbatim)

> Okej en sak jag kom på är att jag vill hellre hjälpa privata personer än företag som
> försöker pressa ut varenda krona från folket. Så istället för att endast ge bästa priset
> vill jag även att vi ska hitta en lista på bästa bilar för en viss person anpassade efter
> deras val, exempelvis vad har de för budget på försäkringen/månad? Vill de ha bakdrivna,
> framdrivna eller alldrive bilar? Hur bensinsnåla ska de vara x L/100km? Vill du ha en
> kombi, sportbil eller något annat? utöver befintliga filter såsom miltal, årsmodell, pris
> osv. Det ska även finnas en lista på vanliga fel på denna bilen, vad de ska akta sig för och
> vad som de kan pruta ner priset med. Exempelvis en audi från 2011 brukar bränna motorolja,
> se över ifall det är åtgärdat! osv. Kom på egna förslag, allt är välkommet!

### Brief 3 — the ambition level (verbatim)

> Spelar ingen roll, jag vill ha ett fungerande projekt som är på högsta möjliga nivån.
> Med real data från blocket, försäkringsbolag osv.

### Product values that follow

- **Buyer-first.** The discount is one signal among reliability, running costs and budget fit.
  The match score exists *because of* the pivot.
- **The known-issues briefing is the differentiator.** It turns "cheap car" into "cheap car —
  ask about X, verify Y, and here is ~Z kr of negotiation room". Example: Audi A4 2008–2012
  2.0 TFSI burns oil → check whether the piston-ring fix was done → ~15 000 kr leverage.
- **Radical honesty in the output.** Estimates (valuation, insurance, specs) are labelled as
  estimates. Sample data is never presented as real listings. Known issues are prompts to
  verify, not diagnoses.
- **CV/portfolio project.** Kais is a mechanical-engineering student (LiU). Clear
  architecture, honest data-quality reasoning and demonstrable end-to-end function matter
  more than feature count. Aesthetics count: *"fina grafer, esthetically pleasing"*.

---

## 3. Decided — don't reopen

| Decision | Choice (made by Kais) | Why |
|---|---|---|
| Market value | **Hybrid:** car.info lookup by regnr (stub, off) → **comparables** fallback | car.info has no public valuation API and needs a regnr, which Blocket ads don't expose |
| Build order | **Sample data first**; the real scraper is pluggable | Demonstrable offline; not blocked by anti-bot measures |
| Scraper tech | **requests + BeautifulSoup**, parsing Blocket's `__NEXT_DATA__` JSON | Blocket is Next.js; embedded JSON is far more stable than CSS selectors |
| Real data | **Bright Data Web Unlocker** (Kais's own paid account), `country="se"` | Blocket blocks plain scrapers; the agent's environment could not reach blocket.se at all |
| Insurance | **Calibrated heuristic** plus personal factors (age, bonus, city) | There is no public Swedish premium API; quotes require a personnummer |
| Location | **Never inside a OneDrive-synced folder** | The first build vanished from a OneDrive folder between turns and had to be rebuilt |
| Git | Yes (3 commits + handoff) | CV/GitHub |
| Front-end | **Delegated to Claude** — *"spelar ingen roll… högsta nivå"* | Decide once real data flows (§9.7); do not re-ask |

---

## 4. Current state

### Works (re-verified 2026-09-26 on the Mac)

- `pipeline.run --source sample` loads 200 listings, 10 specs and 14 known issues into all
  6 tables.
- The advisor filters behave correctly. An AWD-only profile returns only Volvo XC60 (the sole
  AWD model in the specs). A Golf 2019 correctly shows *no known issues*, because the Golf
  faults are registered for 2008–2016, so year-range filtering works.
- Insurance calibration, against published Swedish figures (average helförsäkring
  ≈ 584 kr/mo per Hedvig; Stockholm ≈ +40 %; drivers under 25 ≈ 2×; bonus up to −55 %):
  typical 150 k/150 hp car = **560 kr/mo** · Stockholm, 23 years old, 0 bonus years =
  **1 680** · rural, 45 years old, 10 bonus years = **330** · Tesla 380 k/283 hp = **1 080**.
- `--source blocket-bd` without a key fails gracefully with a clear message, no crash.
- The UTF-8 stdout fix in `recommend.py` survives a cp1252 pipe. Without it, the script
  crashed on `≤` (tested by simulating with `PYTHONIOENCODING=cp1252`).

### Built but never run against the real site

- `scrapers/blocket_brightdata.py` (Web Unlocker fetch + `--probe`). There is no `.env`, so no
  key has ever been configured.
- `scrapers/blocket.py`. The plain requests path will almost certainly be blocked.
- `scrapers/carinfo.py` `_lookup_carinfo`. This is a stub that returns `None`.

### Not built

Front-end (Power BI `.pbix` / Streamlit) · tests · year-aware valuation · advisor reading from
the DB · PostgreSQL · `LAUNCH.md`.

### Outside the code

- `docs/REVIEW_BRIEF.md` is an external-review brief written for Kimi on 2026-07-18: 8 blunt
  review questions and all the weaknesses. **Kimi's answer never came back into the
  conversation.** If Kais pastes it later, evaluate it critically — don't implement blindly.

---

## 5. Architecture and file map

```
sample_data ─┐                                       ┌─▶ analysis/queries.sql ─▶ Power BI (not built)
Blocket (BD) ┴▶ run.py ─▶ CarInfoValuer ─▶ SQLite ───┤
                          (discount_pct)   star +    └─ (recommend.py does NOT read this yet — §8.2)
                                           reference
recommend.py ─▶ sample_data ─▶ CarInfoValuer ─▶ matcher.rank(BuyerProfile) ─▶ printed shortlist
                                                  ├─ reference/lookup (specs, known issues)
                                                  └─ insurance.estimate_monthly_premium
```

| Path | Role |
|---|---|
| `scrapers/blocket.py` | `Listing` dataclass (the shape every scraper returns) + `BlocketScraper`: `_page_url` → `_fetch_page` → `_extract_next_data` → `_iter_raw_ads` → `_normalize` (paths marked `TODO`) |
| `scrapers/blocket_brightdata.py` | `BlocketBrightDataScraper` overrides **only** `_fetch_page` → `POST https://api.brightdata.com/request` with a Bearer key, `{zone, url, format:"raw", country:"se"}`. `--probe URL` saves HTML + screenshot to `debug/` and prints `__NEXT_DATA__` keys |
| `scrapers/carinfo.py` | `CarInfoValuer`: cohort tiers (brand, model, year) → (brand, model) → (brand, year), first with ≥ 3 prices; median ± 1.0 kr/km mileage adjustment |
| `scrapers/sample_data.py` | 10 models × 2013–2022, seed 42, ~18 % deliberately underpriced 10–20 %. Mileage in **km**. Uses `date.today()` for car age |
| `reference/specs_data.py` | One spec row per (brand, model): body, drivetrain, hp, fuel, L/100km or kWh/100km, tax, reliability 1–5 (approximate) |
| `reference/known_issues_data.py` | 14 real, community-known faults with year ranges, severity, what to check, negotiation SEK |
| `reference/lookup.py` | `get_spec(brand, model)`, `get_issues(brand, model, year)` |
| `database/schema.sql` | Star schema + `car_specs` + `known_issues`. `fact.url` is UNIQUE, so re-runs upsert. `date_id` = YYYYMMDD. `value_method` = `carinfo`/`comparables` |
| `database/db.py` | Connection, dimension get-or-create, fact upsert, reference loaders |
| `pipeline/run.py` | ETL CLI: `--source sample \| blocket \| blocket-bd` |
| `pipeline/matcher.py` | `BuyerProfile` → hard filters → TCO → 0–100 score → briefing |
| `pipeline/insurance.py` | Premium estimator (formula below) |
| `pipeline/recommend.py` | Advisor CLI (Swedish output) |
| `analysis/queries.sql` | 8 queries for Power BI (top deals, brand/county, spec-enriched base table, issue briefing, negotiation room) |
| `.claude/skills/car-deal-digest/` | Project skill: how to run the pipeline and relay a shortlist |

**Key formulas (so you don't have to reverse-engineer them):**
- `discount_pct = (value − price) / value × 100`. Positive means listed below value.
- TCO/year = insurance × 12 + fuel (consumption × annual_km × price: petrol 18.5, diesel 19.5
  kr/l, electricity 2.8 kr/kWh) + tax + repair reserve `(6 − reliability) × 2000`.
- Match score = weighted mean of clamped components: deal 0.35 (−5 % → 0, +30 % → 1),
  reliability 0.25, economy 0.20 (0 kr fuel → 1, 20 k → 0), budget headroom 0.20.
- Insurance = (300 + 0.0014 × value + 1.5 × max(0, hp − 120) [+40 if ≥ 12 years old]) ×
  city (Stockholm 1.2, Gbg/Malmö 1.1) × age (< 25: 1.8, < 30: 1.3, ≥ 65: 1.1) ×
  bonus clamp(1.4 − 0.08 × years, 0.55, 1.4). Rounded to 10 kr.
- Red flags: discount > 35 % ("too good to be true"), mileage > 30 000 km per year of age.

**Patterns to keep:**
- Every scraper returns the `Listing` shape. A new data source = a subclass that overrides
  `_fetch_page` only.
- Reference data has a single source of truth in `reference/*.py`; the DB loaders read the
  same lists.
- Hard filters (exclude) are kept separate from the soft score (rank).
- Mileage is **km internally**. Blocket shows Swedish *mil* (1 mil = 10 km); convert in
  `_normalize`.

---

## 6. Setting up on the PC

### What Kais does (three steps)

1. Unzip `car-deal-finder-handoff.zip` to a folder **not synced by OneDrive**, e.g.
   `C:\dev\car-deal-finder`. Windows OneDrive often backs up Desktop and Documents by default,
   so avoid those.
2. If Python isn't installed, install **Python 3.11+** from python.org and tick
   *"Add python.exe to PATH"*. Git is already there, since Claude Code on Windows needs it.
3. Open the folder in Claude Code and write: **"Läs HANDOFF.md och sätt upp projektet."**

### What Claude Code does (Git Bash, which is what Claude Code uses on Windows)

```bash
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pipeline.run --source sample --limit 200
.venv/Scripts/python.exe -m pipeline.recommend --budget 220000 --min-year 2016 \
    --body Kombi,Halvkombi --max-insurance 800 --max-lphmil 6.0 --top 3
```

**Expected output** (captured 2026-09-26; must match exactly within calendar year 2026):

```
[1] Toyota Corolla 2021   — Match 67/100
    Pris 128 000 kr  (värde ~161 206 kr  rabatt +21%)  ·  78 838 km
    Halvkombi · FWD · Hybrid · 122 hk · pålitlighet 5/5
    Kostnad/år ~21 870 kr  (försäkring 580/mån  bränsle 12 210, skatt 700, reparationsreserv 2000)
      🟡 Hybridbatteriets hälsa på äldre exemplar
    💬 Förhandlingsutrymme att verifiera: ~8 000 kr
[2] Volkswagen Golf 2019   — Match 60/100   (Kostnad/år ~27 690 kr, ✅ inga kända typfel)
[3] Volkswagen Passat 2018 — Match 59/100   (Kostnad/år ~29 135 kr, 🟠 AdBlue/SCR och DPF)
```

The ETL should print `loaded 200 listings, 10 specs, 14 known issues`. A fresh DB has
`fact_listings` 200 · `dim_location` 9 · `dim_time` 1 · `car_specs` 10 · `known_issues` 14.
Also run `--drivetrain AWD --budget 300000` and expect only Volvo XC60 results.

> The numbers depend on `date.today()` (car age in `sample_data.py`). They hold for 2026 and
> shift in 2027. That is the generator, not a bug.

### Windows risks — honest caveats

- **Console encoding.** Fixed in `recommend.py`, but the fix is untested on real Windows. If
  another script crashes with `UnicodeEncodeError`, run `export PYTHONUTF8=1`.
- **venv paths.** Use `.venv/Scripts/`, not `.venv/bin/`. Activation is
  `source .venv/Scripts/activate` in Git Bash, or `.venv\Scripts\Activate.ps1` in PowerShell
  (which may need `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`).
- **`python` can open the Microsoft Store stub.** Use `py -3` instead.
- **lxml** ships Windows wheels. If the install still fails, `blocket.py` has a single
  `BeautifulSoup(html, "lxml")` call that can fall back to `"html.parser"`.
- **No dev server.** This is a CLI project. If a Streamlit front-end is added, register it in
  `.claude/launch.json` and start it with `preview_start`. Kais's rule is never to hand him
  manual terminal instructions. Streamlit ignores `$PORT`, so wire the port explicitly.
- **`.env` is not in the zip** because it never existed. Create it on the PC from
  `.env.example` when Kais has a Bright Data key. It is gitignored.
- **Mac-only context is now in the repo:** this file, `CLAUDE.md`, and the `car-deal-digest`
  skill under `.claude/skills/`.

---

## 7. History — how we got here

- **2026-06-17** — Kais sent brief 1. Claude flagged that Blocket and car.info resist scraping
  and that car.info valuation needs a regnr, then asked three questions. Kais chose hybrid
  valuation, sample data first, and requests + BS4. The first build included the schema, ETL
  and ranking SQL, and the pipeline ran. It exposed the cohort flaw: 40–62 % "discounts" on
  old cars.
- **Pivot** — Kais sent brief 2. Claude proposed TCO, a reliability score, a negotiation
  sheet, red flags and a match score, and all were accepted.
- **Data-loss incident** — the whole project folder vanished from
  `~/Downloads/OneDrive_2_6-17-2026/` between turns. Kais chose `~/Projects/car-deal-finder`
  and everything was rebuilt there, plus the new advisor layer (`reference/`, `insurance.py`,
  `matcher.py`, `recommend.py`). Verified.
- **2026-06-27** — Kais sent brief 3 ("högsta nivå, real data"). `git init`. Fetching blocket.se
  from Claude's environment was refused. A web search for Swedish premiums led to calibrating
  the insurance model (commit 2). Claude was honest that real insurer quotes can't be fetched.
- **2026-06-28** — Kais chose Bright Data. Built the Web Unlocker integration and probe
  (commit 3) following Bright Data's documented API.
- **Detour** — asked to detect dev servers. There are none in this project; the workspace's
  `launch.json` pointed at Reverse LinkedIn, which was fixed separately.
- **2026-07-18** — exported the project plus a review brief for Kimi. No feedback was received.
- **Aug 2026** — paused for the exam period.
- **2026-09-26** — this handoff: recommend UTF-8 fix, `HANDOFF.md`, `CLAUDE.md`, portable
  skill, `docs/REVIEW_BRIEF.md`.

---

## 8. Known weaknesses (ranked)

1. **Valuation inflates discounts on older cars.** With about 200 listings across 10 models ×
   10 years, the exact (brand, model, year) cohort rarely reaches 3 prices. The valuer then
   pools all years for the model, so a 2013 car is compared with newer, pricier ones. The
   Power BI queries mask this with `discount BETWEEN 5 AND 40`, which only treats the symptom.
   **Fix:** make the valuation year-aware. For example, fit log(price) ~ age + mileage per
   (brand, model), which is a small hedonic regression that is fine at n = 200–2 000, and keep
   a depreciation-bridge fallback for thin cohorts. Show before/after discount distributions.
2. **The advisor can't see real data.** `recommend.py` calls `sample_data.generate()` and
   never reads `car_deals.db`, so listings loaded via `--source blocket-bd` never reach it.
   **Fix:** add `--source db` that selects from `fact_listings ⋈ dim_car ⋈ dim_location` and
   maps `blocket_price → price`.
3. **The Blocket parser is unverified.** The search path and params (`/bilar/sok?q=&page=`),
   the ads-array location and the field names are all guesses behind `TODO` markers. The *mil*
   → km conversion is still to do.
4. **Reference data is approximate.** There is one spec per (brand, model) with no
   generations or engines; a "Golf" is always 125 hp petrol. There are only 14 issues, and the
   SEK amounts and tax values are rough.
5. **Insurance is a heuristic, not a quote.** It is transparent and overridable, but still an
   estimate.
6. **No tests.** The highest-value targets are the valuer cohort tiers, the matcher's hard
   filters and the insurance multipliers.
7. **Sample data is circular.** The valuer re-discovers the generator's depreciation curve, so
   the sample data can't validate the valuation method.
8. **Minor.** `dim_car` is almost 1:1 with the facts because colour and gearbox are in the
   natural key. `dim_time` accumulates one row per run date.

---

## 9. Suggested next steps (in order)

1. **Set up and verify on the PC** (§6). Show Kais the baseline match.
2. **Offer a private GitHub repo.** There is no remote, and this is the only copy.
3. **Real data.** Kais creates a Bright Data account and a Web Unlocker zone, then fills in
   `.env` → run
   `python -m scrapers.blocket_brightdata --probe "https://www.blocket.se/bilar/sok?q=volvo"`
   → finalize `_iter_raw_ads` and `_normalize` against the real JSON (including the *mil* → km
   conversion and the real search URL) → first `--source blocket-bd` run.
   **Never run the full pipeline before the probe confirms the paths.**
4. **Let the advisor read the DB** (§8.2).
5. **Year-aware valuation** (§8.1).
6. **pytest** for the valuer, matcher and insurance.
7. **Front-end — Claude decides.** Recommendation: a **Streamlit advisor** (profile form →
   shortlist cards with a TCO breakdown chart and the issue briefing), because the product is
   interactive by nature. Add **Power BI** for the market overview using the existing
   `analysis/queries.sql`. Make it look good.
8. **Grow the reference data** to match the real market: per-generation specs and more known
   issues for the models that dominate real listings.
9. When it's launchable, write `LAUNCH.md` with the `launch-runbook` skill. Move to PostgreSQL
   later; the schema is portable on purpose.

---

## 10. Working with Kais

- **Swedish chat**, casual and energetic ("kör på!"). English for code, comments and commits.
- **Narrate as you go:** *"säg till vad du gör så att jag hänger med"*. Give the one-line why,
  then do it.
- **"Full frihet" means decide.** Build the impressive version and give a walkthrough
  afterwards. Don't re-ask anything in §3.
- **Don't guess.** Base claims on the files. Say what is an estimate, a stub or unverified,
  in the text.
- **Aesthetics are requirements.**
- **Never:** rank by discount alone · present sample data as real listings · give
  multi-terminal manual instructions · hardcode ports · claim something runs without
  verifying it.
- **Proof of done:** it runs, the output is checked, it's committed with an English message,
  and the README or roadmap is updated in the same pass.
