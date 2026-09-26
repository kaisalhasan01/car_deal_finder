-- ===========================================================================
-- Swedish Car Deal Finder — schema v2 (star schema + advisor reference tables)
-- ---------------------------------------------------------------------------
-- Grain: fact_listings has one row per Blocket ad (current state);
--        fact_price_snapshots has one row per ad per day it was observed.
-- Dimensions: car variant, location, seller, calendar date.
-- Reference: car_specs, known_issues (curated, loaded from reference/*.py).
-- Model output: valuation_models (depreciation per model, per run date).
-- Lineage: etl_runs (one row per pipeline run).
-- Portable SQL on purpose (SQLite today, PostgreSQL later).
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- Dimension: car variant ----------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_car (
    car_id     INTEGER PRIMARY KEY,
    brand      TEXT    NOT NULL,
    model      TEXT    NOT NULL,
    model_year INTEGER NOT NULL,
    fuel_type  TEXT    NOT NULL DEFAULT 'unknown',
    gearbox    TEXT    NOT NULL DEFAULT 'unknown',
    UNIQUE (brand, model, model_year, fuel_type, gearbox)
);

-- Dimension: location (municipality + county) -------------------------------
CREATE TABLE IF NOT EXISTS dim_location (
    location_id INTEGER PRIMARY KEY,
    city        TEXT NOT NULL,
    county      TEXT NOT NULL DEFAULT 'unknown',
    UNIQUE (city, county)
);

-- Dimension: seller ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_seller (
    seller_id   INTEGER PRIMARY KEY,
    seller_type TEXT NOT NULL DEFAULT 'unknown',     -- private | dealer | unknown
    dealer_name TEXT NOT NULL DEFAULT '',
    UNIQUE (seller_type, dealer_name)
);

-- Dimension: calendar (continuous, for Power BI time intelligence) ----------
CREATE TABLE IF NOT EXISTS dim_date (
    date_id      INTEGER PRIMARY KEY,                 -- 20260926
    date         TEXT    NOT NULL UNIQUE,             -- '2026-09-26'
    year         INTEGER NOT NULL,
    quarter      INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    month_name   TEXT    NOT NULL,                    -- Swedish: 'september'
    iso_week     INTEGER NOT NULL,
    weekday      INTEGER NOT NULL,                    -- 1 = Monday ... 7 = Sunday
    weekday_name TEXT    NOT NULL,                    -- Swedish: 'lördag'
    is_weekend   INTEGER NOT NULL
);

-- Fact: one row per ad (current state) --------------------------------------
-- discount_pct = (market_value_sek - price_sek) / market_value_sek * 100
CREATE TABLE IF NOT EXISTS fact_listings (
    listing_id         INTEGER PRIMARY KEY,
    source             TEXT    NOT NULL,              -- blocket | sample
    ad_id              TEXT,
    url                TEXT    NOT NULL UNIQUE,
    car_id             INTEGER NOT NULL REFERENCES dim_car(car_id),
    location_id        INTEGER NOT NULL REFERENCES dim_location(location_id),
    seller_id          INTEGER NOT NULL REFERENCES dim_seller(seller_id),
    spec_id            INTEGER REFERENCES car_specs(spec_id),   -- matched reference spec
    published_date_id  INTEGER REFERENCES dim_date(date_id),
    first_seen_date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
    last_seen_date_id  INTEGER NOT NULL REFERENCES dim_date(date_id),
    is_active          INTEGER NOT NULL DEFAULT 1,    -- 0 = gone from Blocket (sold/removed)
    title              TEXT,
    model_spec         TEXT,
    regnr              TEXT,
    color              TEXT,
    body_type          TEXT,
    drivetrain         TEXT,
    power_hp           INTEGER,
    mileage_km         INTEGER,
    price_sek          INTEGER NOT NULL,              -- latest asking price
    first_price_sek    INTEGER NOT NULL,              -- asking price when first seen
    market_value_sek   INTEGER,                       -- hedonic estimate (leave-one-out)
    value_low_sek      INTEGER,                       -- 80 % interval
    value_high_sek     INTEGER,
    discount_pct       REAL,
    deal_z             REAL,                          -- discount in units of the model's price spread
    value_method       TEXT,                          -- hedonic-model | hedonic-brand | hedonic-global
    value_confidence   TEXT,                          -- high | medium | low
    value_n            INTEGER,                       -- comparable listings behind the estimate
    damage_flag        INTEGER NOT NULL DEFAULT 0,    -- ad text suggests damage/defect
    days_on_market     INTEGER,
    lat                REAL,
    lon                REAL,
    image_url          TEXT,
    scope              TEXT                           -- search that found it (for deactivation)
);

CREATE INDEX IF NOT EXISTS idx_fact_car      ON fact_listings(car_id);
CREATE INDEX IF NOT EXISTS idx_fact_location ON fact_listings(location_id);
CREATE INDEX IF NOT EXISTS idx_fact_seller   ON fact_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_fact_active   ON fact_listings(is_active, source);
CREATE INDEX IF NOT EXISTS idx_fact_regnr    ON fact_listings(regnr);

-- Fact: price observed per ad per day (price history, price drops) ----------
CREATE TABLE IF NOT EXISTS fact_price_snapshots (
    listing_id INTEGER NOT NULL REFERENCES fact_listings(listing_id) ON DELETE CASCADE,
    date_id    INTEGER NOT NULL REFERENCES dim_date(date_id),
    price_sek  INTEGER NOT NULL,
    PRIMARY KEY (listing_id, date_id)
);

-- ===========================================================================
-- Reference tables for the buyer-advisor layer (curated, not scraped)
-- ===========================================================================

-- One row per (brand, model, fuel variant); is_default marks the fallback row.
CREATE TABLE IF NOT EXISTS car_specs (
    spec_id              INTEGER PRIMARY KEY,
    brand                TEXT NOT NULL,
    model                TEXT NOT NULL,
    body_type            TEXT,        -- Kombi | Halvkombi | Sedan | SUV | Sportbil ...
    drivetrain           TEXT,        -- FWD | RWD | AWD
    power_hp             INTEGER,
    primary_fuel         TEXT NOT NULL, -- Bensin | Diesel | El | Hybrid | Laddhybrid
    fuel_l_per_100km     REAL,        -- NULL for pure EV
    energy_kwh_per_100km REAL,        -- NULL for combustion-only
    annual_tax_sek       INTEGER,     -- fordonsskatt / year (approx)
    reliability          INTEGER,     -- 1 (poor) .. 5 (excellent)
    is_default           INTEGER NOT NULL DEFAULT 1,
    UNIQUE (brand, model, primary_fuel)
);

-- Known faults: one row per (brand, model, issue), scoped by a year range.
CREATE TABLE IF NOT EXISTS known_issues (
    issue_id                 INTEGER PRIMARY KEY,
    brand                    TEXT NOT NULL,
    model                    TEXT NOT NULL,
    year_from                INTEGER,
    year_to                  INTEGER,
    engine                   TEXT,
    category                 TEXT,     -- Motor | Växellåda | El | Kaross/Rost ...
    severity                 TEXT,     -- low | medium | high
    issue                    TEXT NOT NULL,
    what_to_check            TEXT,
    negotiation_leverage_sek INTEGER,  -- indicative repair cost / haggling room
    applies_to_fuels         TEXT,     -- e.g. 'Diesel' or 'Bensin,Hybrid'; NULL = any fuel
    UNIQUE (brand, model, issue)
);

CREATE INDEX IF NOT EXISTS idx_specs_model  ON car_specs(brand, model);
CREATE INDEX IF NOT EXISTS idx_issues_model ON known_issues(brand, model);

-- ===========================================================================
-- Model output + lineage
-- ===========================================================================

-- Depreciation per fitted group, one set per run date (trend over time).
CREATE TABLE IF NOT EXISTS valuation_models (
    fitted_date_id                INTEGER NOT NULL REFERENCES dim_date(date_id),
    level                         TEXT    NOT NULL,   -- global | brand | model
    brand                         TEXT    NOT NULL DEFAULT '',
    model                         TEXT    NOT NULL DEFAULT '',
    n_listings                    INTEGER,
    value_age3_sek                INTEGER,
    value_age8_sek                INTEGER,
    depreciation_pct_per_year     REAL,
    mileage_effect_pct_per_10k_km REAL,
    residual_sd_pct               REAL,
    PRIMARY KEY (fitted_date_id, level, brand, model)
);

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id          INTEGER PRIMARY KEY,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    source          TEXT    NOT NULL,
    scope           TEXT,
    pages_fetched   INTEGER,
    ads_seen        INTEGER,
    listings_loaded INTEGER,
    new_listings    INTEGER,
    price_changes   INTEGER,
    deactivated     INTEGER,
    reached_end     INTEGER,
    notes           TEXT
);
