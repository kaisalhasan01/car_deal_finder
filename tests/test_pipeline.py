"""End-to-end: sample ETL -> advisor, and the offline real-data path
(Blocket fixture -> raw snapshots -> replay ETL -> advisor)."""
from __future__ import annotations

import json

from conftest import FakeSession
from pipeline import recommend, run
from scrapers.blocket import BlocketScraper


def test_sample_etl_then_advisor(tmp_path, capsys):
    dbfile = tmp_path / "sample.db"
    assert run.main(["--source", "sample", "--limit", "150", "--db", str(dbfile)]) == 0
    assert run.main(["--source", "sample", "--limit", "150", "--db", str(dbfile)]) == 0  # rerun ok
    capsys.readouterr()
    assert recommend.main(["--db", str(dbfile), "--source", "db", "--json", "--top", "3",
                           "--budget", "300000", "--min-year", "2013"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["demo"] is True                      # sample data is always labelled
    assert len(out["results"]) == 3
    assert all(r["market_value_sek"] and r["tco_year"] for r in out["results"])


def test_real_data_path_offline(tmp_path, capsys):
    snapshots = tmp_path / "raw"
    list(BlocketScraper(session=FakeSession(), delay=0, snapshot_dir=snapshots).search(pages=5))
    dbfile = tmp_path / "real.db"
    assert run.main(["--source", "replay", "--replay", str(snapshots), "--db", str(dbfile)]) == 0
    capsys.readouterr()
    assert recommend.main(["--db", str(dbfile), "--source", "db", "--json", "--min-year", "2010",
                           "--budget", "400000", "--top", "10"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["demo"] is False
    urls = {r["url"] for r in out["results"]}
    assert "https://www.blocket.se/mobility/item/20101001" in urls
    v60 = next(r for r in out["results"] if r["url"].endswith("20101001"))
    assert v60["attributes"]["drivetrain"] == "AWD" and v60["regnr"] == "ABC123"
    assert any("car.info" in link["url"] for link in v60["briefing"]["history_links"])


def test_sample_and_real_cannot_share_a_database(tmp_path, capsys):
    dbfile = tmp_path / "mixed.db"
    assert run.main(["--source", "sample", "--limit", "50", "--db", str(dbfile)]) == 0
    snapshots = tmp_path / "raw"
    list(BlocketScraper(session=FakeSession(), delay=0, snapshot_dir=snapshots).search(pages=5))
    assert run.main(["--source", "replay", "--replay", str(snapshots), "--db", str(dbfile)]) == 2
