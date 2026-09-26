"""Bilrådgivaren — Streamlit front-end for the Car Deal Finder.

    streamlit run app/streamlit_app.py --server.port 8501

Reads the database named by CAR_DEALS_DB (default car_deals.db). Without real data
it shows a clearly labelled demo market.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import charts                                    # noqa: E402
from database import db                                   # noqa: E402
from pipeline import service                              # noqa: E402
from pipeline.matcher import BuyerProfile                 # noqa: E402
from reference.lookup import get_issues                   # noqa: E402
from reference.specs_data import SPECS                    # noqa: E402

st.set_page_config(page_title="Bilrådgivaren", page_icon="🚗", layout="wide")

SEVERITY = {"high": "🔴 Hög", "medium": "🟠 Medel", "low": "🟡 Låg"}
CONFIDENCE = {"high": "hög", "medium": "medel", "low": "låg"}
SELLER = {"private": "Privatperson", "dealer": "Handlare", None: "Okänd säljare"}
DRIVE = {"FWD": "Framhjulsdrift", "RWD": "Bakhjulsdrift", "AWD": "Fyrhjulsdrift"}


def sek(v) -> str:
    return "–" if v is None else f"{int(round(v)):,} kr".replace(",", " ")


def theme() -> str:
    try:
        return st.context.theme.type or "light"
    except Exception:
        return "light"


@st.cache_resource(show_spinner="Läser marknaden och anpassar värderingsmodellen …")
def get_market(db_path: str, version: str) -> service.Market:  # version busts the cache
    return service.load_market(db_path)


def market_version(db_path: Path) -> str:
    if not db_path.exists():
        return f"demo:{date.today()}"
    conn = db.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*), COALESCE(MAX(run_id), 0) FROM etl_runs").fetchone()
        return f"{row[0]}:{row[1]}"
    except Exception:
        return "new"
    finally:
        conn.close()


db_path = Path(os.environ.get("CAR_DEALS_DB", db.DEFAULT_DB_PATH))
market = get_market(str(db_path), market_version(db_path))
listings = market.listings

# --------------------------------------------------------------------- header
st.title("🚗 Bilrådgivaren")
st.caption("Hitta rätt begagnad bil på Blocket för **dig**, inte bara den billigaste. "
           "Rankning efter fynd, pålitlighet, driftkostnad och budgetmarginal.")
if market.demo:
    st.warning("**DEMO:** syntetisk exempeldata, inte riktiga annonser. Hämta riktig data med "
               "`python -m pipeline.run --source blocket --query \"volvo v60\"`.", icon="⚠️")
else:
    st.success(f"Riktig Blocket-data · {market.label}", icon="✅")

# -------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Din profil")
    budget = st.number_input("Max pris (kr)", 20_000, 2_000_000, 220_000, step=10_000)
    min_year = st.slider("Årsmodell från", 2000, date.today().year, 2015)
    max_mil = st.number_input("Max miltal (mil, 0 = ingen gräns)", 0, 60_000, 0, step=1_000)
    bodies = sorted({s["body_type"] for s in SPECS if s.get("body_type")}
                    | {r["body_type"] for r in listings if r.get("body_type")})
    body_types = st.multiselect("Kaross", bodies, placeholder="Alla karosser")
    drivetrains = st.multiselect("Drivning", list(DRIVE), format_func=DRIVE.get,
                                 placeholder="Alla drivlinor")
    fuels = st.multiselect("Bränsle", ["Bensin", "Diesel", "Hybrid", "Laddhybrid", "El"],
                           placeholder="Alla bränslen")
    max_l = st.slider("Max förbrukning (L/100 km, 0 = ingen gräns)", 0.0, 12.0, 0.0, 0.1)
    max_ins = st.number_input("Max försäkring (kr/mån, 0 = ingen gräns)", 0, 5_000, 0, step=50)
    seller = st.radio("Säljare", ["Alla", "Privatperson", "Handlare"], horizontal=True)
    include_damaged = st.checkbox("Visa annonser som nämner fel/skada", False)
    annual_mil = st.slider("Körsträcka per år (mil)", 300, 4_000, 1_500, step=100)
    with st.expander("Försäkringsfaktorer"):
        driver_age = st.number_input("Förarens ålder", 18, 99, 35)
        claims_free = st.number_input("Skadefria år (bonus)", 0, 30, 5)
        home_city = st.text_input("Hemort", "")
    top_n = st.slider("Antal förslag", 3, 20, 6)

profile = BuyerProfile(
    budget_max=int(budget), min_year=int(min_year), max_mileage=int(max_mil) * 10 or None,
    body_types=set(body_types) or None, drivetrains=set(drivetrains) or None,
    fuel_types=set(fuels) or None, max_l_per_100km=max_l or None,
    max_insurance_monthly=int(max_ins) or None,
    seller_types={"Privatperson": {"private"}, "Handlare": {"dealer"}}.get(seller),
    include_damaged=include_damaged, annual_km=int(annual_mil) * 10,
    driver_age=int(driver_age), claims_free_years=int(claims_free), home_city=home_city or None)

tab_match, tab_market, tab_value, tab_about = st.tabs(
    ["Toppmatchningar", "Marknaden", "Värdera en bil", "Om datan"])

# ---------------------------------------------------------------- top matches
with tab_match:
    all_results = service.recommend(market, profile, top_n=None)
    results = all_results[:top_n]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Annonser i urvalet", f"{len(listings):,}".replace(",", " "))
    k2.metric("Matchar din profil", f"{len(all_results):,}".replace(",", " "))
    k3.metric("Medianpris bland träffar",
              sek(pd.Series([r["price"] for r in all_results]).median()) if all_results else "–")
    k4.metric("Bästa matchning", f"{results[0]['match_score']}/100" if results else "–")

    if not results:
        st.info("Inga bilar matchade dina filter. Prova att lätta på något krav.")
    else:
        c1, c2 = st.columns(2)
        pv = charts.price_vs_value(results, theme())
        if pv is not None:
            c1.altair_chart(pv, width="stretch", theme=None)
        tc = charts.tco_breakdown(results, theme())
        if tc is not None:
            c2.altair_chart(tc, width="stretch", theme=None)
        with st.expander("Tabellvy"):
            st.dataframe(pd.DataFrame([{
                "Bil": f"{r['brand']} {r['model']} {r['year']}", "Match": r["match_score"],
                "Pris": r["price"], "Värde": r.get("market_value_sek"),
                "Rabatt %": r.get("discount_pct"), "Säkerhet": CONFIDENCE.get(r.get("value_confidence")),
                "Kostnad/år": r["tco_year"], "Försäkring/mån": r["insurance_monthly"],
                "Mil": (r["mileage"] or 0) // 10, "Säljare": SELLER.get(r.get("seller_type"))}
                for r in results]), hide_index=True, width="stretch")

        for i, r in enumerate(results, 1):
            a, brief = r["attributes"], r["briefing"]
            with st.container(border=True):
                left, right = st.columns([5, 1])
                left.subheader(f"{i}. {r['brand']} {r['model']} {r['year']}")
                if r.get("title") and not market.demo:
                    left.caption(r["title"])
                right.metric("Match", f"{r['match_score']}/100")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Pris", sek(r["price"]),
                          delta=(f"{r['discount_pct']:+.0f} % mot värde"
                                 if r.get("discount_pct") is not None else None))
                m2.metric("Marknadsvärde", sek(r.get("market_value_sek")),
                          help=(f"80 %: {sek(r.get('value_low_sek'))} – {sek(r.get('value_high_sek'))}"
                                f" · säkerhet {CONFIDENCE.get(r.get('value_confidence'), '?')}"))
                m3.metric("Kostnad per år", sek(r["tco_year"]),
                          help=f"Försäkring {r['insurance_monthly']} kr/mån, energi "
                               f"{sek(r['fuel_cost_year'])}, skatt {sek(r['tax_year'])}, "
                               f"reparationsreserv {sek(r['repair_reserve_year'])}")
                m4.metric("Miltal", f"{(r['mileage'] or 0) // 10:,} mil".replace(",", " ")
                          if r.get("mileage") is not None else "–")
                st.write(" · ".join(str(x) for x in (
                    a["body_type"], DRIVE.get(a["drivetrain"], a["drivetrain"]), a["fuel"],
                    f"{a['power_hp']} hk" if a["power_hp"] else None,
                    f"pålitlighet {a['reliability']}/5" if a["reliability"] else None,
                    SELLER.get(r.get("seller_type")), r.get("city")) if x))
                for flag in brief["red_flags"]:
                    st.error(flag, icon="🚩")
                for signal in brief["signals"]:
                    st.info(signal, icon="📉")
                if brief["issues"]:
                    with st.expander(f"Att kolla / pruta på — förhandlingsutrymme ~"
                                     f"{sek(brief['negotiation_room_sek'])}", expanded=i == 1):
                        for it in brief["issues"]:
                            st.markdown(f"**{SEVERITY.get(it['severity'], '')} · {it['issue']}**  \n"
                                        f"→ {it['what_to_check']}")
                else:
                    st.caption("✅ Inga kända typfel registrerade för denna modell/årsmodell.")
                if brief["seller_note"]:
                    st.caption("⚖️ " + brief["seller_note"])
                links = [f"[{l['label']}]({l['url']})" for l in brief["history_links"]]
                if not market.demo:
                    links.append(f"[Annonsen på Blocket]({r['url']})")
                if links:
                    st.markdown(" · ".join(links))

# --------------------------------------------------------------------- market
with tab_market:
    df = pd.DataFrame(listings)
    models = (df.groupby(["brand", "model"]).size().sort_values(ascending=False)
              .reset_index(name="n"))
    choice = st.selectbox("Modell", [f"{b} {m}" for b, m in zip(models["brand"], models["model"])])
    brand, model = models.iloc[[f"{b} {m}" for b, m in
                                zip(models["brand"], models["model"])].index(choice)][["brand", "model"]]
    sub = df[(df["brand"] == brand) & (df["model"] == model)]
    summary = next((s for s in market.valuer.summaries() if s["level"] == "model"
                    and s["brand"] == brand and s["model"] == model), None)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Aktiva annonser", len(sub))
    k2.metric("Medianpris", sek(sub["price"].median()))
    if summary:
        k3.metric("Värdeminskning per år", f"{summary['depreciation_pct_per_year']:.1f} %",
                  help="Typisk bil, år 3 → 4, 1 500 mil/år")
        k4.metric("Prisspridning", f"±{summary['residual_sd_pct']:.0f} %",
                  help="Hur mycket liknande bilar varierar i pris (1 standardavvikelse)")
    this_year = date.today().year
    scatter = pd.DataFrame({"ålder": this_year - sub["year"], "pris": sub["price"],
                            "årsmodell": sub["year"], "mil": sub["mileage"].fillna(0) // 10,
                            "säljare": sub["seller_type"].map(SELLER).fillna("Okänd")})
    st.altair_chart(charts.depreciation(scatter, service.model_curve(market, brand, model), theme(),
                                        title=f"{brand} {model}: pris mot ålder"),
                    width="stretch", theme=None)

    st.subheader("Marknadsöversikt per modell")
    overview = (df.assign(handlare=df["seller_type"].eq("dealer"))
                .groupby(["brand", "model"])
                .agg(annonser=("price", "size"), medianpris=("price", "median"),
                     snittrabatt=("discount_pct", "mean"), handlarandel=("handlare", "mean"))
                .reset_index().sort_values("annonser", ascending=False))
    overview["handlarandel"] = (overview["handlarandel"] * 100).round(0)
    overview["snittrabatt"] = overview["snittrabatt"].round(1)
    st.dataframe(overview.rename(columns={"brand": "Märke", "model": "Modell",
                                          "annonser": "Annonser", "medianpris": "Medianpris (kr)",
                                          "snittrabatt": "Snittrabatt %",
                                          "handlarandel": "Handlare %"}),
                 hide_index=True, width="stretch")

    st.subheader("Trovärdiga fynd")
    st.caption("Aktiva annonser minst 5 % under marknadsvärdet, med medel/hög värderingssäkerhet "
               "och utan skadeord i annonsen. Sorterade på hur ovanligt lågt priset är för modellen.")
    deals = df[(df["discount_pct"] >= 5) & df["value_confidence"].isin(["high", "medium"])
               & ~df.get("damage_flag", pd.Series(0, index=df.index)).fillna(0).astype(bool)]
    st.dataframe(deals.sort_values("deal_z", ascending=False).head(25)[
        ["brand", "model", "year", "price", "market_value_sek", "discount_pct", "deal_z", "city"]]
        .rename(columns={"brand": "Märke", "model": "Modell", "year": "År", "price": "Pris",
                         "market_value_sek": "Värde", "discount_pct": "Rabatt %",
                         "deal_z": "Ovanlighet (z)", "city": "Ort"}),
        hide_index=True, width="stretch")

# ----------------------------------------------------------------- valuation
with tab_value:
    st.subheader("Vad är bilen värd?")
    st.caption("Värdera vilken bil som helst mot jämförbara annonser: samma modell, ålder, "
               "miltal i förhållande till åldern och utrustning.")
    brands = sorted(df["brand"].unique())
    c1, c2, c3 = st.columns(3)
    v_brand = c1.selectbox("Märke", brands, index=0)
    v_model = c2.selectbox("Modell", sorted(df[df["brand"] == v_brand]["model"].unique()))
    v_year = c3.number_input("Årsmodell", 1990, this_year + 1, 2016)
    c4, c5, c6 = st.columns(3)
    v_mil = c4.number_input("Miltal (mil)", 0, 80_000, 12_000, step=500)
    v_price = c5.number_input("Begärt pris (kr, valfritt)", 0, 5_000_000, 0, step=5_000)
    v_seller = c6.selectbox("Säljare", ["Okänd", "Privatperson", "Handlare"])
    car = {"brand": v_brand, "model": v_model, "year": int(v_year), "mileage": int(v_mil) * 10,
           "price": int(v_price) or None,
           "seller_type": {"Privatperson": "private", "Handlare": "dealer"}.get(v_seller)}
    val = service.valuate(market, car)
    if val:
        m1, m2, m3 = st.columns(3)
        m1.metric("Marknadsvärde", sek(val["value"]))
        m2.metric("Intervall (80 %)", f"{val['low'] / 1000:.0f}–{val['high'] / 1000:.0f} tkr")
        m3.metric("Rabatt mot värdet", f"{val['discount_pct']:+.1f} %"
                  if val.get("discount_pct") is not None else "–")
        st.caption(f"Säkerhet: **{CONFIDENCE[val['confidence']]}** · baserat på {val['n']} "
                   f"jämförbara annonser ({val['cohort_n']} av samma årsmodell)"
                   + (" · ⚠️ utanför det datat täcker, tolka försiktigt" if val["extrapolated"] else ""))
        sub = df[(df["brand"] == v_brand) & (df["model"] == v_model)]
        scatter = pd.DataFrame({"ålder": this_year - sub["year"], "pris": sub["price"],
                                "årsmodell": sub["year"], "mil": sub["mileage"].fillna(0) // 10,
                                "säljare": sub["seller_type"].map(SELLER).fillna("Okänd")})
        highlight = ({"ålder": this_year - int(v_year), "pris": int(v_price)} if v_price else None)
        st.altair_chart(charts.depreciation(scatter, service.model_curve(market, v_brand, v_model),
                                            theme(), highlight=highlight,
                                            title=f"{v_brand} {v_model}: jämförbara annonser"),
                        width="stretch", theme=None)
        issues = get_issues(v_brand, v_model, int(v_year))
        if issues:
            st.markdown("**Kända typfel för denna årsmodell**")
            for it in issues:
                st.markdown(f"- {SEVERITY.get(it['severity'], '')} **{it['issue']}** — "
                            f"{it['what_to_check']} (~{sek(it['negotiation_leverage_sek'])})")
    else:
        st.info("För lite marknadsdata för att värdera bilen ännu.")

# ---------------------------------------------------------------------- about
with tab_about:
    st.subheader("Om datan och metoden")
    st.markdown(f"""
- **Data:** {market.label}{' — **demo**' if market.demo else ''}.
- **Marknadsvärde:** en hierarkisk hedonisk regression över *begärda* priser. Modellen använder
  modell, ålder, miltal jämfört med det normala för åldern, handlare/privat, växellåda, AWD och
  bränsle. Varje annons värderas utan sig själv (leave-one-out). Värdet är en **uppskattning**
  med ett 80 %-intervall, inte en officiell värdering.
- **Kostnad per år:** försäkring (kalibrerad uppskattning, ingen offert) + energi + fordonsskatt
  + reparationsreserv efter pålitlighet. Alla delar är **uppskattningar**.
- **Kända fel:** kurerade, välkända typfel. Använd dem som frågor att ställa, **inte** som en
  diagnos. Gör alltid en besiktning.
- **Matchpoäng:** fynd (hur ovanligt lågt priset är, viktat med värderingens säkerhet) +
  pålitlighet + driftekonomi + budgetmarginal. Aldrig bara rabatten.
""")
    if market.db_path:
        conn = db.connect(market.db_path)
        runs = pd.read_sql_query("SELECT run_id, started_at, source, scope, listings_loaded, "
                                 "new_listings, price_changes, deactivated FROM etl_runs "
                                 "ORDER BY run_id DESC LIMIT 20", conn)
        conn.close()
        st.markdown("**Senaste körningar (data lineage)**")
        st.dataframe(runs, hide_index=True, width="stretch")
