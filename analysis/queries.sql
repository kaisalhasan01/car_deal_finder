-- ===========================================================================
-- Swedish Car Deal Finder — analysis queries for Power BI / DB Browser
-- Positive discount_pct = listed below estimated value.
-- ===========================================================================

-- 1) TOP DEALS (credible band only).
SELECT c.brand, c.model, c.year, f.blocket_price, f.carinfo_value, f.discount_pct,
       f.mileage, f.days_on_market, l.city, l.county, f.value_method, f.url
FROM fact_listings f
JOIN dim_car c       ON c.car_id = f.car_id
JOIN dim_location l  ON l.location_id = f.location_id
WHERE f.discount_pct BETWEEN 5 AND 40
ORDER BY f.discount_pct DESC
LIMIT 50;

-- 2) AVG DISCOUNT BY BRAND.
SELECT c.brand, COUNT(*) AS listings,
       ROUND(AVG(f.discount_pct), 1) AS avg_discount_pct,
       ROUND(AVG(f.blocket_price))   AS avg_price
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
WHERE f.discount_pct IS NOT NULL
GROUP BY c.brand
ORDER BY avg_discount_pct DESC;

-- 3) DEALS BY COUNTY.
SELECT l.county, COUNT(*) AS listings,
       SUM(CASE WHEN f.discount_pct >= 10 THEN 1 ELSE 0 END) AS strong_deals,
       ROUND(AVG(f.discount_pct), 1) AS avg_discount_pct
FROM fact_listings f
JOIN dim_location l ON l.location_id = f.location_id
WHERE f.discount_pct IS NOT NULL
GROUP BY l.county
ORDER BY strong_deals DESC;

-- 4) PRICE vs MILEAGE scatter feed.
SELECT c.brand, c.model, c.year, f.mileage, f.blocket_price, f.carinfo_value, f.discount_pct
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
WHERE f.mileage IS NOT NULL
ORDER BY c.brand, c.model, f.mileage;

-- ===========================================================================
-- Buyer-advisor queries (join the reference tables)
-- ===========================================================================

-- 5) LISTINGS ENRICHED WITH SPECS — the base table for buyer filtering in Power BI.
--    Slice by drivetrain / body_type / fuel / economy with slicers.
SELECT c.brand, c.model, c.year,
       f.blocket_price, f.carinfo_value, f.discount_pct, f.mileage,
       s.body_type, s.drivetrain, s.primary_fuel, s.power_hp,
       s.fuel_l_per_100km, s.energy_kwh_per_100km, s.annual_tax_sek, s.reliability,
       l.city, l.county, f.url
FROM fact_listings f
JOIN dim_car c       ON c.car_id = f.car_id
JOIN dim_location l  ON l.location_id = f.location_id
LEFT JOIN car_specs s ON s.brand = c.brand AND s.model = c.model
ORDER BY f.discount_pct DESC;

-- 6) DEALS ON RELIABLE, ECONOMICAL CARS (example buyer filter baked into SQL).
SELECT c.brand, c.model, c.year, f.blocket_price, f.discount_pct,
       s.drivetrain, s.body_type, s.fuel_l_per_100km, s.reliability, f.url
FROM fact_listings f
JOIN dim_car c        ON c.car_id = f.car_id
JOIN car_specs s      ON s.brand = c.brand AND s.model = c.model
WHERE f.discount_pct >= 5
  AND s.reliability >= 4
  AND (s.fuel_l_per_100km IS NULL OR s.fuel_l_per_100km <= 5.5)
ORDER BY f.discount_pct DESC;

-- 7) KNOWN-ISSUE BRIEFING per listing — what to check + total haggling room.
SELECT c.brand, c.model, c.year, f.blocket_price,
       ki.severity, ki.category, ki.issue, ki.what_to_check,
       ki.negotiation_leverage_sek
FROM fact_listings f
JOIN dim_car c       ON c.car_id = f.car_id
JOIN known_issues ki ON ki.brand = c.brand AND ki.model = c.model
                    AND (ki.year_from IS NULL OR c.year >= ki.year_from)
                    AND (ki.year_to   IS NULL OR c.year <= ki.year_to)
ORDER BY c.brand, c.model, ki.severity DESC;

-- 8) TOTAL NEGOTIATION ROOM per model/year (sum of known-issue leverage).
SELECT c.brand, c.model, c.year,
       COUNT(ki.issue_id)                       AS known_issues,
       SUM(ki.negotiation_leverage_sek)         AS negotiation_room_sek
FROM fact_listings f
JOIN dim_car c       ON c.car_id = f.car_id
JOIN known_issues ki ON ki.brand = c.brand AND ki.model = c.model
                    AND (ki.year_from IS NULL OR c.year >= ki.year_from)
                    AND (ki.year_to   IS NULL OR c.year <= ki.year_to)
GROUP BY c.brand, c.model, c.year
ORDER BY negotiation_room_sek DESC;
