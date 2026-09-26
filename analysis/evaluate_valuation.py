"""Compare the legacy cohort-median valuer with the hierarchical hedonic valuer.

The synthetic generator knows each car's true fair value and which cars were
deliberately underpriced, so we can score both methods honestly:

  * MAPE          — mean absolute % error of the value estimate vs the true value
  * age bias      — mean signed % error per age bucket (the cohort method's flaw)
  * deal finding  — precision / recall / F1 of "discount >= 10 %" vs injected deals

Caveat (HANDOFF §8.7): the generator uses exponential depreciation, which a
log-linear model captures by construction, so these numbers flatter the hedonic
model. They prove the cohort method is biased; real accuracy needs real data.

    python -m analysis.evaluate_valuation            # prints tables
    python -m analysis.evaluate_valuation --write    # also writes docs/VALUATION_EVAL.md
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.valuation import value_listings        # noqa: E402
from scrapers import sample_data                     # noqa: E402
from scrapers.carinfo import CarInfoValuer           # noqa: E402

DEAL_THRESHOLD = 10.0
PRICE_FLOOR = 20_000   # the generator clamps prices here; such rows have no valid "truth"
AGE_BUCKETS = [(0, 5, "0–5 år"), (6, 9, "6–9 år"), (10, 99, "10+ år")]


def _cohort(listings):
    valuer = CarInfoValuer(listings)
    return [valuer.estimate(it)[0] for it in listings]


def _hedonic(listings):
    _, vals = value_listings(listings)
    return [v.value if v else None for v in vals]


def score(listings, values) -> dict:
    today = date.today().year
    errs, signed_by_bucket = [], {label: [] for *_, label in AGE_BUCKETS}
    tp = fp = fn = 0
    for it, value in zip(listings, values):
        truth = it["_fair_value"]
        if not value or truth <= 0 or it["price"] <= PRICE_FLOOR:
            continue
        err = (value - truth) / truth * 100
        if not it["_injected_deal"]:
            errs.append(abs(err))
            age = today - it["year"]
            for lo, hi, label in AGE_BUCKETS:
                if lo <= age <= hi:
                    signed_by_bucket[label].append(err)
        flagged = (value - it["price"]) / value * 100 >= DEAL_THRESHOLD
        tp += flagged and it["_injected_deal"]
        fp += flagged and not it["_injected_deal"]
        fn += (not flagged) and it["_injected_deal"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "mape": statistics.mean(errs), "median_ape": statistics.median(errs),
        "bias": {k: statistics.mean(v) if v else float("nan") for k, v in signed_by_bucket.items()},
        "precision": precision, "recall": recall, "f1": f1, "false_deals": fp,
    }


def evaluate(sizes=(200, 1000), seeds=range(42, 47)) -> list[dict]:
    rows = []
    for n in sizes:
        for name, fn in (("Kohort-median (gammal)", _cohort), ("Hedonisk LOO (ny)", _hedonic)):
            runs = [score(ls, fn(ls)) for ls in (sample_data.generate(n=n, seed=s) for s in seeds)]
            avg = lambda key: statistics.mean(r[key] for r in runs)          # noqa: E731
            rows.append({
                "n": n, "method": name, "mape": avg("mape"), "median_ape": avg("median_ape"),
                "precision": avg("precision"), "recall": avg("recall"), "f1": avg("f1"),
                "false_deals": avg("false_deals"),
                "bias": {k: statistics.mean(r["bias"][k] for r in runs) for k in runs[0]["bias"]},
            })
    return rows


def to_markdown(rows) -> str:
    buckets = [label for *_, label in AGE_BUCKETS]
    lines = [
        "| Listings | Method | MAPE | Median APE | "
        + " | ".join(f"Bias {b}" for b in buckets)
        + " | Deal precision | Deal recall | F1 | False deals |",
        "|---:|---|---:|---:|" + "---:|" * len(buckets) + "---:|---:|---:|---:|",
    ]
    for r in rows:
        bias = " | ".join(f"{r['bias'][b]:+.1f} %" for b in buckets)
        lines.append(
            f"| {r['n']} | {r['method']} | {r['mape']:.1f} % | {r['median_ape']:.1f} % | {bias} | "
            f"{r['precision']:.0%} | {r['recall']:.0%} | {r['f1']:.2f} | {r['false_deals']:.1f} |")
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write docs/VALUATION_EVAL.md")
    args = ap.parse_args()
    table = to_markdown(evaluate())
    print(table)
    if args.write:
        out = PROJECT_ROOT / "docs" / "VALUATION_EVAL.md"
        out.write_text(
            "# Valuation evaluation (synthetic data with known truth)\n\n"
            f"Generated by `python -m analysis.evaluate_valuation --write` on {date.today()}. "
            "Averaged over seeds 42–46. MAPE and bias are measured on non-deal cars against the "
            "generator's true fair value. A deal is flagged at a discount of at least "
            f"{DEAL_THRESHOLD:.0f} %.\n\n{table}\n\n"
            "**Caveat:** the generator's depreciation is exponential, which the log-linear model "
            "assumes, so absolute accuracy here is optimistic. The comparison shows that the "
            "cohort method is biased by age and the hedonic model is not. Real-world accuracy has "
            "to be measured on real Blocket data.\n", encoding="utf-8")
        print(f"\nwrote {out.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
