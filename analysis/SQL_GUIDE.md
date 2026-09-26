# Learn SQL on your own car data

Twelve exercises on the project's database, from a first `SELECT` to window functions.
Try each one before opening the solution. Run your SQL any way you like:

```bash
python -m analysis.sql_runner --list                   # the catalog in queries.sql
python -m analysis.sql_runner --only top_deals         # run one catalog query
sqlite3 car_deals_sample.db                             # or DB Browser for SQLite (GUI)
```

Use `car_deals_sample.db` (after `python -m pipeline.run --source sample`) or your real
`car_deals.db`. The schema is in `database/schema.sql`, and the ready-made views
(`vw_listings`, `vw_deal_board` …) are in `database/views.sql`.

**The star schema in one sentence:** `fact_listings` holds one row per ad (price, mileage,
market value …). It points to `dim_car` (brand, model, year), `dim_location` (city, county),
`dim_seller` (private/dealer) and `dim_date` (the calendar). `fact_price_snapshots` holds the
price per ad per day.

---

### 1. First look (SELECT, WHERE, ORDER BY)
List the 10 cheapest active Volvo listings with model, model year and price.
*Hint: you need to JOIN `dim_car` to get the brand.*

<details><summary>Solution</summary>

```sql
SELECT c.model, c.model_year, f.price_sek
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
WHERE c.brand = 'Volvo' AND f.is_active = 1
ORDER BY f.price_sek
LIMIT 10;
```
</details>

### 2. Counting (GROUP BY)
How many active listings does each county have?

<details><summary>Solution</summary>

```sql
SELECT l.county, COUNT(*) AS listings
FROM fact_listings f
JOIN dim_location l ON l.location_id = f.location_id
WHERE f.is_active = 1
GROUP BY l.county
ORDER BY listings DESC;
```
</details>

### 3. Averages with a filter on the group (HAVING)
Average price per model, but only for models with at least 10 listings.

<details><summary>Solution</summary>

```sql
SELECT c.brand, c.model, COUNT(*) AS n, ROUND(AVG(f.price_sek)) AS avg_price
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
GROUP BY c.brand, c.model
HAVING COUNT(*) >= 10
ORDER BY avg_price DESC;
```
</details>

### 4. Conditional counting (CASE)
Per brand: the number of listings and how many are "strong deals" (discount ≥ 10 %).

<details><summary>Solution</summary>

```sql
SELECT c.brand,
       COUNT(*) AS listings,
       SUM(CASE WHEN f.discount_pct >= 10 THEN 1 ELSE 0 END) AS strong_deals
FROM fact_listings f
JOIN dim_car c ON c.car_id = f.car_id
GROUP BY c.brand;
```
</details>

### 5. Three joins
Show each active listing's brand, model, city, seller type and price. Four tables.

<details><summary>Solution</summary>

```sql
SELECT c.brand, c.model, l.city, s.seller_type, f.price_sek
FROM fact_listings f
JOIN dim_car c      ON c.car_id = f.car_id
JOIN dim_location l ON l.location_id = f.location_id
JOIN dim_seller s   ON s.seller_id = f.seller_id
WHERE f.is_active = 1;
```
</details>

### 6. LEFT JOIN and missing data
Which active listings have **no** matching reference spec? They are the ones the advisor
can't filter on body type or drivetrain.
*Hint: LEFT JOIN `car_specs` and look for NULL.*

<details><summary>Solution</summary>

```sql
SELECT c.brand, c.model, COUNT(*) AS listings
FROM fact_listings f
JOIN dim_car c        ON c.car_id = f.car_id
LEFT JOIN car_specs s ON s.spec_id = f.spec_id
WHERE f.is_active = 1 AND s.spec_id IS NULL
GROUP BY c.brand, c.model
ORDER BY listings DESC;
```
This is the to-do list for `reference/specs_data.py` once real data arrives.
</details>

### 7. A subquery
Listings priced below the average price of their own model and model year.

<details><summary>Solution</summary>

See `above_model_average` in `queries.sql`.
</details>

### 8. CTE (WITH) for readability
Compute each car's age in a CTE, then average the discount per age bucket
(0–3, 4–7, 8–11, 12+ years).

<details><summary>Solution</summary>

See `age_buckets` in `queries.sql`. Notice how the CTE keeps the bucket logic in one place.
</details>

### 9. Your first window function (ROW_NUMBER)
The single best deal (highest `deal_z`) **per model**.
*Hint: `ROW_NUMBER() OVER (PARTITION BY brand, model ORDER BY deal_z DESC)`, then keep rank 1.*

<details><summary>Solution</summary>

See `best_deal_per_model` in `queries.sql`.
</details>

### 10. Median without MEDIAN()
SQLite has no `MEDIAN()`. Compute the median price per model with `ROW_NUMBER()` and `COUNT() OVER`.

<details><summary>Solution</summary>

See `median_price_per_model` in `queries.sql`. The trick: keep rows `(n+1)/2` and `(n+2)/2`
(integer division) and average them. That covers both odd and even `n`.
</details>

### 11. Comparing with the previous row (LAG)
Find every price change in `fact_price_snapshots`: date, old price, new price and change.
*It needs at least two ETL runs on different days to return rows.*

<details><summary>Solution</summary>

See `price_drops` in `queries.sql`.
</details>

### 12. Running totals and moving averages
Daily new listings (by publish date) with a running total and a 7-day moving average.

<details><summary>Solution</summary>

See `new_listings_running_total` in `queries.sql`. `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`
is the moving-window frame.
</details>

---

**Next steps:** write a view of your own in `database/views.sql` (e.g. "cars under 150 000 kr
with reliability ≥ 4 in your county"), then use it in Power BI (`powerbi/README.md`).
