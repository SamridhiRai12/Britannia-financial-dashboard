"""
Britannia Industries Limited - Executive Financial Intelligence Dashboard (v3: dark/light mode, plain-English charts)
Run:  streamlit run app.py
Data: five years of CONSOLIDATED financials (FY2021-22 .. FY2025-26), ₹ crore, from the company's annual reports.
"""
from __future__ import annotations

import html
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.data import (DATA_NOTES, EXPLORER_BS, EXPLORER_CF, EXPLORER_PL, FY, FY_LONG, LABELS, RESTATEMENT_LOG, SOURCES,
                      STATEMENT_GROUPS, run_verification)
from src.exports import build_excel, flags_csv, ratios_csv, statements_csv
from src.insights import FLAG_TESTS, build_ctx, build_flags, chart_insight, executive_insights, flag_counts
from src.ratios import CATEGORIES, PILLAR_WEIGHTS, RATIO_META, SCORE_RULES, band, fmt_value, interpret, rating_label
from src.theme import PAL, PALETTES, apply_theme, build_css, chart_head, insight_box, kpi_card, rgba, style_fig
from src.utils import arrow, cagr, cr, growth, is_nan

st.set_page_config(page_title="Britannia | Financial Intelligence", page_icon="📊", layout="wide",
                   initial_sidebar_state="collapsed")
SECTIONS = ["Overview", "Profitability", "Balance Sheet", "Cash Flow", "Ratios", "Red Flags", "Insights", "Data"]
SECTION_TITLES = {"Overview": "Executive Overview", "Profitability": "Profitability Analysis", "Balance Sheet": "Balance Sheet Analysis",
                  "Cash Flow": "Cash Flow Analysis", "Ratios": "Financial Ratio Analysis", "Red Flags": "Red Flag Analysis",
                  "Insights": "Executive Insights", "Data": "Data & Verification"}


def _bind(p: dict):
    """Expose the active palette / surface colours as module-level names (NAVY, GOLD, STRONG, ...)."""
    g = globals()
    for k in ("NAVY", "BLUE", "SKY", "GOLD", "GREEN", "RED", "AMBER", "S5", "S6", "INK", "MUTED", "GRID", "STRONG", "REF", "CONNECTOR",
              "ACCENT", "CARD"):
        g[k] = p[k]


# theme is decided from the previous interaction (widgets below write the same keys)
_dark = st.session_state.get("dark", True)
apply_theme(st.session_state.get("pref_pal", "Navy & Gold"), _dark)
PAL["HEIGHT"] = {"Compact": 0.85, "Standard": 1.0, "Tall": 1.25}[st.session_state.get("pref_size", "Standard")]
_bind(PAL)
st.markdown(build_css(_dark), unsafe_allow_html=True)


# ======================================================================================
# Streamlit-version compatibility helpers
# ======================================================================================
def html_block(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


HEAD_DONE: set = set()


def head(key: str, title: str | None = None, how: str | None = None):
    """Render the plain-English chart header once per chart."""
    if key in HEAD_DONE:
        return
    t, h = HOWTO.get(key, (title, how))[:2] if key in HOWTO else (title, how)
    title, how = title or t, how or h
    if title and how:
        html_block(chart_head(title, how))
        HEAD_DONE.add(key)


def show(fig, key: str, title: str | None = None, how: str | None = None, unit: str | None = None):
    head(key, title, how)
    if key in HEAD_DONE:                       # header carries the title -> remove duplicate title inside the figure
        fig.update_layout(title=None, margin=dict(t=20))
    unit = unit or (HOWTO[key][2] if key in HOWTO and len(HOWTO[key]) > 2 else None)
    if unit:
        fig.update_layout(yaxis_title_text=unit)
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except Exception:
        st.plotly_chart(fig, use_container_width=True, key=key)


_NUM = re.compile(r"^[\-\+₹\(]*[\d,]+(\.\d+)?[%x\)]*( bps| cr| days)?$")


def _cell(v) -> str:
    if isinstance(v, float):
        return "–" if v != v else f"{v:,.2f}"
    return str(v)


def table(frame: pd.DataFrame, height: int | None = None):
    """Theme-aware HTML table (works identically in dark and light mode)."""
    cols = list(frame.columns)
    out = ['<div class="tbl-wrap"' + (f' style="max-height:{height}px"' if height else "") + '><table class="rt"><tr>'
           + "".join(f"<th>{html.escape(str(c_))}</th>" for c_ in cols) + "</tr>"]
    for row in frame.itertuples(index=False):
        tds = []
        for v in row:
            t = _cell(v)
            tds.append(f'<td class="{"num" if _NUM.match(t) else ""}">{html.escape(t)}</td>')
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</table></div>")
    html_block("".join(out))


def popover(label: str):
    return st.popover(label) if hasattr(st, "popover") else st.expander(label)


def sec(title: str, sub: str = ""):
    html_block(f'<div class="sec-title">{html.escape(title)}</div>' + (f'<div class="sec-sub">{html.escape(sub)}</div>' if sub else ""))


def insight(key: str, c, years, focus=None, metric=None, title="What this means"):
    html_block(insight_box(chart_insight(key, c, years, focus=focus, metric=metric), title))


def pick(key: str, options: list[str], default: int = 0) -> str:
    """Small per-chart view switch (rendered as pills)."""
    head(key)
    return st.radio("Chart view", options, index=default, horizontal=True, key=f"view_{key}", label_visibility="collapsed")


# ======================================================================================
# Plain-English layer: chart explanations, glossary, section intros, KPI hints
# ======================================================================================
HOWTO = {
    "ov_wf": ("From revenue to net profit", "Start at the left with total revenue. Red bars are costs taken away, green bars are income added, and the dark bars are running subtotals (EBITDA, EBIT, PBT and finally PAT = net profit).", None),
    "ov_gauge": ("Financial health score", "One 0–100 score built from profitability, liquidity, solvency, efficiency and cash flow. The marker shows the score: the green zone (65+) is strong, the red zone (below 35) is stressed.", None),
    "ov_pillars": ("Score by area", "Each bar is one area of financial health scored 0–100. Longer and greener is better; amber or red bars show where to look first.", None),
    "ov_health": ("Health score over time", "Each line is one area of financial health; the thick gold line is the overall score. Rising lines mean improvement.", "Score (0–100)"),
    "pf_rev": ("Revenue and operating margin", "The shapes show revenue in ₹ crore (left scale). The gold line shows EBITDA margin: the share of each rupee of sales left after operating costs (right scale). Tags mark the best and weakest margin years.", "Revenue (₹ crore)"),
    "pf_profit": ("Profit at each stage", "Each year shows four levels: EBITDA (operating profit before depreciation), EBIT (after depreciation), PBT (before tax) and PAT (net profit). The gaps are what depreciation, interest and tax take away.", "₹ crore"),
    "pf_margins": ("Margins: how much of each ₹100 of sales is kept", "Each line shows the profit kept at one stage as a % of revenue. Falling lines mean costs are growing faster than sales; the gap between gross and EBITDA margin is overhead cost.", "% of revenue"),
    "pf_cost": ("Where each ₹100 of revenue goes", "Each column adds up to 100. The coloured blocks show how much goes to materials, employees and other expenses; the gold block is the operating profit (EBITDA) that remains.", "% of revenue"),
    "pf_quality": ("How profit before tax is built", "Bars above zero add to profit (operating profit, other income); bars below zero reduce it (interest cost, associate losses). The line is the resulting profit before tax (PBT).", "₹ crore"),
    "bs_assets": ("What the company owns", "Each column is total assets split by type: factories, investments, stock, customer dues, cash and others. Switch to '100% mix' to compare shares instead of amounts.", "₹ crore"),
    "bs_funding": ("Who funds the company", "Each column splits the same total into owners' money (equity) and money owed to others (borrowings, suppliers, other). A bigger equity block means a safer balance sheet.", "₹ crore"),
    "bs_debt": ("Borrowings and net debt", "Blocks show long-term and short-term borrowings. The red line is net debt: borrowings minus cash and investments. Below zero means the company holds more cash than it owes.", "₹ crore"),
    "bs_liq": ("Can it pay its short-term bills?", "Bars compare short-term assets with short-term liabilities (left scale). Lines show the current, quick and cash ratios (right scale): above 1.0x means assets cover the bills.", "₹ crore"),
    "bs_treasury": ("Cash & investments versus borrowings", "Blocks are the cash and investments the company holds; the red line is what it owes in borrowings. Blocks taller than the line mean treasury exceeds debt.", "₹ crore"),
    "bs_wc": ("Money tied up in day-to-day operations", "Bars above zero (stock, customer dues) need cash; gold bars below zero are supplier credit that provides cash. The line is the net result: below zero means suppliers fund operations.", "₹ crore"),
    "cf_bars": ("Where cash came from and went", "Operating = cash from running the business; Investing = spending on assets and investments; Financing = loans, interest and dividends. Above zero brings cash in; below zero sends cash out.", "₹ crore"),
    "cf_fcf": ("Free cash flow", "Free cash flow = operating cash flow minus capital expenditure: the cash left for shareholders and debt reduction. The dotted line (right scale) shows it as a % of revenue.", "₹ crore"),
    "cf_conv": ("Do profits turn into cash?", "Lines near or above 100% mean reported profit is backed by real cash. Sustained values well below 100% are a warning sign.", "% conversion"),
    "cf_wf": ("How the focus year's cash was used", "Start with operating cash flow; red bars are cash paid out on capex, interest and dividends; the final dark bar is what is left (or the shortfall).", None),
    "cf_cum": ("Total cash sources and uses", "Adds up the whole selected period: cash generated from operations, less capex, interest and dividends. The last bar is the leftover or shortfall.", None),
    "cf_capex": ("Investing in the business vs wear and tear", "Bars compare capital spending with depreciation (the yearly wear on assets). The gold line (right) is capex ÷ depreciation: below 1.0x means assets wear out faster than they are replaced.", "₹ crore"),
    "rx_dupont": ("What drives return on equity (DuPont)", "ROE (gold line) = profit margin × how hard assets work (asset turnover) × leverage (equity multiplier). The lines show which of the three is moving ROE.", "% (ROE, net margin)"),
    "rx_days": ("Working-capital cycle in days", "Bars above zero are days cash is tied up (stock, customer dues); bars below zero are days of supplier credit. The red line is the net cycle: negative means suppliers fund the business.", "Days"),
    "rx_radar": ("Scorecard shape: then versus now", "Each corner is one area of financial health (0–100; farther from the centre is better). Compare the first year (light) with the focus year (gold).", None),
    "rf_heat": ("Red-flag heat map", "Rows are tests, columns are years. Green = healthy, amber = watch, red = risk. Hover over a cell to see the measured value.", None),
    "rf_margin": ("Margin change versus last year", "Bars below zero mean the margin shrank compared with the previous year (in basis points: 100 bps = 1 percentage point).", "Change (bps)"),
    "rf_refi": ("Short-term debt versus cash cover", "If the navy bar (liquid treasury) is taller than the gold bar (current borrowings), short-term debt is covered by cash. The red line (right) is the share of debt that is short-term.", "₹ crore"),
    "rf_rec": ("Customer dues versus sales growth", "If the gold bar is much taller than the navy bar, customers' unpaid dues are growing faster than sales: a possible sign of loosening credit.", "% growth"),
    "rf_cash": ("Profit versus cash versus payouts", "Compare reported profit (PAT) with the cash generated, the cash left after capex, and dividends paid. Dividends above free cash flow must be funded from savings or borrowing.", "₹ crore"),
    "in_health": ("Health score by area", "Each series is one area of financial health scored 0–100; the gold line is the overall score.", "Score (0–100)"),
}

GLOSSARY = {
    "Crore": "Indian unit: 1 crore = 10 million (₹ 1 crore = ₹10,000,000).",
    "Revenue": "Money earned from selling products, before any costs.",
    "Gross margin": "What is left of each ₹100 of sales after the direct cost of materials.",
    "EBITDA": "Operating profit before depreciation, interest, other income and tax: the core profit from running the business.",
    "EBIT": "EBITDA minus depreciation (the yearly wear on factories and machines).",
    "PBT": "Profit before tax: after all costs and interest, before income tax.",
    "PAT": "Profit after tax: the 'bottom line' that belongs to shareholders.",
    "Margin": "Profit as a percentage of revenue, e.g. an 18% EBITDA margin keeps ₹18 of operating profit per ₹100 of sales.",
    "Operating cash flow": "Cash the business actually generates after tax and working-capital movements.",
    "Capex": "Capital expenditure: cash spent on factories, machinery and other long-life assets.",
    "Free cash flow": "Operating cash flow minus capex: cash left for dividends and debt repayment.",
    "Depreciation": "The cost of asset wear and tear spread over the years; it reduces profit but is not a cash payment.",
    "Borrowings (debt)": "Money borrowed from banks and lenders (lease liabilities are shown separately).",
    "Net debt": "Borrowings minus cash and liquid investments. A negative number means net cash.",
    "Working capital": "Short-term assets minus short-term liabilities; the cash needed for day-to-day operations.",
    "Current ratio": "Short-term assets ÷ short-term liabilities. Above 1.0x means short-term bills are covered.",
    "Quick ratio": "Like the current ratio but excluding stock, which is slower to turn into cash.",
    "ROE": "Return on equity: profit earned per ₹100 of shareholders' money.",
    "ROCE": "Return on capital employed: pre-tax profit per ₹100 of long-term capital (equity + debt).",
    "Interest cover": "How many times operating profit covers interest costs. Higher means safer.",
    "Payout ratio": "Share of profit paid to shareholders as dividends.",
    "Cash conversion cycle": "Days between paying suppliers and collecting from customers. Negative means suppliers fund the business.",
    "bps": "Basis points: 100 bps = 1 percentage point.",
}

INTROS = {
    "Overview": "<b>Start here.</b> The cards compare the latest year with the year before: green means better, red means worse (for debt, lower is better). The waterfall shows how each rupee of revenue turns into profit, and the gauge condenses overall financial health into one number. Hover over any card for its definition.",
    "Profitability": "<b>This page answers:</b> is Britannia growing, and is it keeping more or less profit from each rupee of sales? Use the view buttons above a chart to switch between bars, lines and area, and the chart builder at the bottom to compare any metrics you like.",
    "Balance Sheet": "<b>This page shows</b> what Britannia owns, who funds it, how much it owes, and whether it can pay its short-term bills. A strong picture has more equity than debt and cash and investments larger than borrowings.",
    "Cash Flow": "<b>Profit on paper is not cash in the bank.</b> This page shows the cash the business really generates, what it spends, and what is left after paying dividends.",
    "Ratios": "<b>Ratios turn raw numbers into comparable health checks.</b> Each row gives the formula, the values over time, whether the trend is improving, and a plain-English reading. Tabs group ratios by what they measure.",
    "Red Flags": "<b>This page runs automatic tests</b> for common warning signs: falling margins, rising debt, weak cash flow and more. Green is fine, amber means keep an eye on it, red needs attention.",
    "Insights": "<b>A summary for senior management:</b> what is going well, what to watch, and the questions worth asking the finance team.",
}

KPI_HINTS = {
    "Revenue": "Total money earned from selling products, before any costs.",
    "EBITDA": "Operating profit before depreciation, interest, other income and tax.",
    "EBITDA margin": "EBITDA as a percentage of revenue: operating profit kept from each ₹100 of sales.",
    "Net profit (PAT)": "Profit after all costs, interest and tax: the bottom line.",
    "PAT margin": "Net profit as a percentage of revenue.",
    "Total assets": "Everything the company owns: factories, investments, stock, cash and customer dues.",
    "Debt (borrowings)": "Money borrowed from banks and lenders (excluding lease liabilities). Lower is generally safer.",
    "Free cash flow": "Operating cash flow minus capital spending: what is left for shareholders and debt repayment.",
}


def intro(section_name: str):
    html_block(f'<div class="intro">{INTROS[section_name]}</div>')


def glossary(terms: list[str]):
    with st.expander("📖 Plain-English glossary for this page"):
        html_block('<dl class="gl">' + "".join(f"<dt>{html.escape(t)}</dt><dd>{html.escape(GLOSSARY[t])}</dd>" for t in terms) + "</dl>")


def mark_extremes(fig, xs, ys, fmt, yref="y"):
    """Tag the best and weakest points on a line so the reader sees the story at a glance."""
    ys = [float(v) for v in ys]
    if len(ys) < 3:
        return
    hi, lo = ys.index(max(ys)), ys.index(min(ys))
    if hi == lo:
        return
    for i, name, ay in ((hi, "Peak", -34), (lo, "Low", 34)):
        fig.add_annotation(x=xs[i], y=ys[i], yref=yref, text=f"{name}: {fmt(ys[i])}", showarrow=True, arrowhead=2, ax=0, ay=ay,
                           font=dict(size=11, color=STRONG), bgcolor=CARD, bordercolor=ACCENT, borderwidth=1, arrowcolor=ACCENT)


# ======================================================================================
# Data (cached)
# ======================================================================================
@st.cache_data(show_spinner=False)
def load_all():
    c = build_ctx()
    return c, build_flags(c), run_verification()


@st.cache_data(show_spinner=False)
def excel_bytes(years: tuple) -> bytes:
    c, flags, _ = load_all()
    return build_excel(c.d, c.r, flags["detail"], list(years))


c, flags, verification = load_all()
D, R = c.d, c.r

# ======================================================================================
# TOP BAR  (company header -> navigation -> filters / preferences / export)
# ======================================================================================
hero_slot = st.empty()
section = st.radio("Section", SECTIONS, horizontal=True, label_visibility="collapsed", key="nav")

k1, k2, k3, k4, k5 = st.columns([3.2, 1.6, 0.9, 0.9, 1.1])
with k1:
    y_from, y_to = st.select_slider("Financial year range", options=FY, value=(FY[0], FY[-1]),
                                    help="Filters every chart, table, insight and export.")
i0, i1 = FY.index(y_from), FY.index(y_to)
if i0 == i1:
    i0, i1 = (i0 - 1, i1) if i0 > 0 else (i0, i1 + 1)
years = FY[i0:i1 + 1]
with k2:
    focus = st.selectbox("Focus year (KPIs, waterfalls)", years, index=len(years) - 1, format_func=lambda y: f"{y}  ({FY_LONG[y]})")
with k3:
    st.write("")
    with popover("🎨 Display"):
        st.selectbox("Colour palette", list(PALETTES.keys()), index=0, key="pref_pal")
        st.toggle("Show data labels on charts", value=True, key="pref_labels")
        st.select_slider("Chart size", options=["Compact", "Standard", "Tall"], value="Standard", key="pref_size")
        st.caption("Each chart also has its own view switch (bars / lines / area / 100% mix), and every analysis page has a chart builder.")
with k4:
    st.write("")
    with popover("⬇ Export"):
        st.download_button("Excel workbook (.xlsx)", data=excel_bytes(tuple(years)),
                           file_name=f"Britannia_Financial_Report_{years[0]}_{years[-1]}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx")
        st.download_button("Financial statements (.csv)", data=statements_csv(D, years),
                           file_name=f"Britannia_Statements_{years[0]}_{years[-1]}.csv", mime="text/csv", key="dl_csv_fs")
        st.download_button("Ratios (.csv)", data=ratios_csv(R, years),
                           file_name=f"Britannia_Ratios_{years[0]}_{years[-1]}.csv", mime="text/csv", key="dl_csv_ratio")
        st.download_button("Red flags (.csv)", data=flags_csv(flags["detail"], years),
                           file_name=f"Britannia_RedFlags_{years[0]}_{years[-1]}.csv", mime="text/csv", key="dl_csv_flags")
with k5:
    st.write("")
    st.toggle("🌙 Dark mode", value=True, key="dark", help="Switch between Dark and Light mode.")

# ---- company snapshot in the header (filled now that focus year is known) -------------
_p = c.prev(focus)


def _snap(label, value, delta, up=None):
    cls = "fl" if up is None else ("up" if up else "dn")
    return f'<div class="s"><div class="l">{html.escape(label)}</div><div class="v">{html.escape(value)}</div><div class="d {cls}">{html.escape(delta)}</div></div>'


_nd = c.v("net_debt", focus)
_score = float(c.sc.loc[focus, "Overall"])
_fl = flag_counts(flags, focus)
_snaps = "".join([
    _snap("Revenue", cr(c.v("revenue", focus)), f"{arrow(c.g('revenue', focus))} {c.g('revenue', focus):+.1f}% YoY", c.g("revenue", focus) > 0),
    _snap("EBITDA margin", f"{c.margin('ebitda', focus):.1f}%", f"{(c.margin('ebitda', focus) - c.margin('ebitda', _p)) * 100:+,.0f} bps YoY",
          c.margin("ebitda", focus) >= c.margin("ebitda", _p)),
    _snap("Net profit", cr(c.v("pat", focus)), f"{arrow(c.g('pat', focus))} {c.g('pat', focus):+.1f}% YoY", c.g("pat", focus) > 0),
    _snap("Net debt / (cash)", cr(_nd), "Net cash" if _nd < 0 else "Net debt", _nd < 0),
    _snap("Free cash flow", cr(c.v("fcf", focus)), f"{c.r.loc[focus, 'fcf_margin']:.1f}% of revenue", c.v("fcf", focus) > 0),
    _snap("Health score", f"{_score:.0f} / 100", rating_label(_score)[0], _score >= 65),
    _snap("Red flags", f"{_fl['Risk']} risk · {_fl['Watch']} watch", f"of {sum(_fl.values())} tests", _fl["Risk"] == 0),
])
hero_slot.markdown(
    f"""<div class="hero"><h1>Britannia Industries Limited</h1>
<div class="sub">Executive financial intelligence · consolidated · ₹ crore · source: annual reports FY2021-22 to FY2025-26</div>
<span class="chip">{FY_LONG[years[0]]} → {FY_LONG[years[-1]]}</span><span class="chip">Focus: {FY_LONG[focus]}</span>
<span class="chip">{int((verification.Result == 'PASS').sum())}/{len(verification)} data checks passed</span>
<div class="snap">{_snaps}</div></div>""", unsafe_allow_html=True)

# ======================================================================================
# Plotly drawing helpers (palette / labels / chart-type aware)
# ======================================================================================
_HT = {"cr": "₹%{y:,.0f} cr", "cr1": "₹%{y:,.1f} cr", "pct": "%{y:.1f}%", "x": "%{y:.2f}x", "days": "%{y:.0f} days",
       "num": "%{y:,.2f}", "bps": "%{y:+,.0f} bps"}
_TT = {"cr": "%{y:,.0f}", "cr1": "%{y:,.1f}", "pct": "%{y:.1f}%", "x": "%{y:.2f}x", "days": "%{y:.0f}", "num": "%{y:,.2f}", "bps": "%{y:+,.0f}"}
STACKED = ("Stacked bars", "Stacked area", "100% mix")


def _add(fig, tr, secondary):
    if secondary is None:
        fig.add_trace(tr)
    else:
        fig.add_trace(tr, secondary_y=secondary)


def Bar(name, x, y, color, fmt="cr", **kw):
    tr = go.Bar(name=name, x=x, y=list(y), marker_color=color, hovertemplate=_HT[fmt] + "<extra></extra>", **kw)
    if st.session_state.get("pref_labels") and "text" not in kw:
        tr.update(texttemplate=_TT[fmt], textposition="auto", cliponaxis=False)
    return tr


def Line(name, x, y, color, fmt="pct", dash=None, **kw):
    lab = bool(st.session_state.get("pref_labels"))
    tr = go.Scatter(name=name, x=x, y=list(y), mode="lines+markers+text" if lab else "lines+markers",
                    line=dict(color=color, width=2.6, dash=dash), marker=dict(size=7),
                    hovertemplate=_HT[fmt] + "<extra></extra>", **kw)
    if lab:
        tr.update(texttemplate=_TT[fmt], textposition="top center")
    return tr


def draw(fig, kind: str, name, x, y, color, fmt="cr", secondary=None):
    """Add one series as bars / line / area according to the user's per-chart view choice."""
    lab = bool(st.session_state.get("pref_labels"))
    y = list(y)
    ht = _HT[fmt] + "<extra></extra>"
    if kind in ("Bars", "Stacked bars", "100% mix", "Grouped bars"):
        tr = go.Bar(name=name, x=x, y=y, marker_color=color, hovertemplate=ht)
        if lab:
            tr.update(texttemplate=_TT[fmt], textposition="auto", cliponaxis=False)
    elif kind == "Lines":
        tr = go.Scatter(name=name, x=x, y=y, mode="lines+markers+text" if lab else "lines+markers", line=dict(color=color, width=2.6),
                        marker=dict(size=7), hovertemplate=ht)
        if lab:
            tr.update(texttemplate=_TT[fmt], textposition="top center")
    else:  # "Area" / "Stacked area"
        stacked = kind == "Stacked area"
        first = not any(getattr(t, "stackgroup", None) == "one" for t in fig.data) if stacked else True
        tr = go.Scatter(name=name, x=x, y=y, mode="lines+markers" if not stacked else "lines", line=dict(color=color, width=2),
                        fill="tozeroy" if first else "tonexty", fillcolor=rgba(color, 0.55 if stacked else 0.22), hovertemplate=ht,
                        stackgroup="one" if stacked else None)
        if lab and not stacked:
            tr.update(mode="lines+markers+text", texttemplate=_TT[fmt], textposition="top center")
    _add(fig, tr, secondary)


def finish(fig, kind: str, relative: bool = False):
    if kind in ("Stacked bars", "100% mix"):
        fig.update_layout(barmode="relative" if relative else "stack")
    else:
        fig.update_layout(barmode="group")
    if kind == "100% mix":
        fig.update_yaxes(range=[0, 100])


def dual():
    return make_subplots(specs=[[{"secondary_y": True}]])


def waterfall(labels, values, measures, title, key, height=430):
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measures, text=[f"{v:,.0f}" for v in values], textposition="outside", textfont=dict(color=INK),
        connector=dict(line=dict(color=CONNECTOR, width=1)),
        increasing=dict(marker=dict(color=GREEN)), decreasing=dict(marker=dict(color=RED)),
        totals=dict(marker=dict(color=NAVY)), hovertemplate="%{x}: ₹%{y:,.1f} cr<extra></extra>"))
    style_fig(fig, title, height, legend=False, hover="closest", xaxis_title=None)
    show(fig, key, title=title)


# ---- Chart studio: user-built multi-metric chart -----------------------------------------
VIEWS = ["Value (₹ cr)", "YoY growth %", "Indexed (first year = 100)", "% of revenue"]
STUDIO_KINDS = ["Grouped bars", "Stacked bars", "Lines", "Area"]


def studio(options: list[str], defaults: list[str], key: str, title: str):
    sec(title, "Build your own chart: pick metrics, a chart type and how values are shown.")
    a, b, d_ = st.columns([3.2, 1.6, 1.6])
    with a:
        sel = st.multiselect("Metrics (choose one or more)", options, default=defaults, format_func=lambda k: LABELS[k], key=f"{key}_m")
    with b:
        view = st.selectbox("Show as", VIEWS, key=f"{key}_v")
    with d_:
        kind = st.selectbox("Chart type", STUDIO_KINDS, key=f"{key}_k")
    if not sel:
        st.info("Select at least one metric above.")
        return
    fig = go.Figure()
    fmt = {"Value (₹ cr)": "cr1", "YoY growth %": "pct", "Indexed (first year = 100)": "num", "% of revenue": "pct"}[view]
    notes = []
    for i, col in enumerate(sel):
        s = D.loc[years, col]
        if view == VIEWS[0]:
            ys = list(s)
        elif view == VIEWS[1]:
            ys = [c.g(col, y) for y in years]
        elif view == VIEWS[2]:
            base = float(s.iloc[0])
            ys = [float(v) / base * 100 if base > 0 else float("nan") for v in s]
        else:
            ys = list(s / D.loc[years, "revenue"] * 100)
        draw(fig, "Bars" if kind == "Grouped bars" else kind, LABELS[col], years, ys, list(SERIES_COLORS())[i % 8], fmt)
        k_ = cagr(float(s.iloc[0]), float(s.iloc[-1]), len(years) - 1)
        notes.append(f"{LABELS[col]}: {s.iloc[0]:,.1f} → {s.iloc[-1]:,.1f}" + (f" ({k_:.1f}% CAGR)" if not is_nan(k_) else ""))
    finish(fig, kind, relative=True)
    if view == VIEWS[2]:
        fig.add_hline(y=100, line_dash="dash", line_color=REF, annotation_text="base = 100", annotation_position="top left")
    ttl = f"{view}: {', '.join(LABELS[k] for k in sel[:3])}{'…' if len(sel) > 3 else ''}"
    unit = {"Value (₹ cr)": "₹ crore", "YoY growth %": "% change vs previous year", "Indexed (first year = 100)": "Index (first year = 100)",
            "% of revenue": "% of revenue"}[view]
    style_fig(fig, ttl, 420)
    show(fig, f"{key}_chart", title=ttl, unit=unit,
         how="Each bar or line is one metric across the years. Use 'Show as' to compare growth rates, indexed performance (first year = 100) or cost intensity (% of revenue).")
    html_block(insight_box("; ".join(notes) + ".", "Your chart in numbers"))


def SERIES_COLORS():
    return [NAVY, GOLD, BLUE, SKY, S5, S6, GREEN, AMBER]


# ======================================================================================
# 1. EXECUTIVE OVERVIEW
# ======================================================================================
def section_overview():
    sec("Executive Overview", f"Headline performance for {FY_LONG[focus]} versus {FY_LONG[c.prev(focus)]}; sparklines span {years[0]}–{years[-1]}.")
    intro("Overview")
    p = c.prev(focus)

    def card(label, col, kind="cr", inverse=False, margin_of=None):
        series = list(D.loc[years, col]) if margin_of is None else [c.margin(margin_of, y) for y in years]
        if kind == "cr":
            g = growth(c.v(col, focus), c.v(col, p))
            val, dtxt = cr(c.v(col, focus)), f"{arrow(g)} {g:+.1f}% vs {p}"
            good = (g > 0) != inverse
            k = cagr(c.v(col, years[0]), c.v(col, years[-1]), len(years) - 1)
            foot = f"CAGR {years[0]}–{years[-1]}: {k:.1f}%" if not is_nan(k) else f"{years[0]}–{years[-1]}"
        else:
            now, before = c.margin(margin_of, focus), c.margin(margin_of, p)
            val, dtxt = f"{now:.1f}%", f"{arrow(now - before)} {(now - before) * 100:+,.0f} bps vs {p}"
            good = now >= before
            foot = f"Range {min(series):.1f}%–{max(series):.1f}%"
        return kpi_card(label, val, dtxt, "good" if good else "bad", series, foot, KPI_HINTS.get(label, ""))

    row1, row2 = st.columns(4), st.columns(4)
    cards = [("Revenue", "revenue", "cr", False, None), ("EBITDA", "ebitda", "cr", False, None),
             ("EBITDA margin", "ebitda", "m", False, "ebitda"), ("Net profit (PAT)", "pat", "cr", False, None),
             ("PAT margin", "pat", "m", False, "pat"), ("Total assets", "total_assets", "cr", False, None),
             ("Debt (borrowings)", "total_debt", "cr", True, None), ("Free cash flow", "fcf", "cr", False, None)]
    for slot, (lab, col, kind, inv, mo) in zip(row1 + row2, cards):
        with slot:
            html_block(card(lab, col, kind, inv, mo))
    st.write("")

    left, right = st.columns([3, 2])
    with left:
        f = focus
        labels = ["Revenue", "Materials / COGS", "Employee cost", "Other expenses", "EBITDA", "Depreciation", "EBIT", "Other income",
                  "Finance cost", "Associates & exceptional", "PBT", "Tax", "PAT"]
        vals = [c.v("revenue", f), -c.v("cogs", f), -c.v("employee_cost", f), -c.v("other_expenses", f), c.v("ebitda", f),
                -c.v("depreciation", f), c.v("ebit", f), c.v("other_income", f), -c.v("finance_costs", f),
                c.v("share_assoc", f) - c.v("exceptional_expense", f), c.v("pbt", f), -c.v("total_tax", f), c.v("pat", f)]
        meas = ["absolute", "relative", "relative", "relative", "total", "relative", "total", "relative", "relative", "relative",
                "total", "relative", "total"]
        waterfall(labels, vals, meas, f"From revenue to PAT — {FY_LONG[f]} (₹ crore)", "ov_wf", 450)
        insight("pl_waterfall", c, years, focus=f)
    with right:
        sc = c.sc
        score = float(sc.loc[focus, "Overall"])
        lab, _ = rating_label(score)
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=score, number=dict(suffix=" / 100", font=dict(color=STRONG, size=34)),
            title=dict(text=f"Financial health score · {lab}", font=dict(size=14, color=INK)),
            gauge=dict(axis=dict(range=[0, 100], tickcolor=MUTED), bar=dict(color=ACCENT, thickness=0.28), bgcolor=PAL["GAUGE_BG"],
                       steps=[dict(range=[0, 35], color=PAL["GAUGE_STEPS"][0]), dict(range=[35, 50], color=PAL["GAUGE_STEPS"][1]),
                              dict(range=[50, 65], color=PAL["GAUGE_STEPS"][2]), dict(range=[65, 100], color=PAL["GAUGE_STEPS"][3])],
                       threshold=dict(line=dict(color=STRONG, width=3), thickness=0.8, value=score))))
        gauge.update_layout(height=int(250 * PAL["HEIGHT"]), margin=dict(l=20, r=20, t=60, b=0), paper_bgcolor=PAL["CARD"], font=dict(family="Inter, Arial", color=INK))
        show(gauge, "ov_gauge")
        pil = sc.loc[focus, ["Profitability", "Liquidity", "Solvency", "Efficiency", "Cash Flow"]]
        bar = go.Figure(go.Bar(x=pil.values, y=pil.index, orientation="h", marker_color=[GREEN if v >= 70 else (AMBER if v >= 40 else RED) for v in pil.values],
                               text=[f"{v:.0f}" for v in pil.values], textposition="outside", hovertemplate="%{y}: %{x:.0f}/100<extra></extra>"))
        style_fig(bar, "Pillar scores (0–100)", 250, legend=False, hover="closest", xaxis_title="Score (0–100)")
        bar.update_xaxes(range=[0, 110])
        bar.update_yaxes(autorange="reversed")
        show(bar, "ov_pillars")

    sec("Five-year comparison", "Selected years side by side with compound growth over the window.")
    rows = []
    for lab, col in [("Revenue", "revenue"), ("EBITDA", "ebitda"), ("PBT", "pbt"), ("PAT", "pat"), ("Total assets", "total_assets"),
                     ("Total equity", "total_equity"), ("Borrowings", "total_debt"), ("Net debt / (net cash)", "net_debt"),
                     ("Operating cash flow", "cfo"), ("Free cash flow", "fcf")]:
        k = cagr(c.v(col, years[0]), c.v(col, years[-1]), len(years) - 1)
        rows.append([lab] + [f"{c.v(col, y):,.0f}" for y in years] + [f"{k:.1f}%" if not is_nan(k) else "n/a"])
    for lab, col in [("EBITDA margin", "ebitda_margin"), ("PAT margin", "pat_margin"), ("ROCE", "roce"), ("ROE", "roe")]:
        rows.append([lab] + [f"{R.loc[y, col]:.1f}%" for y in years] + [f"{(R.loc[years[-1], col] - R.loc[years[0], col]) * 100:+,.0f} bps"])
    table(pd.DataFrame(rows, columns=["₹ crore"] + [FY_LONG[y] for y in years] + ["CAGR / change"]))

    sec("Financial health trend")
    kind = pick("ov_health", ["Lines", "Bars", "Area"])
    hs = c.sc.loc[years]
    fig = go.Figure()
    for i, pcol in enumerate(["Profitability", "Liquidity", "Solvency", "Efficiency", "Cash Flow"]):
        draw(fig, kind, pcol, years, hs[pcol], SERIES_COLORS()[(i + 2) % 8], "num")
    draw(fig, "Lines", "Overall score", years, hs["Overall"], GOLD, "num")
    fig.data[-1].line.width = 4
    finish(fig, kind)
    style_fig(fig, "Composite and pillar scores", 380)
    fig.update_yaxes(range=[0, 105])
    show(fig, "ov_health")
    insight("health_trend", c, years)
    glossary(["Crore", "Revenue", "EBITDA", "EBIT", "PBT", "PAT", "Margin", "Free cash flow", "Borrowings (debt)", "Net debt", "ROCE", "ROE"])


# ======================================================================================
# 2. PROFITABILITY
# ======================================================================================
def section_profit():
    sec("Profitability Analysis", "Revenue, profit and margin trends with the cost drivers behind them.")
    intro("Profitability")
    c1, c2 = st.columns(2)
    with c1:
        kind = pick("pf_rev", ["Bars", "Area", "Lines"])
        fig = dual()
        draw(fig, kind, "Revenue", years, D.loc[years, "revenue"], NAVY, "cr")
        fig.add_trace(Line("EBITDA margin", years, R.loc[years, "ebitda_margin"], GOLD, "pct"), secondary_y=True)
        mark_extremes(fig, years, R.loc[years, "ebitda_margin"], lambda v: f"{v:.1f}%", "y2")
        style_fig(fig, "Revenue (₹ cr) and EBITDA margin", 400)
        fig.update_yaxes(title_text="EBITDA margin (%)", secondary_y=True, showgrid=False)
        show(fig, "pf_rev")
        insight("rev_margin", c, years)
    with c2:
        kind = pick("pf_profit", ["Bars", "Lines", "Area"])
        fig = go.Figure()
        for lab, col, colr in [("EBITDA", "ebitda", NAVY), ("EBIT", "ebit", BLUE), ("PBT", "pbt", SKY), ("PAT", "pat", GOLD)]:
            draw(fig, kind, lab, years, D.loc[years, col], colr, "cr")
        finish(fig, kind)
        style_fig(fig, "Profit ladder (₹ cr)", 400)
        show(fig, "pf_profit")
        insight("profit_trend", c, years)

    c3, c4 = st.columns(2)
    with c3:
        kind = pick("pf_margins", ["Lines", "Bars", "Area"])
        fig = go.Figure()
        for lab, k, colr in [("Gross margin", "gross_margin", SKY), ("EBITDA margin", "ebitda_margin", NAVY), ("EBIT margin", "ebit_margin", BLUE),
                             ("PBT margin (pre-exceptional)", "pbt_pre_exc_margin", S6), ("PAT margin", "pat_margin", GOLD)]:
            draw(fig, kind, lab, years, R.loc[years, k], colr, "pct")
        if kind == "Lines":
            mark_extremes(fig, years, R.loc[years, "ebitda_margin"], lambda v: f"EBITDA {v:.1f}%")
        finish(fig, kind)
        style_fig(fig, "Margin trends (% of revenue)", 400)
        show(fig, "pf_margins")
        insight("margin_trend", c, years)
    with c4:
        kind = pick("pf_cost", ["Stacked bars", "Stacked area", "Lines"])
        fig = go.Figure()
        for lab, col, colr in [("Materials / COGS", "cogs", S5), ("Employee cost", "employee_cost", BLUE), ("Other expenses", "other_expenses", SKY), ("EBITDA", "ebitda", GOLD)]:
            draw(fig, kind, lab, years, [c.margin(col, y) for y in years], colr, "pct")
        finish(fig, kind)
        style_fig(fig, "Where each ₹100 of revenue goes (before D&A)", 400)
        if kind != "Lines":
            fig.update_yaxes(range=[0, 100])
        show(fig, "pf_cost")
        insight("cost_structure", c, years)

    fig = go.Figure()
    fig.add_trace(Bar("Operating EBIT", years, D.loc[years, "ebit"], NAVY, "cr1"))
    fig.add_trace(Bar("Other income", years, D.loc[years, "other_income"], GOLD, "cr1"))
    fig.add_trace(Bar("Finance costs", years, -D.loc[years, "finance_costs"], RED, "cr1"))
    fig.add_trace(Bar("Associates & exceptional (net)", years, D.loc[years, "share_assoc"] - D.loc[years, "exceptional_expense"], SKY, "cr1"))
    fig.add_trace(Line("PBT", years, D.loc[years, "pbt"], STRONG, "cr1"))
    fig.update_layout(barmode="relative")
    style_fig(fig, "Quality of earnings: how PBT is built (₹ cr)", 400)
    show(fig, "pf_quality")
    insight("earnings_quality", c, years)

    studio(EXPLORER_PL, ["revenue", "ebitda", "pat"], "st_pl", "Chart builder — income statement")
    glossary(["Crore", "Revenue", "Gross margin", "EBITDA", "EBIT", "PBT", "PAT", "Margin", "Depreciation", "bps"])

    sec("Income statement — selected years")
    rows = []
    for k in ["revenue", "gross_profit", "ebitda", "ebit", "other_income", "finance_costs", "pbt", "total_tax", "pat", "eps"]:
        rows.append([LABELS[k]] + [f"{D.loc[y, k]:,.2f}" for y in years]
                    + [f"{cagr(c.v(k, years[0]), c.v(k, years[-1]), len(years) - 1):.1f}%" if k != "finance_costs" else "–"])
    table(pd.DataFrame(rows, columns=["₹ crore"] + [FY_LONG[y] for y in years] + ["CAGR"]))


# ======================================================================================
# 3. BALANCE SHEET
# ======================================================================================
def _mix_chart(key, title, parts, kind, height=420):
    total = sum(s.loc[years] for _, s, _ in parts)
    fig = go.Figure()
    for lab, ser, colr in parts:
        if kind == "100% mix":
            draw(fig, kind, lab, years, list(ser.loc[years] / total * 100), colr, "pct")
        else:
            draw(fig, kind, lab, years, ser.loc[years], colr, "cr")
    finish(fig, kind)
    style_fig(fig, title + (" — % of total" if kind == "100% mix" else " (₹ cr)"), height)
    show(fig, key, unit="% of total" if kind == "100% mix" else "₹ crore")


def section_bs():
    sec("Balance Sheet Analysis", "Asset deployment, funding structure, debt and liquidity.")
    intro("Balance Sheet")
    cashbank = D["cash"] + D["bank_balances"]
    c1, c2 = st.columns(2)
    with c1:
        kind = pick("bs_assets", ["Stacked bars", "Stacked area", "100% mix"])
        _mix_chart("bs_assets", "Asset composition",
                   [("Net fixed assets & goodwill", D["net_fixed_assets"], NAVY), ("Investments (incl. associates/JV)", D["investments_total"], GOLD),
                    ("Inventories", D["inventories"], BLUE), ("Trade receivables", D["trade_receivables"], SKY), ("Cash & bank", cashbank, GREEN),
                    ("Loans, other financial & other assets", D["other_assets_bucket"], S5)], kind)
        insight("asset_mix", c, years)
    with c2:
        kind = pick("bs_funding", ["Stacked bars", "Stacked area", "100% mix"])
        _mix_chart("bs_funding", "Funding structure",
                   [("Total equity", D["total_equity"], NAVY), ("Borrowings", D["total_debt"], GOLD), ("Lease liabilities", D["lease_liab"], S6),
                    ("Trade payables", D["trade_payables"], BLUE), ("Other liabilities", D["other_liab_bucket"], S5)], kind)
        insight("funding_mix", c, years)

    c3, c4 = st.columns(2)
    with c3:
        kind = pick("bs_debt", ["Stacked bars", "Stacked area"])
        fig = go.Figure()
        draw(fig, kind, "Non-current borrowings", years, D.loc[years, "nc_borrowings"], NAVY, "cr")
        draw(fig, kind, "Current borrowings", years, D.loc[years, "c_borrowings"], GOLD, "cr")
        fig.add_trace(Line("Net debt / (net cash)", years, D.loc[years, "net_debt"], RED, "cr"))
        mark_extremes(fig, years, D.loc[years, "net_debt"], lambda v: cr(v))
        finish(fig, kind)
        style_fig(fig, "Debt profile and net debt (₹ cr)", 400)
        show(fig, "bs_debt")
        insight("debt_profile", c, years)
    with c4:
        fig = dual()
        fig.add_trace(Bar("Current assets", years, D.loc[years, "total_ca"], NAVY))
        fig.add_trace(Bar("Current liabilities", years, D.loc[years, "total_cl"], SKY))
        fig.add_trace(Line("Current ratio", years, R.loc[years, "current_ratio"], GOLD, "x"), secondary_y=True)
        fig.add_trace(Line("Quick ratio", years, R.loc[years, "quick_ratio"], AMBER, "x", dash="dot"), secondary_y=True)
        fig.add_trace(Line("Cash ratio", years, R.loc[years, "cash_ratio"], GREEN, "x", dash="dot"), secondary_y=True)
        fig.update_layout(barmode="group")
        style_fig(fig, "Liquidity position", 400)
        fig.update_yaxes(title_text="Ratio (times)", secondary_y=True, showgrid=False)
        show(fig, "bs_liq")
        insight("liquidity", c, years)

    c5, c6 = st.columns(2)
    with c5:
        fig = go.Figure()
        fig.add_trace(Bar("Liquid treasury (cash + bank + current investments)", years, D.loc[years, "liquid_treasury"], NAVY))
        fig.add_trace(Bar("Non-current investments + loans/ICDs", years, D.loc[years, "total_treasury"] - D.loc[years, "liquid_treasury"], SKY))
        fig.add_trace(Line("Borrowings", years, D.loc[years, "total_debt"], RED, "cr"))
        fig.update_layout(barmode="stack")
        style_fig(fig, "Treasury assets versus borrowings (₹ cr)", 400)
        show(fig, "bs_treasury")
        insight("treasury_vs_debt", c, years)
    with c6:
        fig = go.Figure()
        fig.add_trace(Bar("Inventories", years, D.loc[years, "inventories"], BLUE))
        fig.add_trace(Bar("Trade receivables", years, D.loc[years, "trade_receivables"], SKY))
        fig.add_trace(Bar("Trade payables (−)", years, -D.loc[years, "trade_payables"], GOLD))
        fig.add_trace(Line("Operating working capital", years, D.loc[years, "op_wc"], STRONG, "cr"))
        fig.update_layout(barmode="relative")
        style_fig(fig, "Operating working capital (₹ cr)", 400)
        show(fig, "bs_wc")
        insight("working_capital", c, years)

    studio(EXPLORER_BS, ["total_assets", "total_equity", "total_debt"], "st_bs", "Chart builder — balance sheet")
    glossary(["Crore", "Borrowings (debt)", "Net debt", "Working capital", "Current ratio", "Quick ratio", "Cash conversion cycle"])

    sec("Condensed balance sheet — selected years")
    keys = ["total_nca", "inventories", "trade_receivables", "liquid_treasury", "total_ca", "total_assets", "total_equity", "total_debt",
            "trade_payables", "total_cl", "total_liabilities", "net_debt", "nwc"]
    table(pd.DataFrame([[LABELS[k]] + [f"{D.loc[y, k]:,.2f}" for y in years] for k in keys], columns=["₹ crore"] + [FY_LONG[y] for y in years]))


# ======================================================================================
# 4. CASH FLOW
# ======================================================================================
def section_cf():
    sec("Cash Flow Analysis", "Cash generation, deployment and free cash flow.")
    intro("Cash Flow")
    c1, c2 = st.columns(2)
    with c1:
        kind = pick("cf_bars", ["Bars", "Lines", "Area"])
        fig = go.Figure()
        draw(fig, kind, "Operating", years, D.loc[years, "cfo"], NAVY, "cr")
        draw(fig, kind, "Investing", years, D.loc[years, "cfi"], GOLD, "cr")
        draw(fig, kind, "Financing", years, D.loc[years, "cff"], SKY, "cr")
        fig.add_trace(Line("Net change in cash", years, D.loc[years, "net_change_cash"], RED, "cr1", dash="dot"))
        finish(fig, kind)
        style_fig(fig, "Operating, investing and financing cash flows (₹ cr)", 410)
        show(fig, "cf_bars")
        insight("cf_bars", c, years)
    with c2:
        kind = pick("cf_fcf", ["Bars", "Lines", "Area"])
        fig = dual()
        draw(fig, kind, "Operating cash flow", years, D.loc[years, "cfo"], NAVY, "cr", secondary=False)
        draw(fig, kind, "Capex", years, D.loc[years, "capex"], SKY, "cr", secondary=False)
        draw(fig, kind, "Free cash flow", years, D.loc[years, "fcf"], GOLD, "cr", secondary=False)
        fig.add_trace(Line("FCF margin", years, R.loc[years, "fcf_margin"], RED, "pct", dash="dot"), secondary_y=True)
        finish(fig, kind)
        style_fig(fig, "Free cash flow = operating cash flow − capex (₹ cr)", 410)
        fig.update_yaxes(title_text="FCF margin %", secondary_y=True, showgrid=False)
        show(fig, "cf_fcf")
        insight("fcf", c, years)

    c3, c4 = st.columns(2)
    with c3:
        kind = pick("cf_conv", ["Lines", "Bars", "Area"])
        fig = go.Figure()
        for lab, k, colr in [("Pre-tax cash from ops / EBITDA", "cgo_ebitda", NAVY), ("CFO / EBITDA (post-tax)", "ocf_ebitda", BLUE),
                             ("CFO / PAT", "ocf_pat", GOLD), ("FCF / PAT", "fcf_pat", GREEN)]:
            draw(fig, kind, lab, years, R.loc[years, k], colr, "pct")
        finish(fig, kind)
        style_fig(fig, "Cash conversion quality (%)", 410)
        fig.add_hline(y=100, line_dash="dash", line_color=REF, annotation_text="100% = profit fully backed by cash", annotation_position="top left")
        show(fig, "cf_conv")
        insight("cash_conv", c, years)
    with c4:
        f = focus
        st.write("")
        waterfall(["Operating cash flow", "Capex", "Free cash flow", "Interest paid", "Dividends paid", "After dividends"],
                  [c.v("cfo", f), -c.v("capex", f), c.v("fcf", f), -c.v("interest_paid", f), -c.v("dividends_paid", f), c.v("fcf_after_div", f)],
                  ["absolute", "relative", "total", "relative", "relative", "total"], f"How {FY_LONG[f]} cash was used (₹ cr)", "cf_wf", 410)
        insight("cf_waterfall", c, years, focus=f)

    c5, c6 = st.columns(2)
    with c5:
        cfo, cap, it, dv = (c.total(k, years) for k in ["cfo", "capex", "interest_paid", "dividends_paid"])
        waterfall(["Operating cash flow", "Capex", "Interest paid", "Dividends paid", "Residual"],
                  [cfo, -cap, -it, -dv, cfo - cap - it - dv], ["absolute", "relative", "relative", "relative", "total"],
                  f"Cumulative sources & uses {years[0]}–{years[-1]} (₹ cr)", "cf_cum", 410)
        insight("cum_uses", c, years)
    with c6:
        fig = dual()
        fig.add_trace(Bar("Capex", years, D.loc[years, "capex"], NAVY))
        fig.add_trace(Bar("Depreciation & amortisation", years, D.loc[years, "depreciation"], SKY))
        fig.add_trace(Line("Capex / D&A", years, R.loc[years, "capex_dep"], GOLD, "x"), secondary_y=True)
        fig.update_layout(barmode="group")
        style_fig(fig, "Reinvestment: capex versus depreciation", 410)
        fig.update_yaxes(title_text="x", secondary_y=True, showgrid=False)
        show(fig, "cf_capex")
        insight("capex_dep", c, years)

    studio(EXPLORER_CF, ["cfo", "capex", "fcf"], "st_cf", "Chart builder — cash flow")
    glossary(["Crore", "Operating cash flow", "Capex", "Free cash flow", "Depreciation", "Payout ratio"])
    sec("Cash-flow summary — selected years")
    keys = ["cash_gen_ops", "tax_paid", "cfo", "capex", "fcf", "cfi", "interest_paid", "dividends_paid", "cff", "net_change_cash", "closing_cash_net_od"]
    table(pd.DataFrame([[LABELS[k]] + [f"{D.loc[y, k]:,.2f}" for y in years] for k in keys], columns=["₹ crore"] + [FY_LONG[y] for y in years]))


# ======================================================================================
# 5. RATIOS
# ======================================================================================
def ratio_table(keys: list[str]) -> str:
    head = "".join(f"<th>{y}</th>" for y in years)
    out = [f'<table class="rt"><tr><th>Ratio</th><th>Formula</th>{head}<th>Trend</th><th>{focus} band</th><th>Interpretation</th></tr>']
    for k in keys:
        m = RATIO_META[k]
        s = R.loc[years, k]
        d_ = s.iloc[-1] - s.iloc[0]
        colr = MUTED if (m["hib"] is None or abs(d_) < 1e-9) else (GREEN if (d_ > 0) == bool(m["hib"]) else RED)
        cells = "".join(f'<td class="num">{html.escape(fmt_value(k, s[y]))}</td>' for y in years)
        b = band(k, R.loc[focus, k])
        cls = {"Strong": "Healthy", "Adequate": "Watch", "Weak": "Risk"}.get(b, "")
        bpill = f'<span class="pill {cls}">{b}</span>' if b != "-" else "–"
        out.append(f'<tr><td><b>{html.escape(m["name"])}</b></td><td class="f">{html.escape(m["formula"])}</td>{cells}'
                   f'<td style="color:{colr};font-weight:700;text-align:center">{arrow(d_)}</td><td>{bpill}</td>'
                   f'<td class="f">{html.escape(interpret(k, R, years))}</td></tr>')
    out.append("</table>")
    return "".join(out)


def section_ratios():
    sec("Financial Ratio Analysis", "Formulas, five-year values and dynamic interpretation. Averages use opening/closing balances (FY22 opens on FY21).")
    intro("Ratios")
    tabs = st.tabs(CATEGORIES)
    for tab, cat in zip(tabs, CATEGORIES):
        with tab:
            html_block(ratio_table([k for k, m in RATIO_META.items() if m["cat"] == cat]))

    sec("Ratio explorer", "Choose any ratio, compare several, and switch the chart type.")
    cc1, cc2 = st.columns([1, 2])
    with cc1:
        cat = st.selectbox("Category", CATEGORIES, key="rx_cat")
        keys = [k for k, m in RATIO_META.items() if m["cat"] == cat]
        k = st.selectbox("Ratio", keys, format_func=lambda x: RATIO_META[x]["name"], key="rx_ratio")
        m = RATIO_META[k]
        extra = st.multiselect("Overlay other ratios (same category)", [x for x in keys if x != k], format_func=lambda x: RATIO_META[x]["name"], key="rx_extra")
        html_block(f'<div class="panel navy"><h4>{html.escape(m["name"])}</h4><p style="font-size:.85rem"><b>Formula:</b> {html.escape(m["formula"])}</p>'
                   f'<p style="font-size:.85rem">{html.escape(interpret(k, R, years))}</p></div>')
    with cc2:
        kind = pick("rx_chart", ["Bars", "Lines", "Area"], 1)
        s = R.loc[years, k]
        fmt = {"%": "pct", "x": "x", "days": "days"}.get(m["unit"], "num")
        fig = dual() if extra else go.Figure()
        draw(fig, kind, m["name"], years, s, NAVY, fmt, secondary=False if extra else None)
        fig.add_trace(Line("Period average", years, [s.mean()] * len(years), GOLD, fmt, dash="dash"), **({"secondary_y": False} if extra else {}))
        for i, x in enumerate(extra):
            mx = RATIO_META[x]
            fx = {"%": "pct", "x": "x", "days": "days"}.get(mx["unit"], "num")
            fig.add_trace(Line(mx["name"], years, R.loc[years, x], SERIES_COLORS()[(i + 2) % 8], fx), secondary_y=True)
        finish(fig, kind)
        style_fig(fig, m["name"] + (" (+ overlays on right axis)" if extra else ""), 400)
        show(fig, "rx_chart", title=m["name"], how=m["meaning"],
             unit={"%": "Percent (%)", "x": "Times (x)", "days": "Days", "₹": "₹ per share"}.get(m["unit"], "₹ crore"))

    c1, c2 = st.columns(2)
    with c1:
        fig = dual()
        fig.add_trace(Bar("Net margin %", years, R.loc[years, "pat_margin"], SKY, "pct"))
        fig.add_trace(Line("Asset turnover (x)", years, R.loc[years, "asset_turnover"], BLUE, "x"), secondary_y=True)
        fig.add_trace(Line("Equity multiplier (x)", years, R.loc[years, "equity_multiplier"], S6, "x"), secondary_y=True)
        fig.add_trace(Line("ROE %", years, R.loc[years, "roe"], GOLD, "pct"))
        style_fig(fig, "DuPont: ROE = margin × turnover × leverage", 410)
        fig.update_yaxes(title_text="% (ROE, net margin)", secondary_y=False)
        fig.update_yaxes(title_text="x", secondary_y=True, showgrid=False)
        show(fig, "rx_dupont")
        insight("dupont", c, years)
    with c2:
        fig = go.Figure()
        fig.add_trace(Bar("Inventory days", years, R.loc[years, "inventory_days"], NAVY, "days"))
        fig.add_trace(Bar("Receivable days", years, R.loc[years, "receivable_days"], SKY, "days"))
        fig.add_trace(Bar("Payable days (−)", years, -R.loc[years, "payable_days"], GOLD, "days"))
        fig.add_trace(Line("Cash conversion cycle", years, R.loc[years, "ccc"], RED, "days"))
        fig.update_layout(barmode="relative")
        style_fig(fig, "Working-capital cycle (days)", 410)
        show(fig, "rx_days")
        insight("wc_days", c, years)

    pil = ["Profitability", "Liquidity", "Solvency", "Efficiency", "Cash Flow"]
    fig = go.Figure()
    for y, colr in [(years[0], SKY), (focus, GOLD)]:
        v = list(c.sc.loc[y, pil])
        fig.add_trace(go.Scatterpolar(r=v + [v[0]], theta=pil + [pil[0]], fill="toself", name=y, line=dict(color=colr),
                                      hovertemplate="%{theta}: %{r:.0f}/100<extra>" + y + "</extra>", opacity=0.75))
    fig.update_layout(polar=dict(bgcolor=PAL["CARD"], radialaxis=dict(range=[0, 100], gridcolor=GRID, color=INK), angularaxis=dict(color=INK, gridcolor=GRID)),
                      height=int(400 * PAL["HEIGHT"]), paper_bgcolor=PAL["CARD"], font=dict(color=INK),
                      title=dict(text=f"Pillar scorecard: {years[0]} vs {focus}", x=0.01, font=dict(size=15, color=STRONG)),
                      margin=dict(l=40, r=40, t=60, b=30), legend=dict(orientation="h"))
    show(fig, "rx_radar")
    glossary(["EBITDA", "Margin", "ROE", "ROCE", "Current ratio", "Quick ratio", "Interest cover", "Payout ratio", "Cash conversion cycle", "Free cash flow"])


# ======================================================================================
# 6. RED FLAGS
# ======================================================================================
def flag_table(df: pd.DataFrame) -> str:
    if df.empty:
        return '<div class="panel good">No tests match the selected filters.</div>'
    out = ['<table class="rt"><tr><th>Year</th><th>Status</th><th>Category</th><th>Test</th><th>Metric</th><th>Assessment</th><th>Rule</th></tr>']
    for r_ in df.itertuples(index=False):
        out.append(f'<tr><td>{r_.Year}</td><td><span class="pill {r_.Status}">{r_.Status}</span></td><td>{html.escape(r_.Category)}</td>'
                   f'<td><b>{html.escape(r_.Test)}</b></td><td class="num">{html.escape(r_.Metric)}</td><td>{html.escape(r_.Assessment)}</td>'
                   f'<td class="f">{html.escape(r_.Rule)}</td></tr>')
    out.append("</table>")
    return "".join(out)


def section_flags():
    sec("Red Flag Analysis", f"{len(FLAG_TESTS)} rule-based tests covering margins, leverage, liquidity, cash flow, working capital and capital allocation.")
    intro("Red Flags")
    cnt = flag_counts(flags, focus)
    load = [flag_counts(flags, y)["Risk"] + flag_counts(flags, y)["Watch"] * 0.5 for y in years]
    cols = st.columns(4)
    for slot, (lab, val, tone, spark) in zip(cols, [("Risk flags", cnt["Risk"], "bad", load), ("Watch flags", cnt["Watch"], "flat", load),
                                                    ("Healthy tests", cnt["Healthy"], "good", []), ("Tests run", sum(cnt.values()), "flat", [])]):
        with slot:
            html_block(kpi_card(f"{lab} · {focus}", str(val), f"Focus year {FY_LONG[focus]}", tone, spark, "sparkline: weighted flag load" if spark else ""))
    st.write("")

    mat, vals = flags["matrix"][years], flags["values"][years]
    labels_ = mat.replace({0: "OK", 1: "Watch", 2: "Risk"})
    fig = go.Figure(go.Heatmap(
        z=mat.values, x=years, y=list(mat.index), text=labels_.values, texttemplate="%{text}", textfont=dict(color=PAL["STATUS_TEXT"], size=11), customdata=vals.values,
        colorscale=[[0, PAL["STATUS"][0]], [0.3333, PAL["STATUS"][0]], [0.3334, PAL["STATUS"][1]], [0.6666, PAL["STATUS"][1]], [0.6667, PAL["STATUS"][2]], [1, PAL["STATUS"][2]]],
        zmin=0, zmax=2, showscale=False, xgap=3, ygap=3, hovertemplate="<b>%{y}</b><br>%{x}: %{customdata}<extra></extra>"))
    style_fig(fig, "Red-flag heat map (hover for the measured value)", 120 + 27 * len(mat), legend=False, hover="closest", xaxis_title=None)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top")
    show(fig, "rf_heat")
    persistent = [t for t in mat.index if (mat.loc[t] > 0).all()]
    last_flags = [t for t in mat.index if mat.loc[t, years[-1]] > 0]
    html_block(insight_box(f"{years[-1]}: {', '.join(last_flags) if last_flags else 'no tests flagged'}. Flagged in every selected year: "
                           f"{', '.join(persistent) if persistent else 'none'}. Year with the heaviest flag load: "
                           f"{mat.apply(lambda s: (s == 2).sum() * 2 + (s == 1).sum()).idxmax()}."))

    sec("Flag register")
    f1, f2, f3 = st.columns(3)
    with f1:
        sev = st.multiselect("Status", ["Risk", "Watch", "Healthy"], default=["Risk", "Watch"], key="rf_sev")
    with f2:
        yrs = st.multiselect("Years", years, default=[focus], key="rf_years")
    with f3:
        allc = sorted(flags["detail"]["Category"].unique())
        cats = st.multiselect("Category", allc, default=allc, key="rf_cats")
    det = flags["detail"]
    det = det[det.Status.isin(sev) & det.Year.isin(yrs) & det.Category.isin(cats)].sort_values(["Year", "Severity"], ascending=[True, False])
    html_block(flag_table(det))

    sec("Supporting evidence")
    s1, s2 = st.columns(2)
    with s1:
        kind = pick("rf_margin", ["Bars", "Lines", "Area"])
        fig = go.Figure()
        for lab, col, colr in [("Gross margin change", "gross_profit", SKY), ("EBITDA margin change", "ebitda", NAVY), ("PAT margin change", "pat", GOLD)]:
            draw(fig, kind, lab + " (bps)", years, [(c.margin(col, y) - c.margin(col, c.prev(y))) * 100 for y in years], colr, "bps")
        finish(fig, kind)
        style_fig(fig, "Year-on-year margin change (bps)", 380)
        show(fig, "rf_margin")
        insight("margin_trend", c, years)
    with s2:
        fig = dual()
        fig.add_trace(Bar("Current borrowings", years, D.loc[years, "c_borrowings"], GOLD, "cr"))
        fig.add_trace(Bar("Liquid treasury", years, D.loc[years, "liquid_treasury"], NAVY, "cr"))
        fig.add_trace(Line("Short-term share of debt (%)", years, R.loc[years, "st_debt_share"], RED, "pct"), secondary_y=True)
        fig.update_layout(barmode="group")
        style_fig(fig, "Refinancing exposure: current borrowings vs liquid treasury (₹ cr)", 380)
        fig.update_yaxes(title_text="Short-term share %", secondary_y=True, showgrid=False, range=[0, 100])
        show(fig, "rf_refi")
        insight("refinancing", c, years)
    s3, s4 = st.columns(2)
    with s3:
        fig = go.Figure()
        fig.add_trace(Bar("Receivables growth %", years, [c.g("trade_receivables", y) for y in years], GOLD, "pct"))
        fig.add_trace(Bar("Revenue growth %", years, [c.g("revenue", y) for y in years], NAVY, "pct"))
        fig.update_layout(barmode="group")
        style_fig(fig, "Receivables vs revenue growth (%)", 380)
        show(fig, "rf_rec")
        insight("receivables_vs_revenue", c, years)
    with s4:
        fig = go.Figure()
        for lab, col, colr in [("PAT", "pat", SKY), ("Operating cash flow", "cfo", NAVY), ("Free cash flow", "fcf", GOLD), ("Dividends paid", "dividends_paid", RED)]:
            fig.add_trace(Bar(lab, years, D.loc[years, col], colr))
        fig.update_layout(barmode="group")
        style_fig(fig, "Profit vs cash vs distributions (₹ cr)", 380)
        show(fig, "rf_cash")
        insight("cash_conv", c, years)


# ======================================================================================
# 7. EXECUTIVE INSIGHTS
# ======================================================================================
def _bullets(items):
    out = []
    for t in items:
        t = html.escape(t)
        while "**" in t:
            t = t.replace("**", "<b>", 1).replace("**", "</b>", 1)
        out.append(f"<li>{t}</li>")
    return "<ul style='padding-left:1.1rem;margin:0'>" + "".join(out) + "</ul>"


def section_insights():
    ei = executive_insights(c, years, flags)
    sec("Executive Insights", f"Strengths, weaknesses and overall financial health, {FY_LONG[years[0]]} → {FY_LONG[years[-1]]}.")
    intro("Insights")
    tone_col = {"good": GREEN, "neutral": GOLD, "warn": AMBER, "bad": RED}[ei["tone"]]
    html_block(f'<div class="panel navy"><div style="display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap">'
               f'<div style="text-align:center;min-width:130px"><div class="hf" style="font-size:3rem;color:{STRONG}">{ei["score"]:.0f}</div>'
               f'<div style="color:{tone_col};font-weight:700;letter-spacing:1px;text-transform:uppercase">{ei["label"]}</div><div style="font-size:.7rem;color:{MUTED}">health score /100</div></div>'
               f'<div style="flex:1;min-width:280px;font-size:.92rem;line-height:1.55">{html.escape(ei["overall"]).replace("**", "")}</div></div></div>')
    st.write("")
    a, b = st.columns(2)
    with a:
        html_block(f'<div class="panel good"><h4>Financial strengths</h4>{_bullets(ei["strengths"])}</div>')
    with b:
        html_block(f'<div class="panel bad"><h4>Weaknesses &amp; watch-points</h4>{_bullets(ei["weaknesses"])}</div>')

    sec("Five-year trends")
    table(ei["trends"])

    sec("Health score by pillar")
    kind = pick("in_health", ["Bars", "Lines", "Area"])
    hs_ = c.sc.loc[years]
    fig = go.Figure()
    for i, pcol in enumerate(["Profitability", "Liquidity", "Solvency", "Efficiency", "Cash Flow"]):
        draw(fig, kind, pcol, years, hs_[pcol], SERIES_COLORS()[(i + 2) % 8], "num")
    draw(fig, "Lines", "Overall", years, hs_["Overall"], GOLD, "num")
    fig.data[-1].line.width = 4
    finish(fig, kind)
    style_fig(fig, "Pillar scores by year", 380)
    fig.update_yaxes(range=[0, 105])
    show(fig, "in_health")
    insight("health_trend", c, years)
    hs = c.sc.loc[years].T.round(1)
    hs.insert(0, "Weight", [f"{PILLAR_WEIGHTS.get(i, 1) * 100:.0f}%" if i in PILLAR_WEIGHTS else "—" for i in hs.index])
    table(hs.reset_index().rename(columns={"index": "Pillar"}))

    cq, rm = st.columns(2)
    with cq:
        html_block('<div class="panel navy"><h4>Questions for management / CFO agenda</h4><ol style="padding-left:1.1rem;margin:0">'
                   + "".join(f"<li style='margin-bottom:.5rem;font-size:.88rem'>{html.escape(q)}</li>" for q in ei["questions"]) + "</ol></div>")
    with rm:
        fy = flags["detail"]
        fy = fy[(fy.Year == years[-1]) & (fy.Severity > 0)].sort_values("Severity", ascending=False)
        items = "".join(f"<li style='margin-bottom:.45rem;font-size:.86rem'><span class='pill {r_.Status}'>{r_.Status}</span> <b>{html.escape(r_.Test)}</b> — {html.escape(r_.Assessment)}</li>"
                        for r_ in fy.itertuples(index=False)) or "<li>No Risk or Watch flags in the latest selected year.</li>"
        html_block(f'<div class="panel bad"><h4>Live watch-list · {years[-1]}</h4><ul style="padding-left:1.1rem;margin:0">{items}</ul></div>')

    with st.expander("Methodology — health-score model (transparent, rule-based, not a credit rating)"):
        rows = [[p_, f"{PILLAR_WEIGHTS[p_] * 100:.0f}%", RATIO_META[k]["name"], z, h] for p_, rules in SCORE_RULES.items() for k, (z, h) in rules.items()]
        table(pd.DataFrame(rows, columns=["Pillar", "Pillar weight", "Indicator", "Scores 0 at", "Scores 100 at"]))
        st.caption("Each indicator is scored linearly between its 0 and 100 anchors (clipped), averaged within a pillar, then weighted. "
                   "Bands: ≥80 Excellent, 65–79 Strong, 50–64 Sound, 35–49 Watchful, <35 Stressed. Anchors are judgemental FMCG benchmarks and can be changed in src/ratios.py.")
    st.caption("Scope: analysis uses only figures from the five consolidated annual reports. It does not include market data, forecasts, segment data or "
               "contingent-liability analysis; narrative on causes is limited to what the statements evidence and is otherwise posed as a question.")


# ======================================================================================
# 8. DATA & VERIFICATION
# ======================================================================================
def section_data():
    sec("Data & Verification", "Cleaned five-year dataset, integrity checks, restatement log and sources.")
    passed = int((verification.Result == "PASS").sum())
    html_block(f'<div class="panel good"><b>{passed} of {len(verification)} integrity checks passed.</b> Every subtotal, balance-sheet identity, '
               f'EBIT-to-PBT bridge, cash-flow reconciliation and EPS was re-computed from the extracted line items and agrees with the reported totals within ₹0.06 cr rounding.</div>')
    st.write("")
    tabs = st.tabs(["Income statement", "Balance sheet", "Cash flow", "Integrity checks", "Restatements", "Sources & notes"])
    for tab, (name, keys) in zip(tabs[:3], STATEMENT_GROUPS.items()):
        with tab:
            table(pd.DataFrame([[LABELS[k]] + [f"{D.loc[y, k]:,.2f}" for y in years] for k in keys], columns=["₹ crore"] + [FY_LONG[y] for y in years]), height=620)
    with tabs[3]:
        only_fail = st.checkbox("Show failures only", value=False, key="vf")
        table(verification[verification.Result == "FAIL"] if only_fail else verification, height=560)
    with tabs[4]:
        st.caption("Where a later annual report re-presented a prior-year figure, the LATEST presentation is used in this dashboard; the original is logged here.")
        table(RESTATEMENT_LOG)
    with tabs[5]:
        table(SOURCES)
        for n_ in DATA_NOTES:
            st.markdown(f"- {n_}")


# ======================================================================================
# Router
# ======================================================================================
{"Overview": section_overview, "Profitability": section_profit, "Balance Sheet": section_bs, "Cash Flow": section_cf,
 "Ratios": section_ratios, "Red Flags": section_flags, "Insights": section_insights, "Data": section_data}[section]()

html_block('<div class="foot">Britannia Industries Limited · Consolidated financials FY2021-22 to FY2025-26 · ₹ crore · Derived measures (EBITDA, EBIT, ratios, scores) are analyst calculations, '
           'not company-reported figures. For analytical use; not investment advice.</div>')
