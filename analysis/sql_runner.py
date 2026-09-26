"""Run the named queries in analysis/queries.sql and print the results as tables.

    python -m analysis.sql_runner                         # all queries, sample DB if no real one
    python -m analysis.sql_runner --db car_deals.db --only top_deals,price_drops
    python -m analysis.sql_runner --list

Queries are separated by "-- name: <id>" lines. A handy way to learn SQL on your
own data: edit a query, rerun, compare.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
QUERIES = Path(__file__).resolve().parent / "queries.sql"


def load_queries(path: Path = QUERIES) -> dict[str, str]:
    """name -> SQL. Trailing section-header comments belong to the next section, so drop them."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    out = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        lines = body.strip().splitlines()
        while lines and (lines[-1].startswith("--") or not lines[-1].strip()):
            lines.pop()
        out[name] = "\n".join(lines)
    return out


def description(sql: str) -> str:
    """The leading comment block of a query."""
    head = []
    for line in sql.splitlines():
        if not line.startswith("--"):
            break
        head.append(line[2:].strip())
    return " ".join(head)


def default_db() -> Path:
    real, sample = ROOT / "car_deals.db", ROOT / "car_deals_sample.db"
    return real if real.exists() else sample


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None, help="default: car_deals.db, else car_deals_sample.db")
    ap.add_argument("--only", default="", help="comma list of query names")
    ap.add_argument("--list", action="store_true", help="list query names and exit")
    ap.add_argument("--rows", type=int, default=15, help="max rows to print per query")
    args = ap.parse_args(argv)

    queries = load_queries()
    if args.list:
        print("\n".join(queries))
        return 0
    wanted = [q.strip() for q in args.only.split(",") if q.strip()] or list(queries)
    unknown = [q for q in wanted if q not in queries]
    if unknown:
        print(f"unknown query: {', '.join(unknown)} (use --list)")
        return 2
    db_path = Path(args.db) if args.db else default_db()
    if not db_path.exists():
        print(f"{db_path} not found — run `python -m pipeline.run --source sample` first.")
        return 2
    conn = sqlite3.connect(db_path)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print(f"database: {db_path.name}")
    for name in wanted:
        sql = queries[name]
        comment = description(sql)
        df = pd.read_sql_query(sql, conn)
        print(f"\n=== {name} — {len(df)} rows")
        if comment:
            print(f"    {comment}")
        print(df.head(args.rows).to_string(index=False) if not df.empty else "    (no rows)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
