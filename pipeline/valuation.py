"""Year- and mileage-aware market valuation: a hierarchical hedonic regression.

Replaces the old cohort-median valuer, which pooled all model years whenever an
exact (brand, model, year) cohort had < 3 listings. A 2013 car was then compared
with newer, pricier ones, and a flat 1 kr/km mileage adjustment swung values by
±100 000 kr (HANDOFF §8.1).

The question it answers: *what do cars like this one, with this model, age,
mileage and equipment, cost on Blocket right now?* Two Audi A4 2011 at 50 000 kr
are not equally good buys if one has driven 20 000 mil and the other 10 000.

Model, for each listing:
    log(price) = b0 + b1·a + b2·a² + (b3 + b4·a)·d + Σ c_k·attr_k  (+ model-year offset)
    a    = age − mean age (years)
    d    = (km − 15 000·age)/10 000 − mean   mileage vs what is normal for the age
    attr = dealer, automatic, AWD, diesel, hybrid, plug-in hybrid, electric
           (centered 0/1 dummies; unknown -> neutral)

Measuring mileage *relative to its age* decorrelates it from age, and the a·d term
lets excess mileage hurt an old, cheap car more (in %) than a young one.

Coefficients are estimated at three levels with partial pooling. Each level is a
ridge regression shrunk toward its parent, not toward zero:

    global  --prior-->  brand  --prior-->  (brand, model)  -->  model-year offset

The prior strength is set in "pseudo-listings" (K_*), so it reads like: "a model
needs ~20 listings before its own depreciation slope outweighs the brand's". The
model-year offset is intercept-only. It is shrunk with K_COHORT pseudo-listings
and uses residuals clipped at ±1.5σ. With many same-year listings it behaves like
the old cohort median; with few it falls back to the regression curve.

Guards (a model must never say a 2011 car is worth more than a 2013):
  * value never rises with age: past the parabola's vertex, or outside the ages
    seen in the data, the curve continues at -5 %/year;
  * an older car with the *same odometer reading* is never worth more than a
    younger one (isotonic: running minimum over younger ages at fixed km);
  * extra mileage never raises the value, and mileage outside the observed range
    is not extrapolated;
  * valuations outside the data are marked `extrapolated` (low confidence).
The model-year offset sits on top of the guarded curve. It may rank neighbouring
years slightly out of order, which reflects real year effects such as facelifts or
a year with a known engine fault.

Other properties:
  * Leave-one-out. A listing never takes part in valuing itself: it is removed
    from the brand fit, the model fit and its cohort offset. Otherwise a lone
    cheap car sets its own "market value".
  * Robust. Gross outliers (|residual| > 3σ) and ads whose text suggests damage
    ("defekt", "motorfel" ...) are excluded from fitting, but still valued.
  * Uncertainty. σ per model (from LOO residuals, shrunk toward the brand) gives
    an 80 % interval and a z-score of how unusual the price is.

Assumptions: asking prices, not transaction prices; one (brand, model) spans all
generations and trims except for the attributes above.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np

K_INTERCEPT = 3.0     # pseudo-listings behind a group's price level
K_SLOPE = 20.0        # ... behind its depreciation (age) and mileage slopes
K_CURVE = 50.0        # ... behind the curvature (age²) and age×mileage terms
K_ATTR = 30.0         # ... behind attribute effects (dealer, gearbox, AWD, fuel)
K_COHORT = 4.0        # ... behind a model-year's own price level
CLIP_Z = 1.5          # cohort offsets use residuals clipped at ±CLIP_Z·σ
NU_SIGMA = 5.0        # pseudo-listings behind a group's residual spread
TRIM_Z = 3.0          # |z| above this is an outlier, excluded from fitting
MIN_FIT_LISTINGS = 8  # below this there is no market to learn from
Z80 = 1.2816          # two-sided 80 % interval
DEFAULT_KM_PER_YEAR = 15_000
OUT_OF_RANGE_DEPRECIATION = 0.05   # log-units per year beyond the ages seen (~5 %/yr)
MIN_YOUNG_SLOPE = 0.05             # newer than any listing: at least +5 %/yr
MIN_MILEAGE_EFFECT = 0.005         # extra 10 000 km must cost at least 0.5 %

ATTRIBUTES = ("dealer", "automatic", "awd", "diesel", "hybrid", "plugin_hybrid", "electric")
_FUEL_DUMMY = {"Diesel": "diesel", "Hybrid": "hybrid", "Laddhybrid": "plugin_hybrid",
               "El": "electric"}
N_CORE = 5

DAMAGE_PATTERN = re.compile(
    r"defekt|motorfel|motorhaveri|motorskada|växellådsfel|reparationsobjekt|renoveringsobjekt|"
    r"renoveringsprojekt|krockskad|skadad|startar (?:ej|inte)|går (?:ej|inte)|reservdelar|"
    r"säljes i befintligt skick som|export(?:bil)?\b|körförbud|avställd",
    re.IGNORECASE,
)


@dataclass
class Valuation:
    value: int                 # SEK, conditional median of asking prices
    low: int                   # 80 % interval
    high: int
    method: str                # 'hedonic-model' | 'hedonic-brand' | 'hedonic-global'
    n: int                     # comparable listings at the level used (excluding itself)
    confidence: str            # 'high' | 'medium' | 'low'
    sigma: float               # residual sd in log space at that level
    cohort_n: int = 0          # same model *and* model year among them (excluding itself)
    extrapolated: bool = False  # age or mileage outside what the data covers
    discount_pct: float | None = None   # (value - price) / value · 100, if a price is known
    deal_z: float | None = None         # (log value - log price) / sigma

    def as_dict(self) -> dict:
        return asdict(self)


def looks_damaged(*texts: str | None) -> bool:
    return bool(DAMAGE_PATTERN.search(" ".join(t for t in texts if t)))


def _norm(value) -> str:
    return str(value).strip().lower() if value is not None else ""


def _attr_raw(car: dict) -> list[float]:
    """0/1 per attribute, NaN when unknown (becomes neutral after centering)."""
    seller = car.get("seller_type")
    gearbox = car.get("gearbox")
    fuel = car.get("fuel_type")
    fuel_flag = _FUEL_DUMMY.get(fuel) if fuel else None
    return [
        {"dealer": 1.0, "private": 0.0}.get(seller, math.nan),
        {"Automat": 1.0, "Manuell": 0.0}.get(gearbox, math.nan),
        1.0 if car.get("drivetrain") == "AWD" else 0.0,   # set only when the ad states AWD
        *[(1.0 if fuel_flag == name else 0.0) if fuel else math.nan
          for name in ("diesel", "hybrid", "plugin_hybrid", "electric")],
    ]


class HedonicValuer:
    """Fit on a list of listing dicts, then value them (LOO) or new cars."""

    def __init__(self, ref_year: int | None = None):
        self.ref_year = ref_year or date.today().year
        self.k = np.array([K_INTERCEPT, K_SLOPE, K_CURVE, K_SLOPE, K_CURVE]
                          + [K_ATTR] * len(ATTRIBUTES))
        self.fitted = False

    # ------------------------------------------------------------------ design
    def _age_dev(self, car: dict) -> tuple[float, float]:
        """(age in years, mileage deviation from normal for that age in 10 000 km)."""
        age = max(0.0, float(self.ref_year - int(car["year"])))
        km = car.get("mileage")
        if km is None:
            km = max(age, 0.5) * DEFAULT_KM_PER_YEAR     # impute typical usage
        return age, (float(km) - age * DEFAULT_KM_PER_YEAR) / 10_000

    def _attrs(self, car: dict) -> np.ndarray:
        raw = np.array(_attr_raw(car))
        return np.where(np.isnan(raw), 0.0, raw - self._attr_mean)

    def _x(self, age: float, dev: float, attrs: np.ndarray) -> np.ndarray:
        a, d = age - self._mean_age, dev - self._mean_dev
        return np.concatenate([[1.0, a, a * a, d, a * d], attrs])

    def _predict_log(self, coef: np.ndarray, age: float, dev: float,
                     attrs: np.ndarray) -> tuple[float, bool]:
        """Guarded prediction, monotone in age at a fixed odometer reading."""
        lv, out_of_range = self._predict_log_raw(coef, age, dev, attrs)
        km10k = dev + age * DEFAULT_KM_PER_YEAR / 10_000          # the odometer reading
        younger = age - 1.0
        while younger >= self._age_lo - 1.0 and younger >= 0:
            dev_y = km10k - younger * DEFAULT_KM_PER_YEAR / 10_000
            lv = min(lv, self._predict_log_raw(coef, younger, dev_y, attrs)[0])
            younger -= 1.0
        return lv, out_of_range

    def _predict_log_raw(self, coef: np.ndarray, age: float, dev: float,
                         attrs: np.ndarray) -> tuple[float, bool]:
        """Monotone in age at fixed *relative* mileage; no wild extrapolation."""
        b0, b1, b2, b3, b4 = coef[:N_CORE]
        a_eff = min(max(age, self._age_lo), self._age_hi)
        extra = age - a_eff                               # >0 older than data, <0 newer
        ac = a_eff - self._mean_age
        if b2 > 0 and ac > -b1 / (2 * b2):                # parabola turns upward: flatten
            vertex = -b1 / (2 * b2)
            extra += ac - vertex
            ac = vertex
        d_clamped = min(max(dev, self._dev_lo), self._dev_hi)
        dc = d_clamped - self._mean_dev
        slope_d = min(b3 + b4 * ac, -MIN_MILEAGE_EFFECT)
        lv = b0 + b1 * ac + b2 * ac * ac + slope_d * dc + float(coef[N_CORE:] @ attrs)
        if extra > 0:
            lv -= OUT_OF_RANGE_DEPRECIATION * extra
        elif extra < 0:   # age slope at the boundary, at normal mileage (independent of km)
            slope_young = min(b1 + 2 * b2 * ac, -MIN_YOUNG_SLOPE)
            lv += slope_young * extra
        out_of_range = age < self._age_lo or age > self._age_hi or d_clamped != dev
        return float(lv), out_of_range

    # --------------------------------------------------------------------- fit
    def fit(self, listings: list[dict]) -> "HedonicValuer":
        rows = [(i, it) for i, it in enumerate(listings)
                if it.get("price") and it.get("year") and it.get("brand") and it.get("model")]
        self._listings = listings
        self.fitted = False
        if len(rows) < MIN_FIT_LISTINGS:
            return self
        age_dev = np.array([self._age_dev(it) for _, it in rows])
        attr_raw = np.array([_attr_raw(it) for _, it in rows])
        self._mean_age, self._mean_dev = age_dev[:, 0].mean(), age_dev[:, 1].mean()
        known = ~np.isnan(attr_raw)
        self._attr_mean = np.array([attr_raw[known[:, k], k].mean() if known[:, k].any() else 0.0
                                    for k in range(attr_raw.shape[1])])
        attrs = np.where(np.isnan(attr_raw), 0.0, attr_raw - self._attr_mean)
        X = np.array([self._x(a, d, at) for (a, d), at in zip(age_dev, attrs)])
        y = np.log(np.array([float(it["price"]) for _, it in rows]))
        brands = np.array([_norm(it["brand"]) for _, it in rows])
        models = np.array([f"{_norm(it['brand'])}|{_norm(it['model'])}" for _, it in rows])
        cohorts = np.array([f"{g}|{int(it['year'])}" for g, (_, it) in zip(models, rows)])
        clean = np.array([not looks_damaged(it.get("title"), it.get("model_spec"))
                          for _, it in rows])

        # Penalties in "pseudo-listings": k_j times the average squared feature.
        self.lam = self.k * np.maximum((X ** 2).mean(axis=0), 1e-6)
        self.lam[0] = self.k[0]

        # Global fit (near-OLS) with iterative outlier trimming.
        inlier = clean.copy()
        weak = np.maximum(self.lam * 1e-3, 1e-6)
        for _ in range(3):
            b_glob = self._solve(X[inlier], y[inlier], np.zeros(X.shape[1]), weak)
            resid = y - X @ b_glob
            sigma_glob = float(np.sqrt(np.mean(resid[inlier] ** 2)))
            new = clean & (np.abs(resid) <= TRIM_Z * max(sigma_glob, 1e-6))
            if (new == inlier).all():
                break
            inlier = new
        self.b_glob, self.sigma_glob = b_glob, max(sigma_glob, 0.02)
        self._age_lo, self._age_hi = float(age_dev[inlier, 0].min()), float(age_dev[inlier, 0].max())
        self._dev_lo, self._dev_hi = (float(np.percentile(age_dev[inlier, 1], 2)),
                                      float(np.percentile(age_dev[inlier, 1], 98)))

        # Brand and model systems (A = XᵀX + Λ, r = Xᵀy + Λ·prior), inliers only.
        self.brand_sys, self.model_sys = {}, {}
        for b in np.unique(brands[inlier]):
            m = inlier & (brands == b)
            A, r = X[m].T @ X[m] + np.diag(self.lam), X[m].T @ y[m] + self.lam * self.b_glob
            self.brand_sys[b] = {"A": A, "r": r, "b": np.linalg.solve(A, r), "n": int(m.sum())}
        for g in np.unique(models[inlier]):
            m = inlier & (models == g)
            A_data, r_data = X[m].T @ X[m] + np.diag(self.lam), X[m].T @ y[m]
            b = np.linalg.solve(A_data, r_data + self.lam * self.brand_sys[g.split("|")[0]]["b"])
            self.model_sys[g] = {"A": A_data, "r_data": r_data, "b": b, "n": int(m.sum())}

        self._X, self._y, self._train_age_dev, self._attr = X, y, age_dev, attrs
        self._brands, self._models, self._cohorts = brands, models, cohorts
        self._inlier, self._rows = inlier, [i for i, _ in rows]
        loo_model, self._extrap = self._leave_one_out()
        self._loo_pred = loo_model
        self._fit_sigmas()                      # model-level σ, used to clip cohort residuals
        self._loo_pred = loo_model + self._cohort_offsets()
        self._fit_sigmas()                      # final σ from the full LOO predictor
        self.fitted = True
        return self

    @staticmethod
    def _solve(X, y, prior, lam):
        return np.linalg.solve(X.T @ X + np.diag(lam), X.T @ y + lam * prior)

    def _row_pred(self, coef: np.ndarray, j: int) -> tuple[float, bool]:
        age, dev = self._train_age_dev[j]
        return self._predict_log(coef, age, dev, self._attr[j])

    def _leave_one_out(self) -> tuple[np.ndarray, np.ndarray]:
        """Exact LOO log-predictions for every training row (brand and model refit)."""
        X, y = self._X, self._y
        pred, extrap = np.empty(len(y)), np.zeros(len(y), dtype=bool)
        for i in range(len(y)):
            b_key, m_key = self._brands[i], self._models[i]
            if not self._inlier[i]:                      # never in the fit: plain prediction
                pred[i], extrap[i] = self._row_pred(self._coef(b_key, m_key), i)
                continue
            x = X[i]
            bs = self.brand_sys[b_key]
            b_brand = np.linalg.solve(bs["A"] - np.outer(x, x), bs["r"] - x * y[i])
            ms = self.model_sys[m_key]
            b_model = np.linalg.solve(ms["A"] - np.outer(x, x),
                                      ms["r_data"] - x * y[i] + self.lam * b_brand)
            pred[i], extrap[i] = self._row_pred(b_model, i)
        return pred, extrap

    def _fit_sigmas(self) -> None:
        """Residual spread per level from LOO residuals, shrunk toward the parent."""
        res = self._y - self._loo_pred
        ok = self._inlier
        self.sigma_brand, self.sigma_model = {}, {}
        for b in self.brand_sys:
            r = res[ok & (self._brands == b)]
            self.sigma_brand[b] = math.sqrt(
                (float((r ** 2).sum()) + NU_SIGMA * self.sigma_glob ** 2) / (len(r) + NU_SIGMA))
        for g in self.model_sys:
            r = res[ok & (self._models == g)]
            parent = self.sigma_brand[g.split("|")[0]]
            self.sigma_model[g] = math.sqrt(
                (float((r ** 2).sum()) + NU_SIGMA * parent ** 2) / (len(r) + NU_SIGMA))

    def _cohort_offsets(self) -> np.ndarray:
        """Shrunken per-model-year level offsets (LOO for training rows)."""
        y = self._y
        clipped = np.zeros(len(y))
        for j in range(len(y)):
            if self._inlier[j]:
                sd = self.sigma_model[self._models[j]]
                r = y[j] - self._row_pred(self.model_sys[self._models[j]]["b"], j)[0]
                clipped[j] = float(np.clip(r, -CLIP_Z * sd, CLIP_Z * sd))
        self.cohort_sys = {}
        for c in np.unique(self._cohorts[self._inlier]):
            m = self._inlier & (self._cohorts == c)
            self.cohort_sys[c] = {"sum": float(clipped[m].sum()), "n": int(m.sum())}
        offsets = np.zeros(len(y))
        for j in range(len(y)):
            cs = self.cohort_sys.get(self._cohorts[j])
            if cs is not None:
                own = 1 if self._inlier[j] else 0
                offsets[j] = (cs["sum"] - clipped[j]) / (cs["n"] - own + K_COHORT)
        return offsets

    def _cohort_offset(self, cohort_key: str) -> tuple[float, int]:
        cs = self.cohort_sys.get(cohort_key)
        return (cs["sum"] / (cs["n"] + K_COHORT), cs["n"]) if cs else (0.0, 0)

    # ----------------------------------------------------------------- predict
    def _coef(self, brand_key: str, model_key: str) -> np.ndarray:
        if model_key in self.model_sys:
            return self.model_sys[model_key]["b"]
        if brand_key in self.brand_sys:
            return self.brand_sys[brand_key]["b"]
        return self.b_glob

    def _level(self, brand_key, model_key, exclude_self: bool) -> tuple[str, int, float]:
        own = 1 if exclude_self else 0
        if model_key in self.model_sys and self.model_sys[model_key]["n"] - own > 0:
            return "hedonic-model", self.model_sys[model_key]["n"] - own, self.sigma_model[model_key]
        if brand_key in self.brand_sys and self.brand_sys[brand_key]["n"] - own > 0:
            return "hedonic-brand", self.brand_sys[brand_key]["n"] - own, self.sigma_brand[brand_key]
        return "hedonic-global", int(self._inlier.sum()) - own, self.sigma_glob

    def _make(self, log_value, method, n, sigma, price, extrapolated=False) -> Valuation:
        confidence = ("low" if extrapolated or method != "hedonic-model" else
                      "high" if n >= 15 else "medium" if n >= 5 else "low")
        log_value = float(log_value)
        value = math.exp(log_value)
        v = Valuation(value=int(round(value)), low=int(round(value * math.exp(-Z80 * sigma))),
                      high=int(round(value * math.exp(Z80 * sigma))), method=method, n=n,
                      confidence=confidence, sigma=round(sigma, 4), extrapolated=extrapolated)
        if price:
            v.discount_pct = round((value - price) / value * 100, 2)
            v.deal_z = round(float((log_value - math.log(price)) / sigma), 2)
        return v

    def value_training(self) -> list[Valuation | None]:
        """Leave-one-out valuations aligned with the list passed to `fit`."""
        out: list[Valuation | None] = [None] * len(self._listings)
        if not self.fitted:
            return out
        for j, i in enumerate(self._rows):
            own = bool(self._inlier[j])
            method, n, sigma = self._level(self._brands[j], self._models[j], exclude_self=own)
            v = self._make(self._loo_pred[j], method, n, sigma, self._listings[i].get("price"),
                           extrapolated=bool(self._extrap[j]))
            v.cohort_n = max(0, self._cohort_offset(self._cohorts[j])[1] - int(own))
            out[i] = v
        return out

    def value(self, car: dict) -> Valuation | None:
        """Value a car that was not part of the fit."""
        if not self.fitted or not car.get("year") or not car.get("brand"):
            return None
        b_key, m_key = _norm(car["brand"]), f"{_norm(car['brand'])}|{_norm(car.get('model'))}"
        age, dev = self._age_dev(car)
        lv, extrap = self._predict_log(self._coef(b_key, m_key), age, dev, self._attrs(car))
        offset, cohort_n = (self._cohort_offset(f"{m_key}|{int(car['year'])}")
                            if m_key in self.model_sys else (0.0, 0))
        method, n, sigma = self._level(b_key, m_key, exclude_self=False)
        v = self._make(lv + offset, method, n, sigma, car.get("price"), extrapolated=extrap)
        v.cohort_n = cohort_n
        return v

    # ---------------------------------------------------------- introspection
    def _typical_log(self, coef: np.ndarray, age: float, km_per_year: int) -> float:
        dev = age * (km_per_year - DEFAULT_KM_PER_YEAR) / 10_000
        return self._predict_log(coef, float(age), dev, np.zeros(len(ATTRIBUTES)))[0]

    def curve(self, brand: str, model: str, ages=range(0, 16),
              km_per_year: int = DEFAULT_KM_PER_YEAR) -> list[dict]:
        """Typical value by age for charts (mileage = age × km_per_year)."""
        if not self.fitted:
            return []
        coef = self._coef(_norm(brand), f"{_norm(brand)}|{_norm(model)}")
        return [{"age": age, "value": int(round(math.exp(self._typical_log(coef, age, km_per_year))))}
                for age in ages]

    def age_range(self) -> tuple[float, float] | None:
        """Youngest and oldest age (years) the model has seen; outside is extrapolation."""
        return (self._age_lo, self._age_hi) if self.fitted else None

    def attribute_effects(self) -> dict[str, float]:
        """Market-wide price effect of each attribute, in % (dealer premium etc.)."""
        if not self.fitted:
            return {}
        return {name: round((math.exp(float(c)) - 1) * 100, 2)
                for name, c in zip(ATTRIBUTES, self.b_glob[N_CORE:])}

    def summaries(self) -> list[dict]:
        """One row per fitted group: interpretable depreciation metrics for SQL/Power BI."""
        if not self.fitted:
            return []
        groups = [("global", "", "", self.b_glob, int(self._inlier.sum()), self.sigma_glob)]
        groups += [("brand", b, "", s["b"], s["n"], self.sigma_brand[b])
                   for b, s in self.brand_sys.items()]
        groups += [("model", g.split("|")[0], g.split("|")[1], s["b"], s["n"], self.sigma_model[g])
                   for g, s in self.model_sys.items()]
        display = {}
        for it in self._listings:
            if it.get("brand") and it.get("model"):
                display.setdefault(_norm(it["brand"]), it["brand"])
                display.setdefault(f"{_norm(it['brand'])}|{_norm(it['model'])}", it["model"])
        rows = []
        for level, b, m, coef, n, sigma in groups:
            v3, v4, v8 = (math.exp(self._typical_log(coef, a, DEFAULT_KM_PER_YEAR))
                          for a in (3, 4, 8))
            rows.append({
                "level": level,
                "brand": display.get(b, b) if b else "",
                "model": display.get(f"{b}|{m}", m) if m else "",
                "n_listings": n,
                "value_age3_sek": int(round(v3)),
                "value_age8_sek": int(round(v8)),
                "depreciation_pct_per_year": round((1 - v4 / v3) * 100, 2),
                # +10 000 km above what is typical for the age, at the average age
                "mileage_effect_pct_per_10k_km": round(
                    (math.exp(min(float(coef[3]), -MIN_MILEAGE_EFFECT)) - 1) * 100, 2),
                "residual_sd_pct": round((math.exp(sigma) - 1) * 100, 1),
            })
        return rows


def value_listings(listings: list[dict], ref_year: int | None = None
                   ) -> tuple[HedonicValuer, list[Valuation | None]]:
    """Fit on `listings` and return leave-one-out valuations aligned with them."""
    valuer = HedonicValuer(ref_year=ref_year).fit(listings)
    return valuer, valuer.value_training()
