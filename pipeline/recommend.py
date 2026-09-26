"""Personalized buyer advisor CLI.

Given a buyer's preferences, find the best cars for *them*, not just the
cheapest, and print a ranked shortlist with cost of ownership and a
"what to check / haggle on" briefing per car.

    # auto: real listings from car_deals.db if it has any, else a labelled demo
    python -m pipeline.recommend --budget 200000 --body Kombi,SUV --max-insurance 700

    python -m pipeline.recommend --source db --seller private --drivetrain AWD
    python -m pipeline.recommend --source sample --json        # machine-readable demo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import db                                              # noqa: E402
from pipeline.matcher import BuyerProfile, attach_valuations, rank   # noqa: E402
from pipeline.valuation import value_listings                        # noqa: E402
from scrapers import sample_data                                     # noqa: E402

SEVERITY_LABEL = {"high": "🔴", "medium": "🟠", "low": "🟡"}
CONFIDENCE_SV = {"high": "hög", "medium": "medel", "low": "låg"}
SELLER_SV = {"private": "Privat", "dealer": "Handlare"}
DEMO_BANNER = ("⚠️  DEMO: syntetisk exempeldata, INTE riktiga annonser. För riktig data: "
               "python -m pipeline.run --source blocket --query \"...\"")


def sek(value) -> str:
    return f"{int(value):,}".replace(",", " ")


def _csv_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {v.strip() for v in value.split(",") if v.strip()}


def build_profile(args) -> BuyerProfile:
    return BuyerProfile(
        budget_max=args.budget, max_mileage=args.max_mileage, min_year=args.min_year,
        drivetrains=_csv_set(args.drivetrain), body_types=_csv_set(args.body),
        fuel_types=_csv_set(args.fuel), max_l_per_100km=args.max_lphmil,
        max_insurance_monthly=args.max_insurance, seller_types=_csv_set(args.seller),
        include_damaged=args.include_damaged, annual_km=args.annual_km,
        driver_age=args.driver_age, claims_free_years=args.claims_free_years,
        home_city=args.home_city,
    )


def load_candidates(source: str, db_path: Path, limit: int) -> tuple[list[dict], str, bool]:
    """(listings with valuation fields, human description, is_demo)."""
    if source in ("db", "auto") and db_path.exists():
        conn = db.connect(db_path)
        try:
            db.init_db(conn)
            rows = db.fetch_listings(conn, active_only=True)
            last = conn.execute("SELECT MAX(finished_at) FROM etl_runs").fetchone()[0]
        except db.SchemaVersionError as exc:
            raise SystemExit(f"{exc}")
        finally:
            conn.close()
        sources = {r["source"] for r in rows}
        if rows:
            demo = "sample" in sources
            label = (f"{db_path.name}: {len(rows)} aktiva annonser, senast uppdaterad "
                     f"{(last or '?')[:16].replace('T', ' ')}")
            return rows, label, demo
    if source == "db":
        raise SystemExit(f"Ingen data i {db_path}. Kör först: python -m pipeline.run --source blocket ...")
    listings = sample_data.generate(n=limit)
    _, vals = value_listings(listings)
    return attach_valuations(listings, vals), f"{len(listings)} syntetiska annonser", True


def _profile_summary(p: BuyerProfile) -> str:
    parts = []
    if p.budget_max: parts.append(f"budget ≤ {sek(p.budget_max)} kr")
    if p.drivetrains: parts.append("drivlina " + "/".join(sorted(p.drivetrains)))
    if p.body_types: parts.append("kaross " + "/".join(sorted(p.body_types)))
    if p.fuel_types: parts.append("bränsle " + "/".join(sorted(p.fuel_types)))
    if p.max_l_per_100km: parts.append(f"≤ {p.max_l_per_100km} L/100km")
    if p.max_insurance_monthly: parts.append(f"försäkring ≤ {p.max_insurance_monthly}/mån")
    if p.min_year: parts.append(f"≥ {p.min_year}")
    if p.max_mileage: parts.append(f"≤ {sek(p.max_mileage)} km")
    if p.seller_types: parts.append("säljare " + "/".join(SELLER_SV.get(s, s) for s in sorted(p.seller_types)))
    return ", ".join(parts) or "inga filter"


def print_results(results: list[dict], profile: BuyerProfile, top_n: int, source_label: str,
                  demo: bool) -> None:
    print("\n" + "=" * 78)
    print("  DINA TOPPMATCHNINGAR")
    print("  Profil: " + _profile_summary(profile))
    print("  Data:   " + source_label)
    if demo:
        print("  " + DEMO_BANNER)
    print("=" * 78)
    if not results:
        print("\n  Inga bilar matchade dina filter. Prova att lätta på något krav.\n")
        return

    for i, r in enumerate(results[:top_n], 1):
        a = r["attributes"]
        print(f"\n[{i}] {r['brand']} {r['model']} {r['year']}   — Match {r['match_score']}/100")
        if r.get("title") and not demo:
            print(f"    \"{r['title']}\"")
        line = f"    Pris {sek(r['price'])} kr"
        if r.get("market_value_sek"):
            line += (f"  ·  värde ~{sek(r['market_value_sek'])} kr "
                     f"(80 %: {sek(r['value_low_sek'])}–{sek(r['value_high_sek'])})"
                     f"  ·  rabatt {r['discount_pct']:+.0f} %"
                     f"  ·  säkerhet {CONFIDENCE_SV.get(r.get('value_confidence'), '?')}")
        print(line)
        km = f"{sek(r['mileage'])} km" if r.get("mileage") is not None else "okänt miltal"
        seller = SELLER_SV.get(r.get("seller_type"), "okänd säljare")
        print(f"    {km} · {a['body_type'] or '?'} · {a['drivetrain'] or '?'} · {a['fuel'] or '?'} · "
              f"{a['power_hp'] or '?'} hk · pålitlighet {a['reliability'] or '?'}/5 · "
              f"{seller} · {r.get('city') or '?'}")
        costs = [f"försäkring {r['insurance_monthly']}/mån"]
        if r["fuel_cost_year"]:
            typical = " (typvärde)" if a["consumption_source"] == "typical" else ""
            costs.append(f"energi {sek(r['fuel_cost_year'])}{typical}")
        costs += [f"skatt {sek(r['tax_year'])}", f"reparationsreserv {sek(r['repair_reserve_year'])}"]
        print(f"    Kostnad/år ~{sek(r['tco_year'])} kr  ({', '.join(costs)})")

        brief = r["briefing"]
        for flag in brief["red_flags"]:
            print(f"    🚩 {flag}")
        for signal in brief["signals"]:
            print(f"    📉 {signal}")
        if brief["issues"]:
            print("    Att kolla / pruta på:")
            for it in brief["issues"]:
                print(f"      {SEVERITY_LABEL.get(it.get('severity'), '•')} {it['issue']}")
                print(f"         → {it['what_to_check']}")
            print(f"    💬 Förhandlingsutrymme att verifiera: ~{sek(brief['negotiation_room_sek'])} kr")
        else:
            print("    ✅ Inga kända typfel registrerade för denna modell/år.")
        if brief["seller_note"]:
            print(f"    ⚖️  {brief['seller_note']}")
        for link in brief["history_links"]:
            print(f"    🔎 {link['label']}: {link['url']}")
        if not demo:
            print(f"    🔗 {r['url']}")
    print()


def to_json(results: list[dict], top_n: int, source_label: str, demo: bool) -> str:
    keep = ("brand", "model", "year", "price", "mileage", "url", "regnr", "seller_type", "city",
            "county", "market_value_sek", "value_low_sek", "value_high_sek", "discount_pct",
            "deal_z", "value_confidence", "match_score", "insurance_monthly", "fuel_cost_year",
            "tax_year", "repair_reserve_year", "tco_year", "attributes", "briefing")
    return json.dumps({"data": source_label, "demo": demo,
                       "results": [{k: r.get(k) for k in keep} for r in results[:top_n]]},
                      ensure_ascii=False, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    # Windows pipes default to cp1252, which cannot encode the emoji markers below.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Personalized car buyer advisor")
    ap.add_argument("--source", choices=["auto", "db", "sample"], default="auto",
                    help="auto = real listings from --db if present, else a labelled demo")
    ap.add_argument("--db", default=str(db.DEFAULT_DB_PATH))
    ap.add_argument("--budget", type=int, default=220_000, help="max asking price (SEK)")
    ap.add_argument("--max-mileage", type=int, default=None, help="max mileage (km)")
    ap.add_argument("--min-year", type=int, default=2015)
    ap.add_argument("--drivetrain", default=None, help="comma list: FWD,RWD,AWD")
    ap.add_argument("--body", default=None, help="comma list: Kombi,SUV,Sedan,Halvkombi,Sportbil")
    ap.add_argument("--fuel", default=None, help="comma list: Bensin,Diesel,El,Hybrid,Laddhybrid")
    ap.add_argument("--max-lphmil", type=float, default=None, help="max L/100km (combustion)")
    ap.add_argument("--max-insurance", type=int, default=None, help="max insurance SEK/month")
    ap.add_argument("--seller", default=None, help="private and/or dealer (comma list)")
    ap.add_argument("--include-damaged", action="store_true", help="keep 'defekt'/'motorfel' ads")
    ap.add_argument("--annual-km", type=int, default=15_000, help="yearly driving for cost calc")
    ap.add_argument("--driver-age", type=int, default=None, help="driver age (affects insurance)")
    ap.add_argument("--claims-free-years", type=int, default=None, help="skadefria år (bonus)")
    ap.add_argument("--home-city", default=None, help="owner's city (affects insurance)")
    ap.add_argument("--limit", type=int, default=300, help="sample size in demo mode")
    ap.add_argument("--top", type=int, default=5, help="results to show")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = ap.parse_args(argv)

    listings, source_label, demo = load_candidates(args.source, Path(args.db), args.limit)
    profile = build_profile(args)
    results = rank(listings, profile)
    if args.json:
        print(to_json(results, args.top, source_label, demo))
    else:
        print_results(results, profile, args.top, source_label, demo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
