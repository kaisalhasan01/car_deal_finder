"""SQL catalog, Power BI export and theme: every query runs, exports are complete."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from analysis.sql_runner import load_queries
from pipeline import export, run

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def sample_db(tmp_path_factory):
    dbfile = tmp_path_factory.mktemp("analysis") / "sample.db"
    assert run.main(["--source", "sample", "--limit", "200", "--db", str(dbfile)]) == 0
    return dbfile


def test_every_catalog_query_runs(sample_db):
    queries = load_queries()
    assert len(queries) >= 15
    conn = sqlite3.connect(sample_db)
    for name, sql in queries.items():
        df = pd.read_sql_query(sql, conn)                 # raises on any SQL error
        assert df.columns.size > 0, name
    conn.close()


def test_negotiation_room_is_per_model_year_not_per_ad(sample_db):
    conn = sqlite3.connect(sample_db)
    df = pd.read_sql_query(load_queries()["negotiation_room"], conn)
    conn.close()
    assert df["known_issues"].max() <= 4                  # the old query multiplied by ad count


def test_export_writes_all_tables(sample_db, tmp_path):
    counts = export.export(sample_db, tmp_path, "csv")
    assert set(counts) == set(export.EXPORTS)
    assert counts["fact_listings"] == 200 and counts["listings_flat"] == 200
    df = pd.read_csv(tmp_path / "fact_listings.csv", encoding="utf-8-sig")
    assert {"listing_id", "car_id", "price_sek", "market_value_sek"} <= set(df.columns)
    dates = pd.read_csv(tmp_path / "dim_date.csv", encoding="utf-8-sig")
    assert pd.to_datetime(dates["date"]).diff().dropna().dt.days.eq(1).all()   # continuous


def test_parquet_export_keeps_types(sample_db, tmp_path):
    pytest.importorskip("pyarrow")
    export.export(sample_db, tmp_path, "parquet")
    df = pd.read_parquet(tmp_path / "fact_listings.parquet")
    assert df["price_sek"].dtype.kind == "i" and df["discount_pct"].dtype.kind == "f"


def test_powerbi_theme_is_valid_and_matches_app_palette():
    from app.charts import PALETTES
    theme = json.loads((ROOT / "powerbi" / "theme.json").read_text(encoding="utf-8"))
    assert theme["dataColors"][:4] == PALETTES["light"]["series"]
    assert {"name", "background", "foreground", "good", "bad"} <= set(theme)


def test_sql_guide_solutions_run(sample_db):
    import re
    guide = (ROOT / "analysis" / "SQL_GUIDE.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```sql\n(.*?)```", guide, flags=re.DOTALL)
    assert len(blocks) >= 6
    conn = sqlite3.connect(sample_db)
    for sql in blocks:
        pd.read_sql_query(sql, conn)
    conn.close()
