"""Personalized buyer advisor CLI.

Given a buyer's preferences, find the best cars for *them* — not just the
cheapest — and print a ranked shortlist with cost-of-ownership and a
"what to check / haggle on" briefing per car.

Examples:
    # default example buyer
    python -m pipeline.recommend

    # an AWD estate, max 200k, max insurance 700/mo, decent economy
    python -m pipeline.recommend --budget 200000 --drivetrain AWD,FWD \
        --body Kombi,SUV --max-insurance 700 --max-lphmil 6.0 --min-year 2016
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers import sample_data                  # noqa: E402
from scrapers.carinfo import CarInfoValuer        # noqa: E402
from pipeline.matcher import BuyerProfile, rank   # noqa: E402

SEVERITY_LABEL = {"high": "🔴", "medium": "🟠", "low": "🟡"}


def _csv_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {v.strip() for v in value.split(",") if v.strip()}


def build_profile(args) -> BuyerProfile:
    return BuyerProfile(
        budget_max=args.budget,
        max_mileage=args.max_mileage,
        min_year=args.min_year,
        drivetrains=_csv_set(args.drivetrain),
        body_types=_csv_set(args.body),
        fuel_types=_csv_set(args.fuel),
        max_l_per_100km=args.max_lphmil,
        max_insurance_monthly=args.max_insurance,
        annual_km=args.annual_km,
        driver_age=args.driver_age,
        claims_free_years=args.claims_free_years,
        home_city=args.home_city,
    )


def compute_deals(listings):
    """Attach (value, discount_pct) to each listing via the hybrid valuer."""
    valuer = CarInfoValuer(listings)
    out = []
    for it in listings:
        value, _method = valuer.estimate(it)
        pct = round((value - it["price"]) / value * 100, 1) if value else None
        out.append((it, value, pct))
    return out


def print_results(results, profile, top_n):
    print("\n" + "=" * 74)
    print("  DINA TOPPMATCHNINGAR")
    print("  Profil: " + _profile_summary(profile))
    print("=" * 74)

    if not results:
        print("\n  Inga bilar matchade dina filter. Prova att lätta på något krav.\n")
        return

    for i, r in enumerate(results[:top_n], 1):
        spec = r["spec"] or {}
        print(f"\n[{i}] {r['brand']} {r['model']} {r['year']}   "
              f"— Match {r['match_score']}/100")
        print(f"    Pris {r['price']:,} kr".replace(",", " ")
              + (f"  (värde ~{r['carinfo_value']:,} kr, ".replace(",", " ")
                 + f"rabatt {r['discount_pct']:+.0f}%)" if r["carinfo_value"] else "")
              + f"  ·  {r.get('mileage', '?'):,} km".replace(",", " "))
        print(f"    {spec.get('body_type','?')} · {spec.get('drivetrain','?')} · "
              f"{spec.get('primary_fuel','?')} · {spec.get('power_hp','?')} hk · "
              f"pålitlighet {spec.get('reliability','?')}/5")
        print(f"    Kostnad/år ~{r['tco_year']:,} kr".replace(",", " ")
              + f"  (försäkring {r['insurance_monthly']}/mån"
              + (f", bränsle {r['fuel_cost_year']:,}".replace(",", " ") if r['fuel_cost_year'] else "")
              + f", skatt {r['tax_year']}, reparationsreserv {r['repair_reserve_year']})")

        brief = r["briefing"]
        for flag in brief["red_flags"]:
            print(f"    🚩 {flag}")
        if brief["issues"]:
            print("    Att kolla / pruta på:")
            for it in brief["issues"]:
                mark = SEVERITY_LABEL.get(it.get("severity"), "•")
                print(f"      {mark} {it['issue']}")
                print(f"         → {it['what_to_check']}")
            print(f"    💬 Förhandlingsutrymme att verifiera: "
                  f"~{brief['negotiation_room_sek']:,} kr".replace(",", " "))
        else:
            print("    ✅ Inga kända typfel registrerade för denna modell/år.")
    print()


def _profile_summary(p: BuyerProfile) -> str:
    parts = []
    if p.budget_max: parts.append(f"budget ≤ {p.budget_max:,} kr".replace(",", " "))
    if p.drivetrains: parts.append("drivlina " + "/".join(sorted(p.drivetrains)))
    if p.body_types: parts.append("kaross " + "/".join(sorted(p.body_types)))
    if p.fuel_types: parts.append("bränsle " + "/".join(sorted(p.fuel_types)))
    if p.max_l_per_100km: parts.append(f"≤ {p.max_l_per_100km} L/100km")
    if p.max_insurance_monthly: parts.append(f"försäkring ≤ {p.max_insurance_monthly}/mån")
    if p.min_year: parts.append(f"≥ {p.min_year}")
    if p.max_mileage: parts.append(f"≤ {p.max_mileage:,} km".replace(",", " "))
    return ", ".join(parts) or "inga filter"


def main() -> None:
    # Windows pipes default to cp1252, which cannot encode the emoji markers below.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="Personalized car buyer advisor")
    ap.add_argument("--budget", type=int, default=220_000, help="max asking price (SEK)")
    ap.add_argument("--max-mileage", type=int, default=None, help="max mileage (km)")
    ap.add_argument("--min-year", type=int, default=2015)
    ap.add_argument("--drivetrain", default=None, help="comma list: FWD,RWD,AWD")
    ap.add_argument("--body", default=None, help="comma list: Kombi,SUV,Sedan,Halvkombi,Sportbil")
    ap.add_argument("--fuel", default=None, help="comma list: Bensin,Diesel,El,Hybrid")
    ap.add_argument("--max-lphmil", type=float, default=None, help="max L/100km (combustion)")
    ap.add_argument("--max-insurance", type=int, default=None, help="max insurance SEK/month")
    ap.add_argument("--annual-km", type=int, default=15_000, help="yearly driving for cost calc")
    ap.add_argument("--driver-age", type=int, default=None, help="driver age (affects insurance)")
    ap.add_argument("--claims-free-years", type=int, default=None, help="skadefria år (bonus)")
    ap.add_argument("--home-city", default=None, help="owner's city (affects insurance)")
    ap.add_argument("--limit", type=int, default=300, help="listings to consider")
    ap.add_argument("--top", type=int, default=5, help="results to show")
    args = ap.parse_args()

    listings = sample_data.generate(n=args.limit)
    deals = compute_deals(listings)
    profile = build_profile(args)
    results = rank(deals, profile)
    print_results(results, profile, args.top)


if __name__ == "__main__":
    main()
