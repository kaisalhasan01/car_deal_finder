-- ===========================================================================
-- Views: the "semantic layer" that Power BI, the API and the advisor read.
-- Recreated on every init (DROP + CREATE) so they always match the schema.
-- Only portable SQL: works in SQLite >= 3.25 and PostgreSQL.
-- ===========================================================================

DROP VIEW IF EXISTS vw_listings;
DROP VIEW IF EXISTS vw_listing_issues;
DROP VIEW IF EXISTS vw_price_history;
DROP VIEW IF EXISTS vw_price_changes;
DROP VIEW IF EXISTS vw_model_market;
DROP VIEW IF EXISTS vw_deal_board;

-- One flat, enriched row per listing ---------------------------------------
CREATE VIEW vw_listings AS
SELECT
    f.listing_id, f.source, f.ad_id, f.url, f.is_active,
    c.brand, c.model, c.model_year, c.fuel_type, c.gearbox,
    l.city, l.county,
    s.seller_type, s.dealer_name,
    dp.date  AS published_date,
    dfs.date AS first_seen_date,
    dls.date AS last_seen_date,
    f.title, f.model_spec, f.regnr, f.color, f.mileage_km,
    f.price_sek, f.first_price_sek,
    f.price_sek - f.first_price_sek AS price_change_sek,
    f.market_value_sek, f.value_low_sek, f.value_high_sek,
    f.discount_pct, f.deal_z, f.value_method, f.value_confidence, f.value_n,
    f.damage_flag, f.days_on_market,
    COALESCE(f.body_type, sp.body_type)   AS body_type,
    COALESCE(f.drivetrain, sp.drivetrain) AS drivetrain,
    COALESCE(f.power_hp, sp.power_hp)     AS power_hp,
    sp.fuel_l_per_100km, sp.energy_kwh_per_100km, sp.annual_tax_sek, sp.reliability,
    f.spec_id,
    f.lat, f.lon, f.image_url
FROM fact_listings f
JOIN dim_car c            ON c.car_id = f.car_id
JOIN dim_location l       ON l.location_id = f.location_id
JOIN dim_seller s         ON s.seller_id = f.seller_id
LEFT JOIN dim_date dp     ON dp.date_id = f.published_date_id
JOIN dim_date dfs         ON dfs.date_id = f.first_seen_date_id
JOIN dim_date dls         ON dls.date_id = f.last_seen_date_id
LEFT JOIN car_specs sp    ON sp.spec_id = f.spec_id;

-- Listing x known issue (the "check / haggle on" briefing as a table) -------
CREATE VIEW vw_listing_issues AS
SELECT
    f.listing_id, c.brand, c.model, c.model_year, f.price_sek,
    ki.severity, ki.category, ki.engine, ki.issue, ki.what_to_check,
    ki.negotiation_leverage_sek
FROM fact_listings f
JOIN dim_car c           ON c.car_id = f.car_id
LEFT JOIN car_specs sp   ON sp.spec_id = f.spec_id
JOIN known_issues ki     ON lower(ki.brand) = lower(COALESCE(sp.brand, c.brand))
                        AND lower(ki.model) = lower(COALESCE(sp.model, c.model))
                        AND (ki.year_from IS NULL OR c.model_year >= ki.year_from)
                        AND (ki.year_to   IS NULL OR c.model_year <= ki.year_to)
                        -- engine-specific faults only for cars with a matching fuel
                        AND (ki.applies_to_fuels IS NULL OR c.fuel_type = 'unknown'
                             OR (',' || ki.applies_to_fuels || ',') LIKE ('%,' || c.fuel_type || ',%'));

-- Daily price observations with labels --------------------------------------
CREATE VIEW vw_price_history AS
SELECT
    p.listing_id, d.date, p.date_id, p.price_sek,
    c.brand, c.model, c.model_year, f.url
FROM fact_price_snapshots p
JOIN dim_date d       ON d.date_id = p.date_id
JOIN fact_listings f  ON f.listing_id = p.listing_id
JOIN dim_car c        ON c.car_id = f.car_id;

-- Price changes per listing, using a window function (LAG) -------------------
CREATE VIEW vw_price_changes AS
WITH steps AS (
    SELECT
        p.listing_id, p.date_id, p.price_sek,
        LAG(p.price_sek) OVER (PARTITION BY p.listing_id ORDER BY p.date_id) AS prev_price
    FROM fact_price_snapshots p
)
SELECT
    listing_id,
    COUNT(*)                                               AS observations,
    SUM(CASE WHEN price_sek < prev_price THEN 1 ELSE 0 END) AS price_drops,
    SUM(CASE WHEN price_sek > prev_price THEN 1 ELSE 0 END) AS price_raises,
    MIN(price_sek)                                         AS lowest_price_sek,
    MAX(price_sek)                                         AS highest_price_sek,
    MAX(CASE WHEN price_sek <> prev_price THEN date_id END) AS last_change_date_id
FROM steps
GROUP BY listing_id;

-- Market overview per model (active listings) --------------------------------
CREATE VIEW vw_model_market AS
SELECT
    c.brand, c.model,
    COUNT(*)                                                   AS active_listings,
    ROUND(AVG(f.price_sek))                                    AS avg_price_sek,
    ROUND(AVG(f.mileage_km))                                   AS avg_mileage_km,
    ROUND(AVG(c.model_year), 1)                                AS avg_model_year,
    ROUND(AVG(f.discount_pct), 1)                              AS avg_discount_pct,
    ROUND(AVG(f.days_on_market), 1)                            AS avg_days_on_market,
    ROUND(100.0 * SUM(CASE WHEN s.seller_type = 'dealer' THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                               AS dealer_share_pct,
    SUM(CASE WHEN f.discount_pct >= 10 AND f.value_confidence <> 'low' THEN 1 ELSE 0 END)
                                                               AS credible_deals
FROM fact_listings f
JOIN dim_car c    ON c.car_id = f.car_id
JOIN dim_seller s ON s.seller_id = f.seller_id
WHERE f.is_active = 1
GROUP BY c.brand, c.model;

-- Credible deals: active, no damage wording, trustworthy valuation ----------
-- Ranked within each model with ROW_NUMBER (another window function).
CREATE VIEW vw_deal_board AS
SELECT *
FROM (
    SELECT
        v.*,
        ROW_NUMBER() OVER (PARTITION BY v.brand, v.model ORDER BY v.deal_z DESC) AS rank_in_model
    FROM vw_listings v
    WHERE v.is_active = 1
      AND v.damage_flag = 0
      AND v.value_confidence IN ('high', 'medium')
      AND v.discount_pct >= 5
) ranked;
