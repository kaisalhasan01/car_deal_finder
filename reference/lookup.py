"""Lookup helpers over the curated reference data (specs + known issues).

Single source of truth = the Python data modules; the DB loaders read the same
lists. Matching is case-insensitive on (brand, model), and issues are further
filtered by whether the car's year falls in the issue's year range.
"""
from __future__ import annotations

from .known_issues_data import ISSUES
from .specs_data import SPECS

_SPEC_INDEX = {(s["brand"].lower(), s["model"].lower()): s for s in SPECS}


def get_spec(brand: str, model: str) -> dict | None:
    """Representative spec for a model, or None if we have no reference data."""
    return _SPEC_INDEX.get((str(brand).strip().lower(), str(model).strip().lower()))


def get_issues(brand: str, model: str, year: int | None = None) -> list[dict]:
    """Known issues for a model, optionally filtered to those covering `year`."""
    b, m = str(brand).strip().lower(), str(model).strip().lower()
    out = []
    for it in ISSUES:
        if it["brand"].lower() != b or it["model"].lower() != m:
            continue
        if year is not None:
            yf, yt = it.get("year_from"), it.get("year_to")
            if (yf is not None and year < yf) or (yt is not None and year > yt):
                continue
        out.append(it)
    return out
