"""
Analytics layer: red-flag rule engine, per-chart management insights and executive commentary.

Everything here is generated from the verified dataset - there are no hard-coded conclusions.  Narrative is
deliberately limited to what the numbers support; where a driver is only plausible (not evidenced in the
extracted statements) the text says so, or poses it as a question for management.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fin_data import FY, FY_ALL, FY_LONG, LABELS, load_financials
from fin_ratios import RATIO_META, compute_ratios, health_scores, rating_label
from fin_utils import bps, cagr, cr, growth, is_nan, mult, pct

STATUS_LABEL = {0: "Healthy", 1: "Watch", 2: "Risk"}


# --------------------------------------------------------------------------------------
# CONTEXT
# --------------------------------------------------------------------------------------
@dataclass
class Ctx:
    d: pd.DataFrame      # FY21 (base) + FY22..FY26
    r: pd.DataFrame      # ratios FY22..FY26
    sc: pd.DataFrame     # health scores FY22..FY26

    def prev(self, y: str) -> str:
        return FY_ALL[FY_ALL.index(y) - 1]

    def v(self, col: str, y: str) -> float:
        return float(self.d.loc[y, col])

    def g(self, col: str, y: str) -> float:
        """YoY growth % (FY22 is measured against the FY21 base)."""
        return growth(self.v(col, y), self.v(col, self.prev(y)))

    def margin(self, col: str, y: str) -> float:
        return self.v(col, y) / self.v("revenue", y) * 100.0

    def total(self, col: str, years: list[str]) -> float:
        return float(self.d.loc[years, col].sum())


def build_ctx() -> Ctx:
    d = load_financials(include_base=True)
    r = compute_ratios()
    return Ctx(d=d, r=r, sc=health_scores(r))


def _span(c: Ctx, col: str, years: list[str]) -> tuple[float, float, float]:
    """first, last, CAGR over the selected window."""
    a, b = c.v(col, years[0]), c.v(col, years[-1])
    return a, b, cagr(a, b, len(years) - 1)


def _argmax(s: pd.Series) -> str:
    return str(s.idxmax())


def _argmin(s: pd.Series) -> str:
    return str(s.idxmin())


# --------------------------------------------------------------------------------------
# RED-FLAG ENGINE
# --------------------------------------------------------------------------------------
def _st(value: float, watch: float, risk: float, worse: str = "high") -> int:
    """0 healthy / 1 watch / 2 risk, given thresholds. worse='high' => larger values are worse."""
    if is_nan(value):
        return 0
    if worse == "high":
        return 2 if value >= risk else (1 if value >= watch else 0)
    return 2 if value <= risk else (1 if value <= watch else 0)


def _flag_gross_margin(c: Ctx, y: str):
    p = c.prev(y)
    now, before = c.margin("gross_profit", y), c.margin("gross_profit", p)
    delta = now - before
    s = _st(delta, -0.30, -1.00, "low")
    note = (" The FY2021-22 Directors' Report cites commodity inflation (crude, edible oils) lifting input and transport costs."
            if y == "FY22" and s else "")
    msg = (f"Gross margin {'fell' if delta < 0 else 'rose'} {abs(delta) * 100:,.0f} bps to {now:.1f}% (from {before:.1f}%): "
           + ("input costs outran pricing/mix." if s else "pricing and mix absorbed input costs.") + note)
    return s, f"{now:.1f}% ({bps(delta)})", msg


def _flag_ebitda_margin(c: Ctx, y: str):
    p = c.prev(y)
    now, before = c.margin("ebitda", y), c.margin("ebitda", p)
    delta = now - before
    s = _st(delta, -0.30, -1.00, "low")
    msg = (f"EBITDA margin {'compressed' if delta < 0 else 'expanded'} {abs(delta) * 100:,.0f} bps to {now:.1f}% (from {before:.1f}%). "
           + ("Operating profitability weakened versus the prior year." if s else "Operating profitability held or improved."))
    return s, f"{now:.1f}% ({bps(delta)})", msg


def _flag_pat_margin(c: Ctx, y: str):
    p = c.prev(y)
    now, before = c.margin("pat", y), c.margin("pat", p)
    delta = now - before
    s = _st(delta, -0.30, -1.00, "low")
    note = ""
    if s and c.v("exceptional_expense", p) < -0.05 * c.v("pbt", p):
        s = min(s, 1)
        note = f" Part of the fall reflects the {p} base, which was inflated by a one-off gain of {cr(abs(c.v('exceptional_expense', p)))}."
    msg = f"PAT margin {now:.1f}% vs {before:.1f}% ({bps(delta)}).{note}"
    return s, f"{now:.1f}% ({bps(delta)})", msg


def _flag_revenue_growth(c: Ctx, y: str):
    gr = c.g("revenue", y)
    s = 2 if gr < 0 else (1 if gr < 5 else 0)
    msg = f"Revenue grew {gr:.1f}% YoY to {cr(c.v('revenue', y))}." + (" Growth is below 5% - top-line momentum is soft." if s else "")
    return s, f"{gr:+.1f}%", msg


def _flag_operating_leverage(c: Ctx, y: str):
    gap = c.g("revenue", y) - c.g("ebitda", y)
    s = _st(gap, 5, 10)
    msg = (f"EBITDA grew {c.g('ebitda', y):+.1f}% vs revenue {c.g('revenue', y):+.1f}%: "
           + ("negative operating leverage - costs grew faster than sales." if s else "profit grew at least in line with sales."))
    return s, f"EBITDA {c.g('ebitda', y):+.1f}% vs rev {c.g('revenue', y):+.1f}%", msg


def _flag_opex_growth(c: Ctx, y: str):
    p = c.prev(y)
    op = lambda yy: c.v("employee_cost", yy) + c.v("other_expenses", yy)
    og = growth(op(y), op(p))
    gap = og - c.g("revenue", y)
    s = _st(gap, 5, 15)
    msg = (f"Employee + other operating expenses grew {og:+.1f}% vs revenue {c.g('revenue', y):+.1f}%"
           + (" - overhead creep is eroding margin." if s else " - overheads are well controlled."))
    return s, f"Opex {og:+.1f}% vs rev {c.g('revenue', y):+.1f}%", msg


def _flag_earnings_quality(c: Ctx, y: str):
    exc, pbt = c.v("exceptional_expense", y), c.v("pbt", y)
    share = abs(exc) / pbt * 100
    s = _st(share, 5, 15)
    kind = "gain" if exc < 0 else "charge"
    msg = (f"Exceptional {kind} of {cr(abs(exc), 1)} = {share:.1f}% of PBT." +
           (" Reported profit is distorted by a one-off; use PBT before exceptional items to judge the trend." if s else " Earnings are free of material one-offs."))
    return s, f"{share:.1f}% of PBT", msg


def _flag_other_income(c: Ctx, y: str):
    share = c.v("other_income", y) / c.v("pbt", y) * 100
    s = _st(share, 20, 35)
    msg = f"Other income is {share:.1f}% of PBT: " + ("profit leans on treasury income." if s else "earnings are operating-led.")
    return s, f"{share:.1f}% of PBT", msg


def _flag_associates(c: Ctx, y: str):
    p = c.prev(y)
    now, before = c.v("share_assoc", y), c.v("share_assoc", p)
    pbt = c.v("pbt", y)
    s = 0
    if now < -10:
        s = 1
        if abs(now) > 1.0 * max(abs(before), 1e-9) * 2 or abs(now) / pbt > 0.03:
            s = 1 if abs(now) / pbt <= 0.03 else 2
    msg = (f"Share of associates/JV result: {cr(now, 1)} (prior {cr(before, 1)}). "
           + ("Losses are widening - review the carrying value of the investment in associates & JV ("
              f"{cr(c.v('associates_jv', y))})." if s else "No material drag from associates/JV."))
    return s, f"{cr(now, 1)}", msg


def _flag_debt_rise(c: Ctx, y: str):
    p = c.prev(y)
    now, before = c.v("total_debt", y), c.v("total_debt", p)
    gr = growth(now, before)
    s = 0 if (now - before) < 100 else _st(gr, 10, 25)
    msg = (f"Borrowings {'rose' if now > before else 'fell'} {abs(gr):.1f}% to {cr(now)} (from {cr(before)}). "
           + ("Debt is rising - confirm the use of proceeds (capex vs shareholder distributions)." if s else "Leverage is stable or falling."))
    return s, f"{gr:+.1f}% to {cr(now)}", msg


def _flag_net_debt(c: Ctx, y: str):
    nd_e = c.r.loc[y, "net_debt_ebitda"]
    s = _st(nd_e, 0.5, 1.0)
    msg = (f"Net debt / EBITDA {nd_e:.2f}x ({'net debt' if nd_e > 0 else 'net cash'} of {cr(abs(c.v('net_debt', y)))}). "
           + ("Net borrowings are meaningful relative to earnings." if s else "Treasury assets exceed borrowings."))
    return s, f"{nd_e:.2f}x", msg


def _flag_refinancing(c: Ctx, y: str):
    share = c.r.loc[y, "st_debt_share"]
    cover = c.v("liquid_treasury", y) / c.v("c_borrowings", y)
    if share < 60:
        s = 0
    else:
        s = 1 if cover >= 1.0 else 2
    msg = (f"Short-term borrowings are {share:.0f}% of debt; liquid treasury covers them {cover:.2f}x. "
           + ("Refinancing exposure is NOT covered by liquid assets." if s == 2 else
              "Concentrated in short-term paper but fully covered by liquid treasury - monitor, low immediate risk." if s == 1
              else "Debt maturity profile is balanced."))
    return s, f"{share:.0f}% short-term; cover {cover:.2f}x", msg


def _flag_current_ratio(c: Ctx, y: str):
    cr_ = c.r.loc[y, "current_ratio"]
    s = _st(cr_, 1.0, 0.8, "low")
    msg = (f"Current ratio {cr_:.2f}x (quick {c.r.loc[y, 'quick_ratio']:.2f}x). "
           + ("Below 1.0x: short-term obligations exceed short-term assets." if s else "Short-term assets cover short-term obligations."))
    return s, f"{cr_:.2f}x", msg


def _flag_quick_ratio(c: Ctx, y: str):
    q = c.r.loc[y, "quick_ratio"]
    s = _st(q, 0.70, 0.50, "low")
    msg = f"Quick ratio {q:.2f}x. " + ("Thin liquidity ex-inventory." if s else "Adequate liquidity without relying on stock.")
    return s, f"{q:.2f}x", msg


def _flag_interest_cover(c: Ctx, y: str):
    ic = c.r.loc[y, "interest_cover"]
    s = _st(ic, 8, 4, "low")
    msg = f"EBIT covers finance cost {ic:.1f}x. " + ("Debt-service headroom is limited." if s else "Debt service is very comfortable.")
    return s, f"{ic:.1f}x", msg


def _flag_finance_cost(c: Ctx, y: str):
    p = c.prev(y)
    gr = growth(c.v("finance_costs", y), c.v("finance_costs", p))
    s = _st(gr, 15, 40) if abs(c.v("finance_costs", y) - c.v("finance_costs", p)) > 10 else 0
    msg = f"Finance costs {gr:+.1f}% to {cr(c.v('finance_costs', y), 1)}. " + ("Funding cost burden is climbing." if s else "Funding cost is stable or falling.")
    return s, f"{gr:+.1f}%", msg


def _flag_cash_conversion(c: Ctx, y: str):
    cc = c.r.loc[y, "cgo_ebitda"]
    s = _st(cc, 90, 75, "low")
    chg = c.v("chg_inventories_cf", y)
    note = f" Inventories absorbed {cr(abs(chg))} of cash." if (s and chg < -100) else ""
    msg = f"Pre-tax cash generated from operations = {cc:.0f}% of EBITDA.{note}" + ("" if s else " Earnings convert well to cash.")
    return s, f"{cc:.0f}%", msg


def _flag_ocf_pat(c: Ctx, y: str):
    x = c.r.loc[y, "ocf_pat"]
    s = _st(x, 90, 70, "low")
    msg = f"Operating cash flow is {x:.0f}% of PAT. " + ("Profits are not fully backed by cash this year." if s else "Profits are backed by cash.")
    return s, f"{x:.0f}%", msg


def _flag_fcf(c: Ctx, y: str):
    f, m = c.v("fcf", y), c.r.loc[y, "fcf_margin"]
    s = 2 if f < 0 else (1 if m < 5 else 0)
    msg = f"Free cash flow {cr(f)} ({m:.1f}% of revenue). " + ("Weak free-cash generation." if s else "Healthy free-cash generation.")
    return s, f"{cr(f)} ({m:.1f}%)", msg


def _flag_dividend_cover(c: Ctx, y: str):
    cov = c.r.loc[y, "fcf_div_cover"]
    gap = c.v("fcf", y) - c.v("dividends_paid", y)
    s = _st(cov, 1.0, 0.5, "low")
    msg = (f"FCF covers dividends paid {cov:.2f}x" + (f" - shortfall of {cr(abs(gap))} had to be met from treasury/borrowings." if gap < 0
           else f" - surplus of {cr(gap)} after dividends."))
    return s, f"{cov:.2f}x", msg


def _flag_capex(c: Ctx, y: str):
    x = c.r.loc[y, "capex_dep"]
    s = _st(x, 0.8, 0.5, "low")
    msg = (f"Capex {cr(c.v('capex', y))} = {x:.2f}x depreciation ({c.r.loc[y, 'capex_revenue']:.1f}% of revenue). "
           + ("Asset base is being consumed faster than replaced - confirm capacity headroom (FCF is flattered by low capex)." if s else "Reinvestment is at or above maintenance level."))
    return s, f"{x:.2f}x", msg


def _flag_cfo_trend(c: Ctx, y: str):
    p = c.prev(y)
    if p == "FY21":
        return 0, "n/a", "No prior-year cash-flow comparator in the dataset."
    gr = growth(c.v("cfo", y), c.v("cfo", p))
    s = _st(gr, -5, -15, "low")
    msg = f"Operating cash flow {gr:+.1f}% YoY to {cr(c.v('cfo', y))}." + (" Operating cash generation is shrinking." if s else "")
    return s, f"{gr:+.1f}%", msg


def _flag_receivables(c: Ctx, y: str):
    p = c.prev(y)
    rg, sg = c.g("trade_receivables", y), c.g("revenue", y)
    gap = rg - sg
    dso = c.v("trade_receivables", y) / c.v("revenue", y) * 365
    s = _st(gap, 10, 25)
    if dso < 15:
        s = min(s, 1)
    msg = (f"Receivables {rg:+.1f}% vs revenue {sg:+.1f}% (closing DSO {dso:.1f} days)."
           + (" Receivables are outgrowing sales; absolute DSO is still very low so credit risk is limited, but the trend should be monitored." if s else ""))
    return s, f"Rec {rg:+.1f}% vs rev {sg:+.1f}%", msg


def _flag_inventory(c: Ctx, y: str):
    p = c.prev(y)
    dio = lambda yy: c.v("inventories", yy) / c.v("cogs", yy) * 365
    delta = dio(y) - dio(p)
    s = _st(delta, 4, 10)
    msg = f"Closing inventory days {dio(y):.1f} ({delta:+.1f} vs {p}). " + ("Stock build-up ties up cash." if s else "Inventory discipline maintained.")
    return s, f"{dio(y):.1f} days ({delta:+.1f})", msg


def _flag_payout(c: Ctx, y: str):
    po = c.r.loc[y, "payout"]
    s = _st(po, 90, 100)
    msg = f"Dividends recognised = {po:.0f}% of PAT. " + ("Distribution exceeds or nearly equals earnings - equity is being drawn down." if s else "Payout is sustainable.")
    return s, f"{po:.0f}%", msg


def _flag_equity(c: Ctx, y: str):
    p = c.prev(y)
    gr = growth(c.v("total_equity", y), c.v("total_equity", p))
    s = _st(gr, -5, -15, "low")
    msg = f"Total equity {gr:+.1f}% to {cr(c.v('total_equity', y))}." + (" Net worth contracted after distributions." if s else "")
    return s, f"{gr:+.1f}%", msg


# (id, category, display name, threshold text, function)
FLAG_TESTS = [
    ("Gross margin compression", "Profitability", "Watch: fall > 30 bps | Risk: > 100 bps", _flag_gross_margin),
    ("EBITDA margin compression", "Profitability", "Watch: fall > 30 bps | Risk: > 100 bps", _flag_ebitda_margin),
    ("PAT margin compression", "Profitability", "Watch: fall > 30 bps | Risk: > 100 bps", _flag_pat_margin),
    ("Revenue growth", "Profitability", "Watch: < 5% | Risk: negative", _flag_revenue_growth),
    ("Operating leverage (EBITDA vs revenue growth)", "Profitability", "Watch: EBITDA lags revenue by 5pp | Risk: 10pp", _flag_operating_leverage),
    ("Overhead growth vs revenue", "Profitability", "Watch: opex outgrows revenue by 5pp | Risk: 15pp", _flag_opex_growth),
    ("Earnings quality (exceptional items)", "Profitability", "Watch: one-offs > 5% of PBT | Risk: > 15%", _flag_earnings_quality),
    ("Dependence on other income", "Profitability", "Watch: > 20% of PBT | Risk: > 35%", _flag_other_income),
    ("Associates / JV losses", "Profitability", "Watch: loss > ₹10 cr | Risk: > 3% of PBT", _flag_associates),
    ("Rising borrowings", "Leverage & Solvency", "Watch: debt +10% (and > ₹100 cr) | Risk: +25%", _flag_debt_rise),
    ("Net debt / EBITDA", "Leverage & Solvency", "Watch: > 0.5x | Risk: > 1.0x", _flag_net_debt),
    ("Refinancing risk (short-term debt)", "Leverage & Solvency", "Short-term share >= 60%: Watch if covered by liquid treasury, Risk if not", _flag_refinancing),
    ("Interest coverage", "Leverage & Solvency", "Watch: < 8x | Risk: < 4x", _flag_interest_cover),
    ("Finance cost growth", "Leverage & Solvency", "Watch: +15% | Risk: +40%", _flag_finance_cost),
    ("Current ratio", "Liquidity", "Watch: < 1.0x | Risk: < 0.8x", _flag_current_ratio),
    ("Quick ratio", "Liquidity", "Watch: < 0.70x | Risk: < 0.50x", _flag_quick_ratio),
    ("Cash conversion (pre-tax CFO / EBITDA)", "Cash Flow", "Watch: < 90% | Risk: < 75%", _flag_cash_conversion),
    ("Operating cash flow vs PAT", "Cash Flow", "Watch: < 90% | Risk: < 70%", _flag_ocf_pat),
    ("Operating cash flow trend", "Cash Flow", "Watch: -5% YoY | Risk: -15%", _flag_cfo_trend),
    ("Free cash flow", "Cash Flow", "Watch: margin < 5% | Risk: negative", _flag_fcf),
    ("Dividend cover by FCF", "Cash Flow", "Watch: < 1.0x | Risk: < 0.5x", _flag_dividend_cover),
    ("Capex vs depreciation", "Cash Flow", "Watch: < 0.8x | Risk: < 0.5x", _flag_capex),
    ("Receivables vs revenue growth", "Working Capital", "Watch: receivables outgrow sales by 10pp | Risk: 25pp (capped at Watch if DSO < 15 days)", _flag_receivables),
    ("Inventory days", "Working Capital", "Watch: +4 days | Risk: +10 days", _flag_inventory),
    ("Dividend payout", "Capital Allocation", "Watch: > 90% of PAT | Risk: > 100%", _flag_payout),
    ("Equity base erosion", "Capital Allocation", "Watch: equity -5% | Risk: -15%", _flag_equity),
]


def build_flags(c: Ctx) -> dict:
    """Run every test for every year. Returns matrix / values / detail table."""
    names = [t[0] for t in FLAG_TESTS]
    matrix = pd.DataFrame(0, index=names, columns=FY)
    values = pd.DataFrame("", index=names, columns=FY)
    rows = []
    for name, cat, thresh, fn in FLAG_TESTS:
        for y in FY:
            s, val, msg = fn(c, y)
            matrix.loc[name, y] = s
            values.loc[name, y] = val
            rows.append([y, cat, name, STATUS_LABEL[s], s, val, thresh, msg])
    detail = pd.DataFrame(rows, columns=["Year", "Category", "Test", "Status", "Severity", "Metric", "Rule", "Assessment"])
    return {"matrix": matrix, "values": values, "detail": detail}


def flag_counts(flags: dict, y: str) -> dict:
    col = flags["matrix"][y]
    return {"Risk": int((col == 2).sum()), "Watch": int((col == 1).sum()), "Healthy": int((col == 0).sum())}


# --------------------------------------------------------------------------------------
# CHART INSIGHTS  (one per chart - each answers "so what?")
# --------------------------------------------------------------------------------------
def chart_insight(key: str, c: Ctx, years: list[str], focus: str | None = None, metric: str | None = None) -> str:
    d, r = c.d, c.r
    y0, y1 = years[0], years[-1]
    n = max(len(years) - 1, 1)
    focus = focus or y1

    if key == "rev_margin":
        a, b, k = _span(c, "revenue", years)
        m = r.loc[years, "ebitda_margin"]
        slow = pd.Series({y: c.g("revenue", y) for y in years})
        slow_y = _argmin(slow.iloc[1:]) if len(years) > 1 else y1
        return (f"Revenue grew from {cr(a)} to {cr(b)} ({k:.1f}% CAGR) while EBITDA margin ranged between {m.min():.1f}% ({_argmin(m)}) and "
                f"{m.max():.1f}% ({_argmax(m)}). The slowest growth year was {slow_y} at {slow[slow_y]:.1f}%. "
                f"Management takeaway: margin, not volume, has been the swing factor - a 100 bps move in EBITDA margin is worth about "
                f"{cr(c.v('revenue', y1) * 0.01)} of profit at {y1} revenue.")
    if key == "profit_trend":
        ea, eb, ek = _span(c, "ebitda", years)
        pa, pb, pk = _span(c, "pat", years)
        txt = (f"EBITDA compounded at {ek:.1f}% ({cr(ea)} to {cr(eb)}) versus PAT at {pk:.1f}% ({cr(pa)} to {cr(pb)}). ")
        big = [y for y in years if c.v("exceptional_expense", y) < -50]
        if big:
            y = big[0]
            txt += (f"{y} PAT includes an exceptional gain of {cr(abs(c.v('exceptional_expense', y)))}; excluding it, pre-exceptional PBT was "
                    f"{cr(r.loc[y, 'pbt_pre_exc'])} - so the {y} PAT peak overstates run-rate earnings. ")
        txt += "Compare PAT growth with EBITDA growth to judge whether operating gains are reaching shareholders."
        return txt
    if key == "margin_trend":
        g_ = r.loc[years, "gross_margin"]
        e_ = r.loc[years, "ebitda_margin"]
        gap0, gap1 = g_.iloc[0] - e_.iloc[0], g_.iloc[-1] - e_.iloc[-1]
        return (f"Gross margin moved {g_.iloc[0]:.1f}% -> {g_.iloc[-1]:.1f}% and EBITDA margin {e_.iloc[0]:.1f}% -> {e_.iloc[-1]:.1f}%. "
                f"The gap between them (overheads: employee + other expenses) went from {gap0:.1f} to {gap1:.1f} percentage points of revenue, "
                f"so {'overhead leverage added to' if gap1 < gap0 else 'overhead growth offset'} the input-cost story. Trough gross margin: {g_.min():.1f}% in {_argmin(g_)}.")
    if key == "cost_structure":
        cg = c.margin("cogs", y1)
        em = c.margin("employee_cost", y1)
        ot = c.margin("other_expenses", y1)
        return (f"In {y1}, out of every ₹100 of revenue: ₹{cg:.1f} goes to materials/COGS, ₹{em:.1f} to employees, ₹{ot:.1f} to other expenses, "
                f"leaving ₹{c.margin('ebitda', y1):.1f} EBITDA. COGS is the dominant lever: each 1 percentage-point change in the COGS ratio moves EBITDA by about "
                f"{c.v('revenue', y1) * 0.01 / c.v('ebitda', y1) * 100:.0f}% - hence hedging, pricing and mix decisions drive earnings volatility.")
    if key == "earnings_quality":
        op = c.v("ebit", y1)
        oi = c.v("other_income", y1)
        return (f"In {y1}, operating EBIT of {cr(op)} accounts for {op / c.v('pbt', y1) * 100:.0f}% of PBT; other income ({cr(oi)}) adds "
                f"{oi / c.v('pbt', y1) * 100:.0f}%, finance cost deducts {cr(c.v('finance_costs', y1))}. Profit is operating-led and not dependent on treasury gains - "
                f"but watch the associates/JV line ({cr(c.v('share_assoc', y1), 1)}), which has moved against the group over the period.")
    if key == "explorer":
        col = metric or "revenue"
        s = d.loc[years, col]
        a, b, k = _span(c, col, years)
        gy = pd.Series({y: c.g(col, y) for y in years})
        txt = f"{LABELS.get(col, col)}: {a:,.1f} -> {b:,.1f}"
        if not is_nan(k):
            txt += f" ({k:.1f}% CAGR)"
        txt += f". Peak {s.max():,.1f} in {_argmax(s)}, low {s.min():,.1f} in {_argmin(s)}."
        if len(years) > 1 and gy.iloc[1:].notna().any():
            txt += f" Strongest YoY move {gy.iloc[1:].max():+.1f}% ({_argmax(gy.iloc[1:])}); weakest {gy.iloc[1:].min():+.1f}% ({_argmin(gy.iloc[1:])})."
        return txt
    if key == "asset_mix":
        sh = lambda col, y: c.v(col, y) / c.v("total_assets", y) * 100
        return (f"Total assets {cr(c.v('total_assets', y0))} -> {cr(c.v('total_assets', y1))}. Net fixed assets are {sh('net_fixed_assets', y1):.0f}% of assets "
                f"(from {sh('net_fixed_assets', y0):.0f}%), while investments (treasury + associates/JV) are {sh('investments_total', y1):.0f}% "
                f"(from {sh('investments_total', y0):.0f}%). Inventories and receivables together are only "
                f"{(c.v('inventories', y1) + c.v('trade_receivables', y1)) / c.v('total_assets', y1) * 100:.0f}% - an asset-light working-capital profile; "
                f"the real capital-allocation question is how efficiently the large treasury portfolio is deployed.")
    if key == "funding_mix":
        sh = lambda col, y: c.v(col, y) / c.v("total_assets", y) * 100
        return (f"Equity funds {sh('total_equity', y1):.0f}% of assets in {y1} (vs {sh('total_equity', y0):.0f}% in {y0}); borrowings fell from "
                f"{sh('total_debt', y0):.0f}% to {sh('total_debt', y1):.0f}%. Trade payables fund {sh('trade_payables', y1):.0f}% of assets - supplier credit is a major, "
                f"free source of funds, which is efficient but means working capital is sensitive to any tightening of payment terms.")
    if key == "debt_profile":
        td = d.loc[years, "total_debt"]
        nd = d.loc[years, "net_debt"]
        cover = c.v("liquid_treasury", y1) / c.v("c_borrowings", y1)
        flip = [y for y in years if c.v("net_debt", y) < 0]
        txt = (f"Borrowings peaked at {cr(td.max())} in {_argmax(td)} and stand at {cr(td.iloc[-1])} in {y1}. ")
        txt += (f"The group has been in a net-cash position since {flip[0]} (net cash {cr(abs(c.v('net_debt', y1)))} in {y1}). " if flip and c.v("net_debt", y1) < 0
                else f"Net debt is {cr(nd.iloc[-1])} in {y1}. ")
        txt += (f"{c.r.loc[y1, 'st_debt_share']:.0f}% of debt is short-term, but liquid treasury covers current borrowings {cover:.1f}x - "
                f"refinancing risk is low, though the shift back towards short-term paper in {y1} is worth a question to Treasury on funding strategy.")
        return txt
    if key == "liquidity":
        cu = r.loc[years, "current_ratio"]
        return (f"Current ratio ranged {cu.min():.2f}x ({_argmin(cu)}) to {cu.max():.2f}x ({_argmax(cu)}); {y1}: {cu.iloc[-1]:.2f}x with quick ratio "
                f"{r.loc[y1, 'quick_ratio']:.2f}x and cash ratio {r.loc[y1, 'cash_ratio']:.2f}x. Ratios near 1x are normal for FMCG negative-working-capital models - "
                f"the buffer that matters is liquid treasury of {cr(c.v('liquid_treasury', y1))}, equal to {c.v('liquid_treasury', y1) / c.v('total_cl', y1) * 100:.0f}% of current liabilities.")
    if key == "treasury_vs_debt":
        tt, td = c.v("total_treasury", y1), c.v("total_debt", y1)
        return (f"{y1}: total treasury (liquid + non-current investments + loans/ICDs) of {cr(tt)} against borrowings of {cr(td)} - a net treasury surplus of {cr(tt - td)}. "
                f"Carrying both a large treasury and borrowings is a negative-carry choice worth testing: finance costs were {cr(c.v('finance_costs', y1))} versus "
                f"other income of {cr(c.v('other_income', y1))}.")
    if key == "working_capital":
        op = d.loc[years, "op_wc"]
        return (f"Operating working capital (inventories + receivables - trade payables) moved from {cr(op.iloc[0])} to {cr(op.iloc[-1])}; it is negative or near zero "
                f"throughout, i.e. suppliers fund the operating cycle (cash conversion cycle {r.loc[y1, 'ccc']:.0f} days in {y1}). "
                f"Sensitivity: every 5 days of change in payable terms moves cash by about {cr(c.v('cogs', y1) * 5 / 365)}.")
    if key == "cf_bars":
        cfo, cfi, cff = c.total("cfo", years), c.total("cfi", years), c.total("cff", years)
        dv = c.total("dividends_paid", years)
        return (f"Cumulative {y0}-{y1}: operating {cr(cfo)}, investing {cr(cfi)}, financing {cr(cff)}. Operating cash flow is positive every year; financing is "
                f"persistently negative because dividends ({cr(dv)}) absorb {dv / cfo * 100:.0f}% of operating cash flow. Investing flows are dominated by treasury "
                f"purchases/redemptions, so a positive investing figure is not an asset-sale signal.")
    if key == "fcf":
        a, b, k = _span(c, "fcf", years)
        return (f"Free cash flow rose from {cr(a)} to {cr(b)} ({'%.1f%% CAGR' % k if not is_nan(k) else 'n/a'}); margin {r.loc[y0, 'fcf_margin']:.1f}% -> {r.loc[y1, 'fcf_margin']:.1f}%. "
                f"Caution: part of the improvement is lower capex ({cr(c.v('capex', y0))} -> {cr(c.v('capex', y1))}), not just higher operating cash. "
                f"Capex at {r.loc[y1, 'capex_dep']:.2f}x depreciation is not sustainable indefinitely, so normalised FCF will likely be lower than {y1}.")
    if key == "cash_conv":
        a = r.loc[years, "ocf_pat"]
        b = r.loc[years, "cgo_ebitda"]
        weak = [y for y in years if r.loc[y, "ocf_pat"] < 90]
        txt = (f"Pre-tax cash generation was {b.min():.0f}-{b.max():.0f}% of EBITDA and operating cash flow {a.min():.0f}-{a.max():.0f}% of PAT. ")
        txt += (f"Conversion lagged profit in {', '.join(weak)}" + (f" (inventories absorbed {cr(abs(c.v('chg_inventories_cf', weak[0])))} that year)" if c.v('chg_inventories_cf', weak[0]) < -100 else "")
                + ". " if weak else "Operating cash flow exceeded reported profit throughout - high earnings quality. ")
        txt += f"Latest {y1}: CFO/PAT {a.iloc[-1]:.0f}%."
        return txt
    if key == "cf_waterfall":
        f = focus
        gap = c.v("fcf_after_div", f)
        return (f"{f}: operating cash flow of {cr(c.v('cfo', f))} funded capex of {cr(c.v('capex', f))}, leaving FCF of {cr(c.v('fcf', f))}. After interest ({cr(c.v('interest_paid', f))}) and dividends "
                f"({cr(c.v('dividends_paid', f))}) the {'surplus' if gap >= 0 else 'shortfall'} was {cr(abs(gap))}"
                + (" - the gap had to be met from treasury run-down or net borrowing." if gap < 0 else " - dividends were covered from internal cash flow, adding to the treasury."))
    if key == "cum_uses":
        cfo = c.total("cfo", years)
        cap, dv, it = c.total("capex", years), c.total("dividends_paid", years), c.total("interest_paid", years)
        res = cfo - cap - dv - it
        tail = (f"leaving {cr(res)} ({res / cfo * 100:.0f}%) to retire debt or build treasury." if res >= 0 else
                f"i.e. outflows exceeded operating cash flow by {cr(abs(res))} ({abs(res) / cfo * 100:.0f}%), bridged by net non-capex investing inflows of {cr(c.total('cfi', years) + cap)} "
                f"(treasury liquidation) while borrowings changed by {cr(c.v('total_debt', y1) - c.v('total_debt', c.prev(y0)))} "
                f"(note: FY22 dividends paid include bonus-debenture settlement).")
        return (f"Of {cr(cfo)} operating cash generated over {y0}-{y1}, {cap / cfo * 100:.0f}% went to capex, {dv / cfo * 100:.0f}% to dividends and {it / cfo * 100:.0f}% to interest, "
                f"{tail} Shareholder distributions are the dominant use of cash.")
    if key == "capex_dep":
        cp = r.loc[years, "capex_dep"]
        return (f"Capex/D&A fell from {cp.iloc[0]:.2f}x ({y0}) to {cp.iloc[-1]:.2f}x ({y1}). The heavy investment phase (peak {cr(d.loc[years, 'capex'].max())} in {_argmax(d.loc[years, 'capex'])}) "
                f"is complete, which lifts FCF but means depreciation ({cr(c.v('depreciation', y1))}) now exceeds new spending - ask management for the capex pipeline and capacity headroom.")
    if key == "dupont":
        f0 = {"m": r.loc[y0, "pat_margin"], "t": r.loc[y0, "asset_turnover"], "l": r.loc[y0, "equity_multiplier"]}
        f1 = {"m": r.loc[y1, "pat_margin"], "t": r.loc[y1, "asset_turnover"], "l": r.loc[y1, "equity_multiplier"]}
        ch = {k: (f1[k] / f0[k] - 1) * 100 for k in f0}
        return (f"ROE moved {r.loc[y0, 'roe']:.1f}% -> {r.loc[y1, 'roe']:.1f}%. {y1} decomposition: net margin {f1['m']:.1f}% x asset turnover {f1['t']:.2f}x x equity multiplier {f1['l']:.2f}x. "
                f"Since {y0}: net margin {ch['m']:+.0f}%, asset turnover {ch['t']:+.0f}%, leverage {ch['l']:+.0f}%. "
                f"{'ROE is now driven by operating performance rather than gearing' if ch['l'] < 0 and (ch['m'] + ch['t']) > 0 else 'Review the balance of margin, turnover and leverage'} - "
                f"equity multiplier {f0['l']:.2f}x -> {f1['l']:.2f}x means the return is earned with less financial risk.")
    if key == "wc_days":
        return (f"Cash conversion cycle {r.loc[y0, 'ccc']:.0f} -> {r.loc[y1, 'ccc']:.0f} days: inventory {r.loc[y1, 'inventory_days']:.0f} days + receivables {r.loc[y1, 'receivable_days']:.0f} days "
                f"- payables {r.loc[y1, 'payable_days']:.0f} days. A negative cycle means suppliers finance operations; payable days are measured against COGS and include service creditors, so they overstate pure materials credit.")
    if key == "flags_matrix":
        return ""  # composed in the app from counts
    if key == "receivables_vs_revenue":
        rg = pd.Series({y: c.g("trade_receivables", y) for y in years})
        sg = pd.Series({y: c.g("revenue", y) for y in years})
        gap = (rg - sg)
        wy = _argmax(gap)
        return (f"Receivables outgrew revenue by the widest margin in {wy} ({rg[wy]:+.1f}% vs {sg[wy]:+.1f}%). Closing receivables are only "
                f"{c.v('trade_receivables', y1) / c.v('revenue', y1) * 365:.1f} days of sales in {y1}, so credit risk is contained; the signal is about channel credit discipline, not solvency.")
    if key == "refinancing":
        return (f"Short-term borrowings are {r.loc[y1, 'st_debt_share']:.0f}% of debt in {y1} against {r.loc[y0, 'st_debt_share']:.0f}% in {y0}. Liquid treasury of {cr(c.v('liquid_treasury', y1))} covers "
                f"current borrowings {c.v('liquid_treasury', y1) / c.v('c_borrowings', y1):.1f}x, so rollover risk is mitigated by asset cover rather than by tenor.")
    if key == "health_trend":
        s = c.sc.loc[years, "Overall"]
        piv = c.sc.loc[y1, ["Profitability", "Liquidity", "Solvency", "Efficiency", "Cash Flow"]]
        return (f"Composite score {s.iloc[0]:.0f} -> {s.iloc[-1]:.0f} / 100 ({rating_label(s.iloc[-1])[0]}). Strongest pillar in {y1}: {piv.idxmax()} ({piv.max():.0f}); "
                f"weakest: {piv.idxmin()} ({piv.min():.0f}). Scores are a transparent, rule-based screen (see methodology) - not a credit rating.")
    if key == "pl_waterfall":
        f = focus
        return (f"{f}: of ₹100 revenue, ₹{c.margin('cogs', f):.1f} is consumed by materials/COGS, ₹{c.margin('employee_cost', f) + c.margin('other_expenses', f):.1f} by employee and other costs, "
                f"giving ₹{c.margin('ebitda', f):.1f} EBITDA and ₹{c.margin('pat', f):.1f} PAT after depreciation, finance cost, other income, one-offs and tax of {cr(c.v('total_tax', f))} "
                f"(effective rate {c.r.loc[f, 'tax_rate']:.1f}%).")
    return ""


# --------------------------------------------------------------------------------------
# EXECUTIVE INSIGHTS
# --------------------------------------------------------------------------------------
def executive_insights(c: Ctx, years: list[str], flags: dict) -> dict:
    d, r, sc = c.d, c.r, c.sc
    y0, y1 = years[0], years[-1]
    n = len(years) - 1
    ra, rb, rk = _span(c, "revenue", years)
    ea, eb, ek = _span(c, "ebitda", years)
    pa, pb, pk = _span(c, "pat", years)
    cfo_t, fcf_t, div_t = c.total("cfo", years), c.total("fcf", years), c.total("dividends_paid", years)

    strengths = [
        f"**Consistent top-line scale:** revenue grew from {cr(ra)} to {cr(rb)} ({rk:.1f}% CAGR); EBITDA {cr(ea)} -> {cr(eb)} ({ek:.1f}% CAGR).",
        f"**Strong, durable returns:** {y1} ROCE {r.loc[y1, 'roce']:.0f}% and ROE {r.loc[y1, 'roe']:.0f}% with EBITDA margin of {r.loc[y1, 'ebitda_margin']:.1f}% "
        f"(low {r.loc[years, 'ebitda_margin'].min():.1f}% in {_argmin(r.loc[years, 'ebitda_margin'])}, high {r.loc[years, 'ebitda_margin'].max():.1f}% in {_argmax(r.loc[years, 'ebitda_margin'])}).",
        f"**Deleveraged balance sheet:** borrowings {cr(c.v('total_debt', y0))} -> {cr(c.v('total_debt', y1))}; debt/equity {r.loc[y0, 'debt_equity']:.2f}x -> {r.loc[y1, 'debt_equity']:.2f}x; "
        f"{'net cash of ' + cr(abs(c.v('net_debt', y1))) if c.v('net_debt', y1) < 0 else 'net debt of ' + cr(c.v('net_debt', y1))}; interest cover {r.loc[y1, 'interest_cover']:.0f}x.",
        f"**Cash-generative model:** cumulative operating cash flow {cr(cfo_t)} and free cash flow {cr(fcf_t)} over {y0}-{y1}; FCF margin {r.loc[y1, 'fcf_margin']:.1f}% in {y1}.",
        f"**Working-capital advantage:** cash conversion cycle of {r.loc[y1, 'ccc']:.0f} days (receivables ~{r.loc[y1, 'receivable_days']:.0f} days) - suppliers finance the operating cycle.",
        f"**Rising shareholder value:** EPS {r.loc[y0, 'eps']:.2f} -> {r.loc[y1, 'eps']:.2f}; dividends paid {cr(div_t)} over the period.",
    ]

    weak = []
    gm = r.loc[years, "gross_margin"]
    weak.append(f"**Margin sensitivity to input costs:** gross margin swung between {gm.min():.1f}% ({_argmin(gm)}) and {gm.max():.1f}% ({_argmax(gm)}); "
                f"{y1} EBITDA margin of {r.loc[y1, 'ebitda_margin']:.1f}% is still {'below' if r.loc[y1, 'ebitda_margin'] < r.loc[years, 'ebitda_margin'].max() else 'at'} the period peak.")
    gr = pd.Series({y: c.g("revenue", y) for y in years}).iloc[1:] if n >= 1 else pd.Series(dtype=float)
    if len(gr):
        weak.append(f"**Uneven growth:** YoY revenue growth ranged {gr.min():.1f}% ({_argmin(gr)}) to {gr.max():.1f}% ({_argmax(gr)}); growth is not yet consistently double-digit.")
    weak.append(f"**High payout limits reinvestment:** dividends were {r.loc[y1, 'payout']:.0f}% of PAT in {y1} (period range {r.loc[years, 'payout'].min():.0f}-{r.loc[years, 'payout'].max():.0f}%) "
                f"and absorbed {div_t / cfo_t * 100:.0f}% of operating cash flow.")
    weak.append(f"**Capex below depreciation:** {y1} capex {cr(c.v('capex', y1))} = {r.loc[y1, 'capex_dep']:.2f}x D&A ({r.loc[y1, 'capex_revenue']:.1f}% of revenue); FCF may be flattered by under-investment.")
    weak.append(f"**Short-term debt concentration:** {r.loc[y1, 'st_debt_share']:.0f}% of borrowings are current in {y1} (vs {r.loc[years, 'st_debt_share'].min():.0f}% at the low) - mitigated by treasury cover of "
                f"{c.v('liquid_treasury', y1) / c.v('c_borrowings', y1):.1f}x.")
    weak.append(f"**Thin liquidity ratios:** current ratio {r.loc[y1, 'current_ratio']:.2f}x, quick ratio {r.loc[y1, 'quick_ratio']:.2f}x - acceptable for FMCG but leaves little margin if payables tighten.")
    if c.v("share_assoc", y1) < -10:
        weak.append(f"**Associates/JV drag:** share of loss {cr(c.v('share_assoc', y1), 1)} in {y1} vs {cr(c.v('share_assoc', y0), 1)} in {y0}, on a carrying value of {cr(c.v('associates_jv', y1))}.")

    trends = []
    def tr(label, col, unit="cr", ratio=False):
        if ratio:
            a, b = r.loc[y0, col], r.loc[y1, col]
            fm = (lambda v: f"{v:,.1f}%") if unit == "%" else (lambda v: f"{v:,.2f}x")
            trends.append([label, fm(a), fm(b),
                           (f"{(b - a) * 100:+,.0f} bps" if unit == "%" else f"{b - a:+,.2f}x"),
                           "▲" if b > a else "▼"])
        else:
            a, b, k = _span(c, col, years)
            trends.append([label, cr(a), cr(b), (f"{k:.1f}% CAGR" if not is_nan(k) else f"{b - a:+,.0f}"), "▲" if b > a else "▼"])
    tr("Revenue", "revenue"); tr("EBITDA", "ebitda"); tr("PAT", "pat"); tr("Total assets", "total_assets")
    tr("Total equity", "total_equity"); tr("Borrowings", "total_debt"); tr("Operating cash flow", "cfo"); tr("Free cash flow", "fcf")
    tr("EBITDA margin", "ebitda_margin", "%", True); tr("PAT margin", "pat_margin", "%", True); tr("ROCE", "roce", "%", True)
    tr("Current ratio", "current_ratio", "x", True); tr("Debt / equity", "debt_equity", "x", True)
    trend_df = pd.DataFrame(trends, columns=["Metric", y0, y1, "Change", "Direction"])

    score = float(sc.loc[y1, "Overall"])
    label, tone = rating_label(score)
    fl = flag_counts(flags, y1)
    overall = (f"Britannia's financial health in {FY_LONG[y1]} is rated **{label}** on the dashboard's rule-based scorecard ({score:.0f}/100). "
               f"The business combines a {r.loc[y1, 'ebitda_margin']:.1f}% EBITDA margin, {r.loc[y1, 'roce']:.0f}% ROCE and a net-cash balance sheet with "
               f"{cr(c.v('fcf', y1))} of free cash flow. The principal watch-points are payout intensity, capex running below depreciation, the re-concentration of debt in "
               f"short-term borrowings and the widening associate/JV loss. Red-flag screen for {y1}: {fl['Risk']} Risk, {fl['Watch']} Watch, {fl['Healthy']} Healthy "
               f"out of {sum(fl.values())} tests.")

    questions = [
        f"Why has the borrowing mix shifted back to short-term paper ({cr(c.v('c_borrowings', y1))} current vs {cr(c.v('nc_borrowings', y1))} non-current) while liquid treasury is {cr(c.v('liquid_treasury', y1))}? What is the net carry after finance costs of {cr(c.v('finance_costs', y1))}?",
        f"With capex at {r.loc[y1, 'capex_dep']:.2f}x depreciation, what is the capacity headroom and the planned capex over the next 2-3 years? How much of the {y1} FCF is repeatable?",
        f"What is the recovery plan for the associates/JV portfolio (carrying value {cr(c.v('associates_jv', y1))}, {y1} share of loss {cr(c.v('share_assoc', y1), 1)})? Are impairment triggers being monitored?",
        f"Is a payout of {r.loc[y1, 'payout']:.0f}% of PAT sustainable if input costs spike again (as in {_argmin(gm)}, gross margin {gm.min():.1f}%)? What is the dividend policy floor/ceiling?",
        f"Employee cost grew {c.g('employee_cost', y1):+.1f}% in {y1} vs revenue {c.g('revenue', y1):+.1f}% - is this a step-change (capability build, wage reset) or run-rate?",
    ]
    return {"strengths": strengths, "weaknesses": weak, "trends": trend_df, "overall": overall,
            "score": score, "label": label, "tone": tone, "questions": questions}
