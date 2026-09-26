# Sessionslogg 2026-09-26: Car Deal Finder (molnsession med Claude)

> Skriven för att vi ska kunna gå igenom allt tillsammans. Den innehåller steg, ändringar,
> testkörningar, buggar, beslut, idéer och förslag. Alla siffror kommer från körningar i den
> här sessionen, och **det som inte är verifierat står uttryckligen**.
> PR: <https://github.com/kaisalhasan01/car_deal_finder/pull/1> · Branch: `claude/happy-noether-s2d3j0`

---

## TL;DR

1. **Blocket har bytt plattform (nov–dec 2025)** till samma system som FINN.no. Den gamla
   scrapern (`/bilar/sok` + `__NEXT_DATA__`) hade därför *aldrig* kunnat fungera. Bilsöket är
   nu ett **öppet JSON-API utan nyckel**, så Bright Data behövs troligen inte. Klienten är
   omskriven för det nya API:t.
2. **Värderingen är omgjord** till en hierarkisk hedonisk regression. Mot den gamla
   kohort-medianen, på syntetisk data med känt facit, sjönk felet (MAPE) från **12,1 % till
   4,2 %**, och i det "orättvisa" scenariot från 7,6 % till 5,5 %. Fynd-F1 steg från 0,49 till
   **0,78**. Åldersbiasen (−27 % på 2013:or) är borta. Ditt Audi-exempel ingår som test.
3. **Rådgivaren läser nu databasen.** Den har prishistorik, upptäcker sålda bilar, visar
   säljarens rättigheter (köplagen/konsumentköplagen) och länkar till car.info via regnummer.
4. **Nytt:** ett **REST-API (FastAPI)**, en **Streamlit-app ("Bilrådgivaren")**, en
   **SQL-katalog + övningar** och ett **Power BI-kit** (export, relationer, 20+ DAX-mått, tema).
5. **72 automatiska tester** (fanns 0) och 11 commits, inklusive den här dokumentationen. Allt är pushat.
6. ⛔ **Riktig Blocket-data är inte verifierad härifrån**, eftersom molnmiljöns nätverk
   blockerar blocket.se. Första steget hemma är
   `python -m scrapers.blocket --probe --query "volvo v60"` (se §9).

---

## 1. Vad jag hittade i repot

- Repot innehöll bara `car-deal-finder-handoff.zip`. Jag packade upp den och **slog ihop zip:ens
  egen git-historik** (dina 4 ursprungliga commits) med GitHub-repot, så att historiken syns på
  GitHub. Sedan tog jag bort zip:en.
- Jag läste allt: `HANDOFF.md`, `CLAUDE.md`, `REVIEW_BRIEF.md`, skillen och all kod.
- **Baslinjen verifierades exakt** enligt HANDOFF §6 innan jag ändrade något: Corolla 67/100,
  Golf 60/100, Passat 59/100, samma kostnader och tabellantal 200/9/1/10/14, och AWD-profilen
  gav bara XC60. ✅
- **Värderingsproblemet (§8.1) bekräftades med data.** Snittrabatt per årsmodell med gamla
  metoden:

  | Årsmodell | 2013 | 2014 | 2015 | 2016 | … | 2022 |
  |---|---|---|---|---|---|---|
  | Snittrabatt | **−27,3 %** (min −100,8 %) | −16,1 % | +1,3 % | −7,4 % | … | −12,4 % |

  Orsak: kohorten föll tillbaka till *alla* årsmodeller, och den platta justeringen på 1 kr/km
  drog ner värdet med ~100 000 kr på gamla bilar. Felet slog alltså åt båda hållen.

## 2. Den viktigaste upptäckten: Blocket har ett nytt, öppet API

Blocket.se gick inte att nå från molnsessionen (403 från nätverkspolicyn). PyPI fungerade dock,
så jag laddade ner det öppna paketet **`blocket-api`** (version 0.5.2 från juli 2026, flera
äldre versioner) och läste källkoden. Jag kompletterade med webbsökningar.

| Fakta | Källa |
|---|---|
| Endpoint: `GET https://www.blocket.se/mobility/search/api/search/SEARCH_ID_CAR_USED` | blocket-api 0.5.2 (källkod), browse.sh |
| Ingen token, en vanlig GET fungerar | browse.sh |
| Plattformsbytet skedde mellan blocket-api 0.3.7 (16 nov 2025, gamla `api.blocket.se` med token) och 0.3.9x (dec 2025) | versionsjämförelse |
| Svar: `docs[]`, `filters[]`, `metadata{result_size, paging, selected_filters}` | browse.sh, Apify |
| Fält: `ad_id`, `heading`, `price.amount`, `year`, `mileage`, `make`, `model`, `model_specification`, **`regno`**, `dealer_segment` ("Privat"/"Företag"), `organisation_name`, `timestamp` (ms), `location`, `coordinates`, `canonical_url` | flera oberoende |
| **Miltal är i mil** (`SCANDINAVIAN_MILE`) | Apify, browse.sh |
| **Okända parametrar ignoreras tyst**, så man validerar `selected_filters` | browse.sh |
| Make-koderna (Volvo `0.818` …) är FINN:s taxonomi | blocket-api-konstanter |

Fullständig dokumentation med länkar finns i [`docs/BLOCKET_API.md`](BLOCKET_API.md).

**Konsekvenser:**
- HANDOFF-beslutet "requests + `__NEXT_DATA__`" byggde på en sajt som inte finns längre.
  *Andemeningen*, att läsa strukturerad JSON med vanliga requests, gäller fortfarande och är
  nu ännu enklare.
- Bright Data är nu en valfri reserv (`--transport brightdata`) och inget krav.
- Annonserna innehåller **regnummer**. Det öppnar för historikkontroll (car.info) och extern
  värdering per bil (§10).

**Nätverket:** Vill du att jag verifierar mot riktig data i en framtida molnsession måste
`blocket.se`, `www.blocket.se` (och ev. `api.brightdata.com`) läggas till bland tillåtna domäner.
Det gör du i miljöns inställningar: molnmiljö-menyn i sessionens titelrad → *Edit* →
*Network access*. Hemma på din PC behövs inget sådant.

## 3. Steg för steg (i ordning)

| # | Vad | Varför | Commit |
|---|---|---|---|
| 1 | Importerade projektet med git-historik, tog bort zip:en, venv + beroenden, verifierade baslinjen | Utgå från känt läge | `ee703a0`, `f89be28` |
| 2 | Research om Blockets API (PyPI-källkod + webbsökning) | blocket.se blockerat härifrån | – |
| 3 | Ny Blocket-klient + kommun→län-tabell + fixturer + 17 tester | Riktig data var första målet | `d230921` |
| 4 | Hierarkisk hedonisk värdering + utvärderingsskript | Svaghet §8.1 | `0922092` |
| 5 | Ditt Audi-exempel avslöjade extrapoleringsbuggar. Skydd, bivillkor (handlare, växellåda, AWD, bränsle), realistisk miltalseffekt i generatorn | Din fråga om "värderingsmetric" | `1a9c10d` |
| 6 | Schema v2 (prishistorik, säljardimension, kalender, vyer), rådgivaren läser DB | Svaghet §8.2, Power BI-grund | `bc5bf42` |
| 7 | FastAPI + Streamlit-app + gemensamt tjänstelager | "API", och produkten är interaktiv | `292262b` |
| 8 | Referensdata 10 → 76 modeller, 14 → 47 kända fel, generella köpkontroller | Riktig data har hundratals modeller | `e4ba427` |
| 9 | SQL-katalog, SQL-körare, övningar, Power BI-kit, export, bränslefiltrerade typfel | SQL + Power BI till CV:t | `b6e273e` |
| 10 | Kodgranskning: läcka av facitfält i API:t, snyggare fel för okänt märke | Egen granskning | `4ffd5af` |
| 11 | Dokumentation (README, CLAUDE.md, HANDOFF-tillägg, skill, den här loggen) | Du bad om det | sista commit |

## 4. Alla ändringar per område

### 4.1 Blocket-klienten (`scrapers/`)
- `blocket.py` är omskriven.
  - **`SearchFilters`** översätter fritext, märken (→ koder), län (→ koder), pris, årsmodell och
    miltal (km → mil) till parametrar. `sales_form=1` ger bara begagnat (leasing har
    månadspris som skulle förstöra värderingen).
  - **Paginering** via `metadata.paging` / `is_end_of_paging`.
  - **Omförsök** med exponentiell backoff vid 429/5xx, och `Retry-After` respekteras.
  - **`normalize_ad()`** mappar en annons till `Listing` och ger ett *skäl* när en annons
    hoppas över (`no_price`, `monthly_price`, `placeholder_price`, `no_year` …).
  - **mil → km**, med en rimlighetskontroll per sida (median mil/år). Går att tvinga med
    `--mileage-unit`.
  - Tolkar **AWD** ("xDrive", "quattro", "4MOTION", "Dual Motor", Volvo "T8" …) och **hk** ur
    modellbeskrivningen.
  - **Säljartyp** (privat/handlare), **regnr** (valideras mot svenskt format) och
    **publiceringsdatum** (ms-timestamp).
  - **Klientsidig filtrering** som skyddsnät, eftersom Blocket ignorerar okända parametrar tyst.
  - **Råa snapshots** i `data/raw/blocket/<datum>/` och **replay** (`--source replay`) utan
    nätverk.
  - **`--probe`** skriver ut fälttäckning, `selected_filters`, första annonsen, de tolkade
    annonserna, beslutet om miltalsenhet och en **PASS/CHECK**-dom.
  - En reservväg om Blocket byter format igen: `__NEXT_DATA__`/inbäddad JSON och en generisk
    JSON-genomsökning.
- `blocket_codes.py` (ny): make-koder (licens WTFPL från blocket-api) och normaliserare för
  märke, bränsle, växellåda, drivning, regnr och säljare.
- `blocket_brightdata.py`: överskrider fortfarande bara `_fetch_page` (din konvention), men är
  nu valfri.
- `reference/geo_data.py` (ny): **alla 290 kommuner → 21 län** (testat), vanliga orter
  (Åkersberga → Österåker …) och Blockets länskoder.
- `sample_data.py`: dolda facitfält (`_fair_value`, `_injected_deal`) för utvärdering. Säljartyp
  och annons-id kommer från en *separat* slumpström, så att de 200 bilarna är identiska.
  Miltalseffekten är nu **procentuell (~3 %/1 000 mil)** i stället för 0,8 kr/km, som kunde ge
  negativa värden. Model 3 och Corolla börjar 2019 (en "Tesla Model 3 2016" fanns i datan).

### 4.2 Värderingen (`pipeline/valuation.py`, ny)
- **Modell:** log(pris) = nivå + ålder + ålder² + (miltal jämfört med det normala för åldern)
  + ålder×miltal + bivillkor (handlare, automat, AWD, bränsle).
- **Partial pooling:** global → märke → modell → årsmodell. En modell med lite data lånar
  lutning från märket. Styrkan anges i "pseudo-annonser", t.ex. att en modell behöver ~20
  annonser innan dess egen värdeminskning väger tyngre än märkets.
- **Leave-one-out:** en annons får aldrig vara med och värdera sig själv. Förut kunde en billig
  bil dra ner sitt eget "marknadsvärde".
- **Robust:** uteliggare (>3σ) och skadeord ("motorfel", "reparationsobjekt", "defekt" …)
  exkluderas från inlärningen men värderas ändå.
- **Osäkerhet:** 80 %-intervall, säkerhetsnivå (hög/medel/låg) och `deal_z` (hur ovanligt lågt
  priset är *för just den modellen*).
- **Skydd** (efter din fråga): värdet stiger aldrig med ålder, en äldre bil med *samma
  mätarställning* är aldrig värd mer, fler mil kostar alltid, och värden utanför datat märks
  "extrapolerat" med låg säkerhet.
- `analysis/evaluate_valuation.py` (ny) och [`docs/VALUATION_EVAL.md`](VALUATION_EVAL.md).
- `scrapers/carinfo.py` finns kvar som *baslinje* i utvärderingen.

### 4.3 Databasen: schema v2 (`database/`)
- Stjärnschema: `dim_car` (färg borttagen ur nyckeln, den var nästan 1:1 med fakta),
  `dim_location` (kommun + län), **ny `dim_seller`**, **`dim_date`** som en kontinuerlig kalender
  med svenska månads- och veckodagsnamn.
- `fact_listings` håller en rad per annons: första sedd, första pris, senast sedd, aktiv/inaktiv,
  värdering, intervall, `deal_z`, skadeflagga och liggtid.
- **`fact_price_snapshots`** har pris per annons och dag, alltså prishistorik.
- **Såld-detektion:** annonser som försvinner ur en *fullständigt* genomsökt sökning markeras
  inaktiva.
- `valuation_models` lagrar värdeminskning per modell och körning. `etl_runs` är en körlogg
  (data lineage).
- **Vyer** (semantiskt lager): `vw_listings`, `vw_listing_issues` (bränslefiltrerad),
  `vw_price_history`, `vw_price_changes` (LAG), `vw_model_market` och `vw_deal_board`
  (ROW_NUMBER).
- **Skydd:** schemaversion (`PRAGMA user_version`), och exempeldata och riktig data **blandas
  aldrig** (separata filer; ETL:en vägrar blanda).

### 4.4 Rådgivaren (`pipeline/matcher.py`, `recommend.py`)
- Läser **databasen** automatiskt. Utan riktig data visas en tydlig **DEMO**-banner.
- Det annonsen säger (bränsle, AWD, hk) går före referensspecen. När ingen variant matchar
  används typvärden, märkta "(typvärde)".
- Nya filter: **säljartyp** och **skadeannonser** (dolda som standard).
- **Fyndpoäng** från `deal_z` × värderingens säkerhet. Aldrig bara rabatten, så din regel
  gäller fortfarande.
- **Briefing:** kända fel (nu filtrerade på bränsle, så en diesel får inte bensinmotorns fel),
  röda flaggor, **prissänkningar**, **liggtid**, **köplagen mot konsumentköplagen**,
  **historiklänkar** (car.info, biluppgifter.se) via regnr och **generella köpkontroller** (rost,
  kamrem, DPF, batterihälsa, mätarställning mot besiktning).
- `--json` ger maskinläsbar output. Kraschen vid annonser utan miltal är borta.

### 4.5 REST-API (`api/main.py`, nytt)
`/health`, `POST /recommend`, `POST /valuate` (värdera *vilken bil som helst*), `/listings`
(filtrering, sortering, sidindelning), `/listings/{id}` (+ typfel + prishistorik),
`/market/models`, `/market/deals`, `/market/depreciation`, `/reference/*`. Automatisk
dokumentation finns på `/docs`, och varje svar innehåller `demo: true/false`.

### 4.6 Appen "Bilrådgivaren" (`app/`, ny)
Streamlit med svensk text. Sidopanelen har din profil (miltal i **mil**) och fyra flikar:
**Toppmatchningar** (nyckeltal, hantelgraf pris↔värde med intervallband, staplad årskostnad,
kort per bil, tabellvy), **Marknaden** (värdeminskningskurva med annonser, översikt, trovärdiga
fynd), **Värdera en bil** och **Om datan** (metod och körlogg). Diagrammen använder en
**färgblindhetsvaliderad palett** för ljust och mörkt läge (kontrollerad med valideringsskript
mot Streamlits bakgrunder), svensk talformatering och **streckad kurva där modellen
extrapolerar**.

### 4.7 Referensdata (`reference/`)
- **126 specrader / 76 modeller** (var 10). De har bränslevarianter, så en V60 laddhybrid får
  laddhybridens förbrukning och AWD. Värdena är ungefärliga och märkta som sådana.
- **47 kända fel** (var 14), bara väldokumenterade: 1.2 PureTech-remmen, 1.0 EcoBoost-kylningen,
  PowerShift, BMW N20/N47, Leaf-batteriet, Outlander PHEV, Renault 1.2 TCe, OM651, DQ200,
  EA189, Kona Electric-återkallelsen, Model S MCU m.fl.

### 4.8 SQL (`analysis/`)
- `queries.sql`: en **katalog med 17 frågor i 6 nivåer**, från JOIN till fönsterfunktioner
  (ROW_NUMBER, PERCENT_RANK, NTILE, LAG, löpande summa, glidande medel, median utan MEDIAN) och
  datakvalitetskontroller.
- `sql_runner.py` kör frågorna och skriver ut tabeller, så att du slipper ett databasprogram.
- `SQL_GUIDE.md` har **12 övningar** på din egen data, med lösningar (lösningarna testas
  automatiskt).

### 4.9 Power BI (`powerbi/`, nytt)
Exporten (`pipeline/export.py`, CSV eller Parquet), en guide steg för steg (inklusive
**svensk decimal-fälla**, relationer med rollspelande datumtabell och ett ER-diagram), **20+
DAX-mått** (USERELATIONSHIP, RANKX, DATESINPERIOD, DATEADD …), ett **tema** med samma palett,
fem sidförslag och CV-formuleringar. `sample_data/` innehåller en färdig export av demodata så
att du kan öva direkt (märkt `source=sample`).

### 4.10 Övrigt
`.claude/launch.json` (app 8501, API 8000), `.streamlit/config.toml`, `requirements.txt` /
`requirements-dev.txt`, `pytest.ini`, `.gitignore` (råsnapshots, Power BI-exporter), README,
CLAUDE.md, ett tillägg överst i HANDOFF.md och en uppdaterad `car-deal-digest`-skill.

## 5. Testkörningar och resultat

| Vad | Kommando | Resultat |
|---|---|---|
| Baslinje före ändringar | `pipeline.run --source sample` + `recommend …` | ✅ exakt enligt HANDOFF §6 |
| Blocket-klient mot fixturer | provkörning + `pytest tests/test_blocket.py` | 2 sidor, 8/11 tolkade, 3 hoppade med rätt skäl; 17 ✅ |
| Live-prob mot Blocket | `scrapers.blocket --probe` | ⛔ 403 (sandlådans nätverk), felhanteringen fungerar |
| Värdering, utvärdering | `analysis.evaluate_valuation --write` | se tabellen nedan |
| Ditt Audi-exempel | `HedonicValuer.value(...)` | före skydden: **2011 > 2013 (bugg)**; efter: monotont |
| Hela testsviten | `pytest` | **72 passed** (~2 s, helt offline) |
| API på riktigt | `uvicorn` + curl | `/health`, `/valuate` OK och `/docs` 200 |
| Appen på riktigt | Streamlit + Playwright-skärmdumpar | 4 flikar, **0 fel** (efter 3 rättade renderingsfel) |
| ETL två gånger i rad | `pipeline.run --source sample` ×2 | idempotent: 200 annonser, 0 nya andra gången |
| Alla SQL-frågor | `analysis.sql_runner` | 17/17 körs |

**Utvärdering av värderingen** (syntetisk data med känt facit, medel över 5 frön):

| Scenario | MAPE gammal → ny | Fynd-F1 gammal → ny | Falska fynd gammal → ny |
|---|---|---|---|
| Realistisk generator, 200 annonser | 12,1 % → **4,2 %** | 0,49 → **0,78** | 17,8 → **2,6** |
| Realistisk generator, 1000 annonser | 10,5 % → **2,6 %** | 0,56 → **0,86** | 96,4 → **0,2** |
| Ursprunglig generator (0,8 kr/km), 200 | 7,6 % → **5,5 %** | 0,58 → **0,71** | 4,4 → 5,8 |
| Ursprunglig generator, 1000 | 4,6 % → **3,9 %** | 0,73 → **0,78** | 6,8 → 14,0 ⚠️ |

Tolka det ärligt: den realistiska generatorn har samma matematiska form som modellen, vilket
smickrar resultatet. Det *robusta* resultatet är att den nya modellen vinner på fel och F1 i
alla scenarier och att den gamla har en inbyggd åldersbias. Priset är fler falska fynd i det
sista scenariot. Verklig träffsäkerhet kan bara mätas på riktig data (§10).

**Ny referensoutput** (ersätter HANDOFF §6), samma profil:
```
[1] Toyota Corolla 2021 — Match 74/100
    Pris 129 000 kr · värde ~164 348 kr (80 %: 139 184–194 063) · rabatt +22 % · säkerhet hög
[2] Toyota Corolla 2019 — Match 70/100
[3] Kia Ceed 2021       — Match 70/100
```

## 6. Buggar jag hittade och rättade

1. **Den gamla parsern kunde aldrig fungera** (plattformsbytet). Den är omskriven.
2. `regDate "2019-05-01"` blev årsmodell **20190501** (siffrorna slogs ihop).
3. `.title()` gjorde "BMW" till "Bmw".
4. `recommend.py` kraschade om miltal saknades (`format(None, ',')`).
5. Formateringsfel: "580/mån  bränsle", eftersom kommatecknet åts upp av `.replace(",", " ")`.
6. **Förhandlingsutrymmet i SQL-fråga #8 multiplicerades med antalet annonser** (BMW 3-serie
   2014: 225 000 kr och "10 fel" i stället för 45 000 kr och 2).
7. Värderingen: extrapolering gav **2011 > 2013** (hittat via ditt exempel), extrapolerad
   ålderslutning berodde på miltalet, och ett attribut skuggade en metod.
8. Upsert skrev över "först sedd"-datum. Fixat med `first_seen` och `first_price`.
9. `dim_date` fylldes *efter* faktaraderna (FOREIGN KEY-fel), och är nu en kontinuerlig kalender.
10. API:t läckte generatorns facitfält i demoläget. Testet bevisar att det fallerar utan fixen.
11. Streamlits standardtema tryckte ihop diagrammen. Löst med `theme=None`.

## 7. Beslut jag tog, och varför

- **Från `__NEXT_DATA__` till JSON-API:t**: Blocket bytte själv. Andemeningen i ditt beslut
  (strukturerad JSON och requests) gäller fortfarande.
- **Bright Data blev valfritt**: API:t kräver ingen avblockering, vilket sparar pengar. Det
  finns kvar som reserv.
- **Egen värdering (comparables) behålls som kärna**, eftersom car.info saknar öppet API och
  blockerar skrapning. Hybridbeslutet (regnr → extern källa) gäller fortfarande och blir
  *möjligt* nu när regnr finns i annonserna (§10).
- **Streamlit + FastAPI** (du delegerade frontend-valet): Streamlit för produkten och FastAPI
  för "API" och CV-bredd. Power BI blir *din* marknadsrapport, med guiden i stället för en
  färdig .pbix. Den kan inte skapas här, och att bygga den själv är lärandet.
- **Exempeldatans generator ändrades** (procentuell miltalseffekt, realistiska startår). Den
  gamla varianten finns kvar som `mileage_effect="additive"` och redovisas i utvärderingen.
- **Separata databasfiler** för exempel och riktig data, som ett tekniskt skydd för din regel
  att aldrig visa exempeldata som riktiga annonser.
- **Dokumentation på engelska i repot** (CV), med den här loggen på svenska till dig.

## 8. Vad som INTE är verifierat (ärligt)

- ⛔ **Riktig Blocket-data**: fältnamnen kommer från dokumentation, och fixturerna är
  *konstruerade* (och märkta så). Den första riktiga körningen är proben.
- ⚠️ Parameternamnet för miltalsfiltret: blocket-api använder `milage_*` men browse.sh
  dokumenterar `mileage_*`. Jag skickar `mileage_*` och filtrerar dessutom på klientsidan. Proben
  visar i `selected_filters` vilket som gäller.
- ⚠️ Vad `location` innehåller (kommun, ort eller stadsdel?). Proben visar hur många som fick
  län.
- ⚠️ `.claude/launch.json` (formatet kunde inte testas här), `powerbi/theme.json` och
  DAX-måtten (inte öppnade i Power BI Desktop).
- ⚠️ Specar, skatt, försäkring och förhandlingsbelopp är ungefärliga uppskattningar.
- ⚠️ Länkformaten till car.info och biluppgifter.se är inte klickade härifrån, eftersom
  nätverket är blockerat.

## 9. Så kör du allt på din PC (checklista)

```bash
git fetch origin && git checkout claude/happy-noether-s2d3j0
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest                                    # 72 ska passera

# 1) Verifiera Blocket (viktigast!)
.venv/Scripts/python.exe -m scrapers.blocket --probe --query "volvo v60"
#    -> PASS: fortsätt · CHECK: skicka mig outputen + filen i debug/

# 2) Första riktiga körningen
.venv/Scripts/python.exe -m pipeline.run --source blocket --query "volvo v60" --pages 5
.venv/Scripts/python.exe -m pipeline.recommend --budget 200000 --body Kombi

# 3) Appen och API:t: starta via Claude Code (launch.json) eller
.venv/Scripts/python.exe -m streamlit run app/streamlit_app.py --server.port 8501

# 4) Power BI
.venv/Scripts/python.exe -m pipeline.export --format parquet
#    -> följ powerbi/README.md (eller öva direkt med powerbi/sample_data/)
```

## 10. Idéer och förslag (prioriterade)

**Nästa steg (hög nytta, låg insats)**
1. **Kör proben** och låt mig anpassa parsern efter det riktiga svaret. Ersätt sedan
   fixturerna med en riktig inspelning, så blir testerna "kontraktstester".
2. **Schemalägg ETL:en dagligen** (Windows Schemaläggaren). Då får du prishistorik, "såld inom
   X dagar" och trender i Power BI. Det är mycket starkare på CV:t än en ögonblicksbild.
3. **Mät värderingen på riktig data**: håll ut 20 % av annonserna och mät felet. Jämför
   sedan begärt pris med vad bilarna *såldes* för, där `is_active=0` + sista pris är en proxy.
4. **Bygg Power BI-rapporten** med guiden (~1–2 kvällar). Publicera skärmdumpar i README:n.

**Produkt / nytta för köpare**
5. **Extern värdering via regnr som "second opinion"**: car.info har betal-API för företag, och
   Blockets egen "Värdera bil" använde tidigare `api.bytbil.com/blocket-basedata-api/...`
   (overifierat om den finns kvar). Bara för topplistan, och bara med tillåtelse.
6. **Bevakning/notiser**: spara en profil och få e-post/push när en ny bil med hög match dyker
   upp. ETL:en + `etl_runs` är redan grunden.
7. **Dubblettdetektion via regnr**: samma bil ompublicerad (ny annons) visar riktig liggtid
   och tidigare prissänkningar. Det är ett starkt förhandlingsargument.
8. **Förhandlingsassistent**: generera ett förslag på bud utifrån värdeintervall, typfel,
   liggtid och prissänkningar ("Budet 118 000 kr motiveras av …").
9. **Riktig fordonsskatt**: räkna skatten från CO₂ och bonus-malus-regler i stället för typvärden.
10. **Bränslepris-API**: dagsaktuella priser i stället för konstanter.
11. **Köpchecklista som PDF** per bil att ta med på visningen.

**Data & teknik**
12. **PostgreSQL + molndrift** (t.ex. Render/Fly för API:t och Streamlit Community Cloud för
    appen), vilket ger en länk på CV:t. Schemat är redan portabelt.
13. **GitHub Actions**: kör pytest på varje push, med en grön badge i README:n.
14. **Utöka referensdatan** efter vad riktig data visar. Frågan
    `SQL_GUIDE.md #6` listar modeller utan spec.
15. **Generationer i specarna** (t.ex. Golf 7 och Golf 8) med årsintervall.
16. **Fler bivillkor i värderingen**: hk, utrustning (från annonstexten), antal ägare (car.info).

**Lärande / CV**
17. Skriv 3–4 egna SQL-vyer och använd dem i Power BI.
18. En kort **"case study"** i README:n: problem → data → metod → resultat, med graferna.
19. Presentera utvärderingsresultatet ärligt (inklusive begränsningarna). Det imponerar mer
    än perfekta siffror.

## 11. Öppna frågor till dig

1. Vill du att jag öppnar nätverket (blocket.se) i molnmiljön så att jag kan verifiera och
   anpassa parsern själv, eller kör du proben hemma och skickar mig outputen?
2. Vilka sökningar ska den dagliga körningen bevaka: dina egna köpkriterier, eller en bredare
   marknad för Power BI (t.ex. 10 populära modeller i hela Sverige)?
3. Ska jag slå ihop PR:en till `main` när du har gått igenom den, eller vill du granska den på
   GitHub först?
4. Är du intresserad av extern värdering (car.info B2B) om det kostar pengar, eller håller vi
   oss till egna jämförelser?

## 12. Svar på dina frågor under sessionen

- **"inte block, blocket!"**: ja, Blocket.se. Allt här gäller Blocket.
- **"Kommer du kunna fortsätta om jag stänger ner datorn?"**: ja. Sessionen körs i molnet, och
  allt pushades löpande till GitHub.
- **"Vi jämför väl med värderingar från car.info?"**: inte automatiskt. car.info saknar öppet
  API och blockerar skrapning, så marknadsvärdet är *vår* uppskattning från jämförbara
  Blocket-annonser. Men varje bil får en direktlänk till car.info via regnummer, och en extern
  värdering kan kopplas in senare (§10.5).
- **"Två A4 2011 för 50k är inte lika mycket värda med 20 000 respektive 10 000 mil"**: exakt.
  Modellen justerar för miltal *i förhållande till åldern*. Ditt exempel avslöjade dessutom en
  extrapoleringsbugg (2011 värderades högre än 2013), som nu är rättad och permanent testad
  (`tests/test_valuation.py::test_value_is_monotone_in_age_and_mileage`).
