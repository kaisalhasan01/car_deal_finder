"""Lookup helpers over the curated reference data (specs + known issues).

The Python data modules are the single source of truth; the DB loaders read the
same lists. Matching a listing to a reference model (case-insensitive):
  1. exact (brand, model), ignoring spaces/dots/hyphens ('Model3' == 'Model 3');
  2. the longest reference model that starts the listing's model on a word boundary
     ('V60 Cross Country' -> 'V60', 'Golf Sportscombi' -> 'Golf').
Specs come in fuel variants. The variant whose primary_fuel equals the listing's
fuel wins, otherwise the row marked is_default.
"""
from __future__ import annotations

import re

from .known_issues_data import ISSUES
from .specs_data import SPECS


def _k(text) -> str:
    return re.sub(r"[\s.\-_]+", "", str(text or "").strip().lower())


_MODELS_BY_BRAND: dict[str, list[str]] = {}
for _s in SPECS:
    _MODELS_BY_BRAND.setdefault(_s["brand"].lower(), [])
    if _s["model"] not in _MODELS_BY_BRAND[_s["brand"].lower()]:
        _MODELS_BY_BRAND[_s["brand"].lower()].append(_s["model"])
for _i in ISSUES:                       # issues may exist for models without a spec row
    _MODELS_BY_BRAND.setdefault(_i["brand"].lower(), [])
    if _i["model"] not in _MODELS_BY_BRAND[_i["brand"].lower()]:
        _MODELS_BY_BRAND[_i["brand"].lower()].append(_i["model"])


def match_model(brand: str | None, model: str | None) -> tuple[str, str] | None:
    """Canonical (brand, model) from the reference data, or None."""
    if not brand or not model:
        return None
    b = str(brand).strip().lower()
    candidates = _MODELS_BY_BRAND.get(b)
    if not candidates:
        return None
    listing = str(model).strip()
    for ref in candidates:
        if _k(ref) == _k(listing):
            return _canonical_brand(b), ref
    prefixed = [ref for ref in candidates
                if re.match(rf"{re.escape(ref.lower())}(?:$|[\s/\-,(])", listing.lower())]
    if prefixed:
        return _canonical_brand(b), max(prefixed, key=len)
    return None


def _canonical_brand(brand_lower: str) -> str:
    for s in SPECS:
        if s["brand"].lower() == brand_lower:
            return s["brand"]
    for i in ISSUES:
        if i["brand"].lower() == brand_lower:
            return i["brand"]
    return brand_lower.title()


def get_spec(brand: str, model: str, fuel: str | None = None) -> dict | None:
    """Reference spec for a model (fuel-matched variant preferred), or None."""
    hit = match_model(brand, model)
    if hit is None:
        return None
    rows = [s for s in SPECS if s["brand"] == hit[0] and s["model"] == hit[1]]
    if not rows:
        return None
    chosen = next((s for s in rows if fuel and s["primary_fuel"] == fuel), None)
    if chosen is None:
        chosen = next((s for s in rows if s.get("is_default", True)), rows[0])
    return {**chosen, "fuel_matched": bool(fuel and chosen["primary_fuel"] == fuel)}


def spec_key(spec: dict | None) -> tuple[str, str, str] | None:
    """Key into database.db.spec_id_map()."""
    if not spec:
        return None
    return spec["brand"].lower(), spec["model"].lower(), spec["primary_fuel"]


_ENGINE_FUELS = [   # keyword in the issue's engine text -> fuels it can apply to
    (re.compile(r"diesel|tdi|crdi|dci|hdi|cdti|tdci|om651|n47|skyactiv-d", re.I), {"Diesel"}),
    (re.compile(r"phev", re.I), {"Laddhybrid"}),
    (re.compile(r"electric", re.I), {"El"}),
    (re.compile(r"^hybrid$", re.I), {"Hybrid", "Laddhybrid"}),
    (re.compile(r"tfsi|tsi|tce|puretech|ecoboost|bensin|dig-t|gdi|skyactiv-g|n20", re.I),
     {"Bensin", "Hybrid", "Laddhybrid"}),
]


def issue_fuels(engine: str | None) -> set[str] | None:
    """Fuels an engine-specific issue applies to; None = any (e.g. gearbox, chassis)."""
    if not engine:
        return None
    for pattern, fuels in _ENGINE_FUELS:
        if pattern.search(engine):
            return fuels
    return None


def get_issues(brand: str, model: str, year: int | None = None,
               fuel: str | None = None) -> list[dict]:
    """Known issues for a model, filtered to `year` and (when known) the car's fuel,
    so a diesel isn't briefed about a petrol engine's fault."""
    hit = match_model(brand, model)
    if hit is None:
        return []
    out = []
    for it in ISSUES:
        if it["brand"] != hit[0] or it["model"] != hit[1]:
            continue
        if year is not None:
            yf, yt = it.get("year_from"), it.get("year_to")
            if (yf is not None and year < yf) or (yt is not None and year > yt):
                continue
        fuels = issue_fuels(it.get("engine"))
        if fuel and fuels is not None and fuel not in fuels:
            continue
        out.append(it)
    return out
