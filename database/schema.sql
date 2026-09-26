-- ===========================================================================
-- Swedish Car Deal Finder — star schema + buyer-advisor reference tables
-- ---------------------------------------------------------------------------
-- Fact table (fact_listings) = one row per Blocket listing, surrounded by three
-- deduplicated dimensions (car, location, time). Two extra REFERENCE tables
-- (car_specs, known_issues) power the personalized buyer-advisor layer.
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Dimension: car attributes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_car (
    car_id    INTEGER PRIMARY KEY,
    brand     TEXT    NOT NULL,
    model     TEXT    NOT NULL,
    year      INTEGER NOT NULL,
    fuel_type TEXT    NOT NULL DEFAULT 'unknown',
    gearbox   TEXT    NOT NULL DEFAULT 'unknown',
    color     TEXT    NOT NULL DEFAULT 'unknown',
    UNIQUE (brand, model, year, fuel_type, gearbox, color)
);

-- ---------------------------------------------------------------------------
-- Dimension: location
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_location (
    location_id INTEGER PRIMARY KEY,
    city        TEXT NOT NULL,
    county      TEXT NOT NULL DEFAULT 'unknown',
    UNIQUE (city, county)
);

-- ---------------------------------------------------------------------------
-- Dimension: time (date_id = YYYYMMDD surrogate)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_time (
    date_id INTEGER PRIMARY KEY,   -- 20260617
    date    TEXT    NOT NULL,      -- ISO 'YYYY-MM-DD'
    week    INTEGER NOT NULL,
    month   INTEGER NOT NULL,
    year    INTEGER NOT NULL,
    UNIQUE (date)
);

-- ---------------------------------------------------------------------------
-- Fact: one row per listing observation
-- discount_pct = (carinfo_value - blocket_price) / carinfo_value * 100
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_listings (
    listing_id     INTEGER PRIMARY KEY,
    car_id         INTEGER NOT NULL REFERENCES dim_car(car_id),
    location_id    INTEGER NOT NULL REFERENCES dim_location(location_id),
    date_id        INTEGER NOT NULL REFERENCES dim_time(date_id),
    blocket_price  INTEGER NOT NULL,
    carinfo_value  INTEGER,
    discount_pct   REAL,
    mileage        INTEGER,
    days_on_market INTEGER,
    url            TEXT UNIQUE,
    value_method   TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_car      ON fact_listings(car_id);
CREATE INDEX IF NOT EXISTS idx_fact_location ON fact_listings(location_id);
CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_listings(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_discount ON fact_listings(discount_pct);

-- ===========================================================================
-- Reference tables for the buyer-advisor layer (curated, not scraped)
-- ===========================================================================

-- One representative spec row per (brand, model).
CREATE TABLE IF NOT EXISTS car_specs (
    spec_id              INTEGER PRIMARY KEY,
    brand                TEXT NOT NULL,
    model                TEXT NOT NULL,
    body_type            TEXT,     -- Kombi | Halvkombi | Sedan | SUV | Sportbil ...
    drivetrain           TEXT,     -- FWD | RWD | AWD
    power_hp             INTEGER,
    primary_fuel         TEXT,     -- Bensin | Diesel | El | Hybrid
    fuel_l_per_100km     REAL,     -- NULL for pure EV
    energy_kwh_per_100km REAL,     -- NULL for non-EV
    annual_tax_sek       INTEGER,  -- fordonsskatt / year (approx)
    reliability          INTEGER,  -- 1 (poor) .. 5 (excellent)
    UNIQUE (brand, model)
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
    UNIQUE (brand, model, issue)
);

CREATE INDEX IF NOT EXISTS idx_specs_model  ON car_specs(brand, model);
CREATE INDEX IF NOT EXISTS idx_issues_model ON known_issues(brand, model);
