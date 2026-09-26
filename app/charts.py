"""Altair charts for the Streamlit advisor.

Palette and mark specs follow a validated data-viz system: categorical slots are
checked for colour-vision deficiency in light and dark mode against Streamlit's
backgrounds, with thin marks, hairline solid grids and tooltips on every mark. Light
mode has a contrast warning for aqua/yellow, so charts using them also show values
as text (direct labels / table view).
"""
from __future__ import annotations

import altair as alt
import pandas as pd

PALETTES = {
    "light": {
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7", "context": "#c3c2b7",
        "band": "#cde2fb", "surface": "#ffffff", "good": "#006300", "critical": "#d03b3b",
    },
    "dark": {
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500"],
        "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835", "context": "#52514e",
        "band": "#184f95", "surface": "#0e1117", "good": "#0ca30c", "critical": "#e66767",
    },
}
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def palette(theme: str | None) -> dict:
    return PALETTES["dark" if theme == "dark" else "light"]


# Swedish number formatting in every chart: 150 000, not 150,000.
SV_LOCALE = {"number": {"decimal": ",", "thousands": "\u00a0", "grouping": [3],
                        "currency": ["", "\u00a0kr"]}}


def _style(chart: alt.Chart, p: dict) -> alt.Chart:
    return (chart.configure(font=FONT, background="transparent", locale=SV_LOCALE)
            .configure_view(stroke=None)
            .configure_axis(gridColor=p["grid"], gridWidth=1, domainColor=p["axis"],
                            tickColor=p["axis"], labelColor=p["muted"], titleColor=p["ink2"],
                            labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
            .configure_axisX(tickCount=5)
            .configure_legend(labelColor=p["ink2"], titleColor=p["ink2"], orient="top",
                              labelFontSize=12, titleFontSize=12, symbolSize=90)
            .configure_title(color=p["ink"], fontSize=14, anchor="start", fontWeight=600))


def price_vs_value(results: list[dict], theme: str | None) -> alt.Chart | None:
    """Dumbbell per car: 80 % value interval (band), market value (blue), asking price (orange)."""
    rows = [r for r in results if r.get("market_value_sek")]
    if not rows:
        return None
    p = palette(theme)
    df = pd.DataFrame([{
        "bil": f"{i}. {r['brand']} {r['model']} {r['year']}",
        "pris": r["price"], "värde": r["market_value_sek"],
        "låg": r["value_low_sek"], "hög": r["value_high_sek"],
        "rabatt": f"{r['discount_pct']:+.0f} %",
    } for i, r in enumerate(rows, 1)])
    order = list(df["bil"])
    y = alt.Y("bil:N", sort=order, title=None, axis=alt.Axis(labelLimit=220))
    x_title = "kr (band = 80 % osäkerhetsintervall för värdet)"
    base = alt.Chart(df).encode(y=y)
    band = base.mark_bar(height=14, cornerRadius=4, color=p["band"]).encode(
        x=alt.X("låg:Q", title=x_title, axis=alt.Axis(format=",.0f")), x2="hög:Q",
        tooltip=[alt.Tooltip("bil:N"), alt.Tooltip("låg:Q", format=",.0f", title="värde låg"),
                 alt.Tooltip("hög:Q", format=",.0f", title="värde hög")])
    link = base.mark_rule(strokeWidth=2, color=p["axis"]).encode(x="pris:Q", x2="värde:Q")
    long = df.melt(id_vars=["bil", "rabatt"], value_vars=["värde", "pris"],
                   var_name="mått", value_name="kr")
    long["mått"] = long["mått"].map({"värde": "Marknadsvärde", "pris": "Begärt pris"})
    dots = alt.Chart(long).mark_circle(size=110, opacity=1, stroke=p["surface"], strokeWidth=2).encode(
        y=y, x=alt.X("kr:Q"),
        color=alt.Color("mått:N", title=None,
                        scale=alt.Scale(domain=["Marknadsvärde", "Begärt pris"],
                                        range=p["series"][:2])),
        tooltip=[alt.Tooltip("bil:N"), alt.Tooltip("mått:N"), alt.Tooltip("kr:Q", format=",.0f"),
                 alt.Tooltip("rabatt:N")])
    label = base.mark_text(align="left", dx=10, color=p["ink2"], fontSize=12).encode(
        x=alt.X("hög:Q"), text="rabatt:N")
    chart = (band + link + dots + label).properties(
        height=max(120, 34 * len(df)), title="Begärt pris jämfört med marknadsvärde")
    return _style(chart, p)


TCO_PARTS = [("insurance", "Försäkring"), ("energy", "Energi"), ("tax", "Skatt"),
             ("repair", "Reparationsreserv")]


def tco_breakdown(results: list[dict], theme: str | None) -> alt.Chart | None:
    """Stacked horizontal bars: yearly cost of ownership per car, by component."""
    if not results:
        return None
    p = palette(theme)
    rows = []
    for i, r in enumerate(results, 1):
        car = f"{i}. {r['brand']} {r['model']} {r['year']}"
        parts = {"insurance": r["insurance_monthly"] * 12, "energy": r["fuel_cost_year"] or 0,
                 "tax": r["tax_year"], "repair": r["repair_reserve_year"]}
        for order, (key, label) in enumerate(TCO_PARTS):
            rows.append({"bil": car, "del": label, "kr": parts[key], "ordning": order,
                         "totalt": r["tco_year"]})
    df = pd.DataFrame(rows)
    y = alt.Y("bil:N", sort=list(dict.fromkeys(df["bil"])), title=None,
              axis=alt.Axis(labelLimit=220))
    bars = alt.Chart(df).mark_bar(height=18, stroke=p["surface"], strokeWidth=2).encode(
        y=y,
        x=alt.X("sum(kr):Q", title="kr per år", axis=alt.Axis(format=",.0f")),
        color=alt.Color("del:N", title=None,
                        scale=alt.Scale(domain=[l for _, l in TCO_PARTS], range=p["series"])),
        order=alt.Order("ordning:Q"),
        tooltip=[alt.Tooltip("bil:N"), alt.Tooltip("del:N"), alt.Tooltip("kr:Q", format=",.0f"),
                 alt.Tooltip("totalt:Q", format=",.0f", title="totalt/år")])
    totals = alt.Chart(df.drop_duplicates("bil")).mark_text(
        align="left", dx=6, color=p["ink2"], fontSize=12).encode(
        y=y, x=alt.X("totalt:Q"), text=alt.Text("totalt:Q", format=",.0f"))
    chart = (bars + totals).properties(height=max(120, 34 * len(set(df["bil"]))),
                                       title="Uppskattad kostnad per år")
    return _style(chart, p)


def depreciation(market_df: pd.DataFrame, curve: list[dict], theme: str | None,
                 highlight: dict | None = None, title: str = "") -> alt.Chart:
    """Listings of one model (gray context) with the fitted typical-value curve (accent)."""
    p = palette(theme)
    layers = []
    if not market_df.empty:
        layers.append(alt.Chart(market_df).mark_circle(
            size=64, color=p["context"], opacity=0.9, stroke=p["surface"], strokeWidth=1).encode(
            x=alt.X("ålder:Q", title="ålder (år)", scale=alt.Scale(zero=True)),
            y=alt.Y("pris:Q", title="kr", axis=alt.Axis(format=",.0f")),
            tooltip=[alt.Tooltip("årsmodell:Q"), alt.Tooltip("pris:Q", format=",.0f"),
                     alt.Tooltip("mil:Q", format=",.0f"), alt.Tooltip("säljare:N")]))
    curve_df = pd.DataFrame(curve).rename(columns={"age": "ålder", "value": "typiskt värde"})
    if "in_data" not in curve_df:
        curve_df["in_data"] = True
    curve_df["täckning"] = curve_df["in_data"].map({True: "inom datat", False: "extrapolerat"})
    line_enc = dict(
        x=alt.X("ålder:Q", title="ålder (år)"),
        y=alt.Y("typiskt värde:Q", title="kr", axis=alt.Axis(format=",.0f")),
        tooltip=[alt.Tooltip("ålder:Q"), alt.Tooltip("typiskt värde:Q", format=",.0f"),
                 alt.Tooltip("täckning:N")])
    # Extrapolated stretches are dashed (reads as "projection"); the data range is solid.
    layers.append(alt.Chart(curve_df).mark_line(strokeWidth=2, strokeDash=[5, 4], opacity=0.7,
                                                color=p["series"][0]).encode(**line_enc))
    layers.append(alt.Chart(curve_df[curve_df["in_data"]]).mark_line(
        strokeWidth=2, color=p["series"][0]).encode(**line_enc))
    inside = curve_df[curve_df["in_data"]]
    label_src = inside if not inside.empty else curve_df
    end = label_src.iloc[[len(label_src) // 2]]
    layers.append(alt.Chart(end).mark_text(align="left", dx=8, dy=-10, color=p["ink2"],
                                           fontSize=12, text="typiskt värde (1 500 mil/år)")
                  .encode(x="ålder:Q", y="typiskt värde:Q"))
    if highlight:
        hl = pd.DataFrame([highlight])
        layers.append(alt.Chart(hl).mark_point(size=160, filled=True, color=p["series"][1],
                                               stroke=p["surface"], strokeWidth=2).encode(
            x="ålder:Q", y="pris:Q",
            tooltip=[alt.Tooltip("pris:Q", format=",.0f", title="din bil")]))
        layers.append(alt.Chart(hl).mark_text(align="left", dx=10, color=p["ink2"], fontSize=12,
                                              text="din bil").encode(x="ålder:Q", y="pris:Q"))
    chart = alt.layer(*layers).properties(height=320, title=title)
    return _style(chart, p)
