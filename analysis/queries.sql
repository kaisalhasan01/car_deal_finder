-- ===========================================================================
-- Swedish Car Deal Finder — analysis query catalog (schema v2)
-- ---------------------------------------------------------------------------
-- Run them all with:   python -m analysis.sql_runner --db car_deals.db
-- or one by name:      python -m analysis.sql_runner --db car_deals.db --only top_deals
-- Every query starts with a "-- name:" line; the runner splits on it.
-- Positive discount_pct = listed below the estimated market value.
-- Standard SQL (window functions need SQLite >= 3.25). SQLite-only bits are marked
-- "sqlite:" (e.g. strftime -> EXTRACT(YEAR FROM CURRENT_DATE) on PostgreSQL).
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- Level 1 — SELECT, JOIN, WHERE, ORDER BY
-- ---------------------------------------------------------------------------

-- name: top_deals
-- The deal board: active, credible valuation, no damage wording, best z-score first.
-- deal_z = how unusual the price is for this model (in standard deviations).
SELECT c.brand, c.model, c.model_year, f.price_sek, f.market_value_sek,
       ROUND(f.discount_pct, 1) AS discount_pct, ROUND(f.deal_z, 2) AS deal_z,
       f.mileage_km / 10 AS mileage_mil, l.city, s.seller_type
FROM fact_listings f
JOIN dim_car c      ON c.car_id = f.car_id
JOIN dim_location l ON l.location_id = f.location_id
JOIN dim_seller s   ON s.seller_id = f.seller_id
WHERE f.is_active = 1
  AND f.damage_flag = 0
  AND f.value_confidence IN ('high', 'medium')
  AND f.discount_pct >= 5
ORDER BY f.deal_z DESC
LIMIT 15;


-- ---------------------------------------------------------------------------
-- Level 2 — GROUP BY, aggregates, HAVING, CASE
-- ---------------------------------------------------------------------------

-- name: market_by_brand
-- Supply and price level per brand; HAVING hides brands with too few ads to say much.
SELECT c.brand,
       COUNT(*)                                   AS listings,
       ROUND(AVG(f.price_sek))                    AS avg_price_sek,
       ROUND(AVG(f.discount_pct), 1)              AS avg_discount_pct,
       SUM(CASE WHEN f.discount_pct >= 10 THEN 1 ELSE 0 END) AS strong_deals
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
WHERE f.is_active = 1
GROUP BY c.brand
HAVING COUNT(*) >= 5
ORDER BY listings DESC;

-- name: private_vs_dealer
-- Do dealers ask more for comparable cars? (Compare discount, not raw price —
-- discount_pct is already adjusted for model, age and mileage.)
SELECT s.seller_type,
       COUNT(*)                        AS listings,
       ROUND(AVG(f.price_sek))         AS avg_price_sek,
       ROUND(AVG(f.discount_pct), 1)   AS avg_discount_pct,
       ROUND(AVG(f.days_on_market), 1) AS avg_days_on_market
FROM fact_listings f
JOIN dim_seller s ON s.seller_id = f.seller_id
WHERE f.is_active = 1
GROUP BY s.seller_type;

-- name: supply_by_county
-- Where are the cars? Feeds a Power BI map / filled map by county.
SELECT l.county,
       COUNT(*)                                              AS listings,
       SUM(CASE WHEN f.discount_pct >= 10 THEN 1 ELSE 0 END) AS strong_deals,
       ROUND(AVG(f.price_sek))                               AS avg_price_sek
FROM fact_listings f
JOIN dim_location l ON l.location_id = f.location_id
WHERE f.is_active = 1
GROUP BY l.county
ORDER BY listings DESC;


-- ---------------------------------------------------------------------------
-- Level 3 — CTEs (WITH) and subqueries
-- ---------------------------------------------------------------------------

-- name: age_buckets
-- Price and discount by age bucket. The CTE computes age once; the outer query groups.
WITH aged AS (
    SELECT f.price_sek, f.discount_pct,
           CAST(strftime('%Y', 'now') AS INTEGER) - c.model_year AS age   -- sqlite:
    FROM fact_listings f
    JOIN dim_car c ON c.car_id = f.car_id
    WHERE f.is_active = 1
)
SELECT CASE WHEN age <= 3 THEN '0-3 år'
            WHEN age <= 7 THEN '4-7 år'
            WHEN age <= 11 THEN '8-11 år'
            ELSE '12+ år' END            AS age_bucket,
       COUNT(*)                          AS listings,
       ROUND(AVG(price_sek))             AS avg_price_sek,
       ROUND(AVG(discount_pct), 1)       AS avg_discount_pct
FROM aged
GROUP BY age_bucket
ORDER BY MIN(age);

-- name: above_model_average
-- Subquery in WHERE: cars priced below their own model's average price.
SELECT c.brand, c.model, c.model_year, f.price_sek
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
WHERE f.is_active = 1
  AND f.price_sek < (SELECT AVG(f2.price_sek)
                     FROM fact_listings f2
                     JOIN dim_car c2 ON c2.car_id = f2.car_id
                     WHERE c2.brand = c.brand AND c2.model = c.model
                       AND c2.model_year = c.model_year AND f2.is_active = 1)
ORDER BY c.brand, c.model, c.model_year
LIMIT 20;


-- ---------------------------------------------------------------------------
-- Level 4 — Window functions (the most CV-worthy SQL skill)
-- ---------------------------------------------------------------------------

-- name: best_deal_per_model
-- ROW_NUMBER() OVER (PARTITION BY ...) picks the #1 deal inside each model.
WITH ranked AS (
    SELECT c.brand, c.model, c.model_year, f.price_sek, f.discount_pct, f.deal_z,
           ROW_NUMBER() OVER (PARTITION BY c.brand, c.model ORDER BY f.deal_z DESC) AS rn
    FROM fact_listings f
    JOIN dim_car c ON c.car_id = f.car_id
    WHERE f.is_active = 1 AND f.damage_flag = 0 AND f.deal_z IS NOT NULL
)
SELECT brand, model, model_year, price_sek, ROUND(discount_pct, 1) AS discount_pct,
       ROUND(deal_z, 2) AS deal_z
FROM ranked
WHERE rn = 1
ORDER BY deal_z DESC;

-- name: price_percentile_in_cohort
-- PERCENT_RANK: where does each car's price sit among same model + model year? 0 = cheapest.
SELECT c.brand, c.model, c.model_year, f.price_sek,
       ROUND(PERCENT_RANK() OVER (PARTITION BY c.brand, c.model, c.model_year
                                  ORDER BY f.price_sek), 2) AS price_percentile,
       COUNT(*) OVER (PARTITION BY c.brand, c.model, c.model_year) AS cohort_size
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
WHERE f.is_active = 1
ORDER BY cohort_size DESC, c.brand, c.model, c.model_year, f.price_sek
LIMIT 25;

-- name: median_price_per_model
-- A median without a MEDIAN() function: rank rows, keep the middle one(s), average them.
WITH ordered AS (
    SELECT c.brand, c.model, f.price_sek,
           ROW_NUMBER() OVER (PARTITION BY c.brand, c.model ORDER BY f.price_sek) AS rn,
           COUNT(*)     OVER (PARTITION BY c.brand, c.model)                      AS n
    FROM fact_listings f
    JOIN dim_car c ON c.car_id = f.car_id
    WHERE f.is_active = 1
)
SELECT brand, model, n AS listings, ROUND(AVG(price_sek)) AS median_price_sek
FROM ordered
WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY brand, model, n
ORDER BY listings DESC;

-- name: price_quartiles
-- NTILE(4) splits each model's listings into price quartiles (Q1 = cheapest 25 %).
SELECT brand, model, quartile, COUNT(*) AS listings,
       MIN(price_sek) AS from_sek, MAX(price_sek) AS to_sek
FROM (
    SELECT c.brand, c.model, f.price_sek,
           NTILE(4) OVER (PARTITION BY c.brand, c.model ORDER BY f.price_sek) AS quartile
    FROM fact_listings f
    JOIN dim_car c ON c.car_id = f.car_id
    WHERE f.is_active = 1
) q
GROUP BY brand, model, quartile
ORDER BY brand, model, quartile;

-- name: price_drops
-- LAG() compares each day's price with the previous observation of the same ad.
-- Needs repeated ETL runs (e.g. daily) to show anything on real data.
WITH steps AS (
    SELECT p.listing_id, d.date, p.price_sek,
           LAG(p.price_sek) OVER (PARTITION BY p.listing_id ORDER BY p.date_id) AS prev_price
    FROM fact_price_snapshots p
    JOIN dim_date d ON d.date_id = p.date_id
)
SELECT c.brand, c.model, c.model_year, s.date, s.prev_price, s.price_sek,
       s.price_sek - s.prev_price AS change_sek
FROM steps s
JOIN fact_listings f ON f.listing_id = s.listing_id
JOIN dim_car c       ON c.car_id = f.car_id
WHERE s.prev_price IS NOT NULL AND s.price_sek <> s.prev_price
ORDER BY change_sek
LIMIT 20;

-- name: new_listings_running_total
-- Daily new ads (by publish date) and a running total with SUM() OVER (ORDER BY ...).
WITH daily AS (
    SELECT d.date, COUNT(*) AS new_listings
    FROM fact_listings f
    JOIN dim_date d ON d.date_id = f.published_date_id
    GROUP BY d.date
)
SELECT date, new_listings,
       SUM(new_listings) OVER (ORDER BY date) AS running_total,
       ROUND(AVG(new_listings) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1)
           AS moving_avg_7d
FROM daily
ORDER BY date DESC
LIMIT 14;


-- ---------------------------------------------------------------------------
-- Level 5 — the buyer-advisor tables (reference data joins)
-- ---------------------------------------------------------------------------

-- name: reliable_economical_deals
-- Deals on reliable, economical cars — the advisor's logic expressed in SQL.
SELECT v.brand, v.model, v.model_year, v.price_sek, ROUND(v.discount_pct, 1) AS discount_pct,
       v.reliability, v.fuel_l_per_100km, v.drivetrain, v.body_type
FROM vw_listings v
WHERE v.is_active = 1
  AND v.discount_pct >= 5
  AND v.reliability >= 4
  AND (v.fuel_l_per_100km IS NULL OR v.fuel_l_per_100km <= 5.5)
ORDER BY v.discount_pct DESC
LIMIT 20;

-- name: negotiation_room
-- Known-issue haggling room per model/year. DISTINCT first: vw_listing_issues has one row
-- per listing x issue, so summing it directly would multiply by the number of ads
-- (the bug in the original query #8).
WITH issues_per_model_year AS (
    SELECT DISTINCT brand, model, model_year, issue, severity, negotiation_leverage_sek
    FROM vw_listing_issues
)
SELECT brand, model, model_year,
       COUNT(*)                        AS known_issues,
       SUM(negotiation_leverage_sek)   AS negotiation_room_sek,
       MAX(CASE severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) AS worst_severity
FROM issues_per_model_year
GROUP BY brand, model, model_year
ORDER BY negotiation_room_sek DESC
LIMIT 20;

-- name: depreciation_by_model
-- The valuation model's own output: yearly depreciation per model, latest fit.
SELECT brand, model, n_listings, depreciation_pct_per_year, value_age3_sek, value_age8_sek,
       residual_sd_pct
FROM valuation_models
WHERE level = 'model'
  AND fitted_date_id = (SELECT MAX(fitted_date_id) FROM valuation_models)
ORDER BY depreciation_pct_per_year DESC;


-- ---------------------------------------------------------------------------
-- Level 6 — data quality checks (run after every ETL)
-- ---------------------------------------------------------------------------

-- name: data_quality
-- Each row is a check; a non-zero 'problems' value needs a look.
SELECT 'listings without mileage' AS check_name, COUNT(*) AS problems
FROM fact_listings WHERE mileage_km IS NULL AND is_active = 1
UNION ALL
SELECT 'listings without valuation', COUNT(*)
FROM fact_listings WHERE market_value_sek IS NULL AND is_active = 1
UNION ALL
SELECT 'unresolved county', COUNT(*)
FROM fact_listings f JOIN dim_location l ON l.location_id = f.location_id
WHERE l.county = 'unknown' AND f.is_active = 1
UNION ALL
SELECT 'no reference spec matched', COUNT(*)
FROM fact_listings WHERE spec_id IS NULL AND is_active = 1
UNION ALL
SELECT 'implausible mileage (> 60 000 km/yr)', COUNT(*)
FROM fact_listings f JOIN dim_car c ON c.car_id = f.car_id
-- sqlite: scalar MAX() is GREATEST() on PostgreSQL
WHERE f.mileage_km > 60000 * MAX(1, CAST(strftime('%Y', 'now') AS INTEGER) - c.model_year)
UNION ALL
SELECT 'ads with damage wording', COUNT(*)
FROM fact_listings WHERE damage_flag = 1 AND is_active = 1;

-- name: etl_history
-- Data lineage: what each pipeline run did.
SELECT run_id, started_at, source, listings_loaded, new_listings, price_changes, deactivated,
       reached_end
FROM etl_runs
ORDER BY run_id DESC
LIMIT 10;
