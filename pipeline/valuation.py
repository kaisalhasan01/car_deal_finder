"""Year- and mileage-aware market valuation: a hierarchical hedonic regression.

Replaces the old cohort-median valuer, which pooled all model years whenever an
exact (brand, model, year) cohort had < 3 listings. A 2013 car was then compared
with newer, pricier ones, and a flat 1 kr/km mileage adjustment swung values by
±100 000 kr (HANDOFF §8.1).

Model, for each listing:
    log(price) = b0 + b1·a + b2·a² + b3·d + b4·a·d  (+ cohort offset)
    a = age − mean age (years)
    d = (km − 15 000·age) / 10 000 − mean   ("mileage vs what is normal for its age")

Using mileage *relative to its age* decorrelates it from age, and the a·d term
lets excess mileage hurt an old, cheap car more (in %) than a young one.

Coefficients are estimated at three levels with partial pooling. Each level is a
ridge regression shrunk toward its parent, not toward zero:

    global  --prior-->  brand  --prior-->  (brand, model)  -->  (brand, model, year) offset

The last level is an intercept-only offset per model year. It is shrunk with
K_COHORT pseudo-listings and uses residuals clipped at ±1.5σ, so a few deals in a
cohort can't drag its level down. With plenty of same-year listings it behaves like
the old cohort median; with few it falls back to the regression curve.

A model with few listings borrows its depreciation slope from its brand, and a
brand borrows from the whole market. The prior strength is set in
"pseudo-listings" (K_*), so it reads like: "a model needs ~20 listings before its
own depreciation slope outweighs the brand's".

Other properties:
  * Leave-one-out. A listing never takes part in valuing itself. It is removed
    from both the brand and the model fit, which is exact and cheap with 4×4
    solves. Otherwise a lone cheap car sets its own "market value".
  * Robust. Gross outliers (|residual| > 3σ) and ads whose text suggests damage
    ("defekt", "motorfel" ...) are excluded from fitting, but still valued.
  * Uncertainty. σ per model (from LOO residuals, shrunk toward the brand) gives
    an 80 % interval and a z-score of how unusual the price is.

Assumptions: prices are asking prices, not transaction prices; depreciation is
smooth in age; one (brand, model) spans all engines and trims.
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
K_COHORT = 4.0        # ... behind a model-year's own price level
CLIP_Z = 1.5          # cohort offsets use residuals clipped at ±CLIP_Z·σ
NU_SIGMA = 5.0        # pseudo-listings behind a group's residual spread
TRIM_Z = 3.0          # |z| above this is an outlier, excluded from fitting
MIN_FIT_LISTINGS = 8  # below this there is no market to learn from
Z80 = 1.2816          # two-sided 80 % interval
DEFAULT_KM_PER_YEAR = 15_000

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
    discount_pct: float | None = None   # (value - price) / value · 100, if a price is known
    deal_z: float | None = None         # (log value - log price) / sigma

    def as_dict(self) -> dict:
        return asdict(self)


def looks_damaged(*texts: str | None) -> bool:
    return bool(DAMAGE_PATTERN.search(" ".join(t for t in texts if t)))


def _norm(value) -> str:
    return str(value).strip().lower() if value is not None else ""


class HedonicValuer:
    """Fit on a list of listing dicts, then value them (LOO) or new cars."""

    def __init__(self, ref_year: int | None = None, k_intercept: float = K_INTERCEPT,
                 k_slope: float = K_SLOPE, k_curve: float = K_CURVE):
        self.ref_year = ref_year or date.today().year
        self.k = np.array([k_intercept, k_slope, k_curve, k_slope, k_curve])
        self.fitted = False

    # ------------------------------------------------------------------ design
    def _raw_features(self, car: dict) -> tuple[float, float]:
        age = max(0.0, float(self.ref_year - int(car["year"])))
        km = car.get("mileage")
        if km is None:
            km = max(age, 0.5) * DEFAULT_KM_PER_YEAR     # impute typical usage
        return age, float(km) / 10_000

    def _x(self, age: float, km10k: float) -> np.ndarray:
        a = age - self._mean_age
        d = km10k - age * DEFAULT_KM_PER_YEAR / 10_000 - self._mean_dev
        return np.array([1.0, a, a * a, d, a * d])

    # --------------------------------------------------------------------- fit
    def fit(self, listings: list[dict]) -> "HedonicValuer":
        rows = [(i, it) for i, it in enumerate(listings)
                if it.get("price") and it.get("year") and it.get("brand") and it.get("model")]
        self._listings = listings
        self.fitted = False
        if len(rows) < MIN_FIT_LISTINGS:
            return self
        feats = np.array([self._raw_features(it) for _, it in rows])
        self._mean_age = feats[:, 0].mean()
        self._mean_dev = (feats[:, 1] - feats[:, 0] * DEFAULT_KM_PER_YEAR / 10_000).mean()
        X = np.array([self._x(a, m) for a, m in feats])
        y = np.log(np.array([float(it["price"]) for _, it in rows]))
        brands = np.array([_norm(it["brand"]) for _, it in rows])
        models = np.array([f"{_norm(it['brand'])}|{_norm(it['model'])}" for _, it in rows])
        cohorts = np.array([f"{g}|{int(it['year'])}" for g, (_, it) in zip(models, rows)])
        clean = np.array([not looks_damaged(it.get("title"), it.get("model_spec"))
                          for _, it in rows])

        # Penalties in "pseudo-listings": k_j times the average squared feature.
        self.lam = self.k * np.maximum((X ** 2).mean(axis=0), 1e-9)
        self.lam[0] = self.k[0]

        # Global fit (near-OLS) with iterative outlier trimming.
        inlier = clean.copy()
        tiny = self.lam * 1e-6
        for _ in range(3):
            b_glob = self._solve(X[inlier], y[inlier], np.zeros(X.shape[1]), tiny)
            resid = y - X @ b_glob
            sigma_glob = float(np.sqrt(np.mean(resid[inlier] ** 2)))
            new = clean & (np.abs(resid) <= TRIM_Z * max(sigma_glob, 1e-6))
            if (new == inlier).all():
                break
            inlier = new
        self.b_glob, self.sigma_glob = b_glob, max(sigma_glob, 0.02)

        # Brand and model systems (A = XᵀX + Λ, r = Xᵀy + Λ·prior), inliers only.
        self.brand_sys, self.model_sys = {}, {}
        for b in np.unique(brands[inlier]):
            m = inlier & (brands == b)
            A, r = self._system(X[m], y[m], self.b_glob)
            self.brand_sys[b] = {"A": A, "r": r, "b": np.linalg.solve(A, r), "n": int(m.sum())}
        for g in np.unique(models[inlier]):
            m = inlier & (models == g)
            brand = g.split("|")[0]
            A_data = X[m].T @ X[m] + np.diag(self.lam)
            r_data = X[m].T @ y[m]
            b = np.linalg.solve(A_data, r_data + self.lam * self.brand_sys[brand]["b"])
            self.model_sys[g] = {"A": A_data, "r_data": r_data, "b": b, "n": int(m.sum())}

        self._X, self._y, self._brands, self._models, self._cohorts = X, y, brands, models, cohorts
        self._inlier, self._rows = inlier, [i for i, _ in rows]
        loo_model = self._leave_one_out()
        self._loo_pred = loo_model
        self._fit_sigmas()                      # model-level σ, used to clip cohort residuals
        self._loo_pred = loo_model + self._cohort_offsets()
        self._fit_sigmas()                      # final σ from the full LOO predictor
        self.fitted = True
        return self

    def _cohort_offsets(self) -> np.ndarray:
        """Shrunken per-model-year level offsets (LOO for training rows)."""
        X, y = self._X, self._y
        clipped = np.zeros(len(y))
        for j in range(len(y)):
            if self._inlier[j]:
                sd = self.sigma_model[self._models[j]]
                r = y[j] - X[j] @ self.model_sys[self._models[j]]["b"]
                clipped[j] = float(np.clip(r, -CLIP_Z * sd, CLIP_Z * sd))
        self.cohort_sys = {}
        for c in np.unique(self._cohorts[self._inlier]):
            m = self._inlier & (self._cohorts == c)
            self.cohort_sys[c] = {"sum": float(clipped[m].sum()), "n": int(m.sum())}
        offsets = np.zeros(len(y))
        for j in range(len(y)):
            cs = self.cohort_sys.get(self._cohorts[j])
            if cs is None:
                continue
            own = 1 if self._inlier[j] else 0
            offsets[j] = (cs["sum"] - clipped[j]) / (cs["n"] - own + K_COHORT)
        return offsets

    def _cohort_offset(self, cohort_key: str) -> tuple[float, int]:
        cs = self.cohort_sys.get(cohort_key)
        return (cs["sum"] / (cs["n"] + K_COHORT), cs["n"]) if cs else (0.0, 0)

    def _system(self, X, y, prior):
        return X.T @ X + np.diag(self.lam), X.T @ y + self.lam * prior

    @staticmethod
    def _solve(X, y, prior, lam):
        return np.linalg.solve(X.T @ X + np.diag(lam), X.T @ y + lam * prior)

    def _leave_one_out(self) -> np.ndarray:
        """Exact LOO log-predictions for every training row (brand and model refit)."""
        X, y = self._X, self._y
        pred = np.empty(len(y))
        for i in range(len(y)):
            b_key, m_key = self._brands[i], self._models[i]
            x = X[i]
            if not self._inlier[i]:                      # never in the fit: plain prediction
                pred[i] = x @ self._coef(b_key, m_key)
                continue
            bs = self.brand_sys[b_key]
            b_brand = np.linalg.solve(bs["A"] - np.outer(x, x), bs["r"] - x * y[i])
            ms = self.model_sys[m_key]
            b_model = np.linalg.solve(ms["A"] - np.outer(x, x),
                                      ms["r_data"] - x * y[i] + self.lam * b_brand)
            pred[i] = x @ b_model
        return pred

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

    def _make(self, log_value, method, n, sigma, price) -> Valuation:
        confidence = ("high" if method == "hedonic-model" and n >= 15 else
                      "medium" if method == "hedonic-model" and n >= 5 else "low")
        log_value = float(log_value)
        value = math.exp(log_value)
        v = Valuation(value=int(round(value)), low=int(round(value * math.exp(-Z80 * sigma))),
                      high=int(round(value * math.exp(Z80 * sigma))), method=method, n=n,
                      confidence=confidence, sigma=round(sigma, 4))
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
            b_key, m_key = self._brands[j], self._models[j]
            own = bool(self._inlier[j])
            method, n, sigma = self._level(b_key, m_key, exclude_self=own)
            v = self._make(self._loo_pred[j], method, n, sigma, self._listings[i].get("price"))
            v.cohort_n = max(0, self._cohort_offset(self._cohorts[j])[1] - int(own))
            out[i] = v
        return out

    def value(self, car: dict) -> Valuation | None:
        """Value a car that was not part of the fit."""
        if not self.fitted or not car.get("year") or not car.get("brand"):
            return None
        b_key, m_key = _norm(car["brand"]), f"{_norm(car['brand'])}|{_norm(car.get('model'))}"
        x = self._x(*self._raw_features(car))
        method, n, sigma = self._level(b_key, m_key, exclude_self=False)
        offset, cohort_n = (self._cohort_offset(f"{m_key}|{int(car['year'])}")
                            if m_key in self.model_sys else (0.0, 0))
        v = self._make(float(x @ self._coef(b_key, m_key)) + offset, method, n, sigma,
                       car.get("price"))
        v.cohort_n = cohort_n
        return v

    # ---------------------------------------------------------- introspection
    def curve(self, brand: str, model: str, ages=range(0, 16),
              km_per_year: int = DEFAULT_KM_PER_YEAR) -> list[dict]:
        """Typical value by age for charts (mileage = age × km_per_year)."""
        if not self.fitted:
            return []
        b_key, m_key = _norm(brand), f"{_norm(brand)}|{_norm(model)}"
        coef = self._coef(b_key, m_key)
        out = []
        for age in ages:
            x = self._x(float(age), max(age, 0.5) * km_per_year / 10_000)
            out.append({"age": age, "value": int(round(math.exp(float(x @ coef))))})
        return out

    def summaries(self) -> list[dict]:
        """One row per fitted group: interpretable depreciation metrics for SQL/Power BI."""
        if not self.fitted:
            return []
        rows = []
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
        for level, b, m, coef, n, sigma in groups:
            def value_at(age):
                x = self._x(float(age), age * DEFAULT_KM_PER_YEAR / 10_000)
                return math.exp(float(x @ coef))
            v3, v4, v8 = value_at(3), value_at(4), value_at(8)
            rows.append({
                "level": level,
                "brand": display.get(b, b) if b else None,
                "model": display.get(f"{b}|{m}", m) if m else None,
                "n_listings": n,
                "value_age3_sek": int(round(v3)),
                "value_age8_sek": int(round(v8)),
                "depreciation_pct_per_year": round((1 - v4 / v3) * 100, 2),
                # +10 000 km above what is typical for the age, at the average age
                "mileage_effect_pct_per_10k_km": round((math.exp(float(coef[3])) - 1) * 100, 2),
                "residual_sd_pct": round((math.exp(sigma) - 1) * 100, 1),
            })
        return rows


def value_listings(listings: list[dict], ref_year: int | None = None
                   ) -> tuple[HedonicValuer, list[Valuation | None]]:
    """Fit on `listings` and return leave-one-out valuations aligned with them."""
    valuer = HedonicValuer(ref_year=ref_year).fit(listings)
    return valuer, valuer.value_training()
