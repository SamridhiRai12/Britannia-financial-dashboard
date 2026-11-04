"""
Ratio engine: calculations, formulas, interpretation text and the transparent health-score model.
All ratios are computed from the verified dataset in data.py (no external inputs).

Averages: ROE, ROA, ROCE, asset turnover and the working-capital days use the AVERAGE of opening and
closing balances. FY22 uses the FY21 closing balance (taken from the FY2021-22 report) as its opening.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fin_data import FY, load_financials


# --------------------------------------------------------------------------------------
# CALCULATION
# --------------------------------------------------------------------------------------
def _avg(s: pd.Series) -> pd.Series:
    return (s + s.shift(1)) / 2.0


def compute_ratios() -> pd.DataFrame:
    """Return ratios for FY22..FY26 (rows = FY, columns = ratio keys)."""
    d = load_financials(include_base=True)
    r = pd.DataFrame(index=d.index)

    avg_assets, avg_equity = _avg(d.total_assets), _avg(d.total_equity)
    avg_ce = _avg(d.capital_employed)
    avg_rec, avg_inv, avg_pay = _avg(d.trade_receivables), _avg(d.inventories), _avg(d.trade_payables)

    # ---- Profitability
    r["gross_margin"] = d.gross_profit / d.revenue * 100
    r["ebitda_margin"] = d.ebitda / d.revenue * 100
    r["ebit_margin"] = d.ebit / d.revenue * 100
    r["pbt_margin"] = d.pbt / d.revenue * 100
    r["pat_margin"] = d.pat / d.revenue * 100
    r["pbt_pre_exc"] = d.pbt + d.exceptional_expense          # PBT before exceptional items (₹ cr)
    r["pbt_pre_exc_margin"] = r.pbt_pre_exc / d.revenue * 100
    r["roe"] = d.pat / avg_equity * 100
    r["roa"] = d.pat / avg_assets * 100
    r["roce"] = (d.pbt + d.finance_costs) / avg_ce * 100
    r["eps"] = d.eps
    r["payout"] = d.dividends_declared / d.pat * 100
    r["other_income_share"] = d.other_income / d.pbt * 100
    r["tax_rate"] = d.total_tax / d.pbt * 100
    # ---- Liquidity
    r["current_ratio"] = d.total_ca / d.total_cl
    r["quick_ratio"] = (d.total_ca - d.inventories) / d.total_cl
    r["cash_ratio"] = d.liquid_treasury / d.total_cl
    r["nwc"] = d.nwc
    r["ocf_cl"] = d.cfo / d.total_cl
    # ---- Solvency
    r["debt_equity"] = d.total_debt / d.total_equity
    r["net_debt_ebitda"] = d.net_debt / d.ebitda
    r["debt_ebitda"] = d.total_debt / d.ebitda
    r["interest_cover"] = d.ebit / d.finance_costs
    r["pbit_cover"] = (d.pbt + d.finance_costs) / d.finance_costs
    r["liab_equity"] = d.total_liabilities / d.total_equity
    r["equity_ratio"] = d.total_equity / d.total_assets * 100
    r["debt_assets"] = d.total_debt / d.total_assets * 100
    r["st_debt_share"] = d.c_borrowings / d.total_debt * 100
    # ---- Efficiency
    r["asset_turnover"] = d.revenue / avg_assets
    r["fixed_asset_turnover"] = d.revenue / (d.ppe + d.cwip)
    r["receivable_days"] = avg_rec / d.revenue * 365
    r["inventory_days"] = avg_inv / d.cogs * 365
    r["payable_days"] = avg_pay / d.cogs * 365
    r["ccc"] = r.inventory_days + r.receivable_days - r.payable_days
    r["equity_multiplier"] = avg_assets / avg_equity
    # ---- Cash-flow quality
    r["cgo_ebitda"] = d.cash_gen_ops / d.ebitda * 100
    r["ocf_ebitda"] = d.cfo / d.ebitda * 100
    r["ocf_pat"] = d.cfo / d.pat * 100
    r["fcf"] = d.fcf
    r["fcf_margin"] = d.fcf / d.revenue * 100
    r["fcf_pat"] = d.fcf / d.pat * 100
    r["capex_revenue"] = d.capex / d.revenue * 100
    r["capex_dep"] = d.capex / d.depreciation
    r["fcf_div_cover"] = d.fcf / d.dividends_paid
    return r.loc[FY]


# --------------------------------------------------------------------------------------
# METADATA: formulas, units, direction, meaning
# --------------------------------------------------------------------------------------
# hib: True = higher is better, False = lower is better, None = neutral / context-dependent
RATIO_META: dict[str, dict] = {
    # ---------------- Profitability ----------------
    "gross_margin": dict(name="Gross margin", cat="Profitability", unit="%", hib=True,
        formula="(Revenue - COGS) / Revenue x 100;  COGS = materials + stock-in-trade purchases +/- inventory change",
        meaning="Pricing power and input-cost absorption. Falls when commodity costs rise faster than prices."),
    "ebitda_margin": dict(name="EBITDA margin", cat="Profitability", unit="%", hib=True,
        formula="Operating EBITDA / Revenue from operations x 100",
        meaning="Core operating profitability before depreciation, interest and treasury income."),
    "ebit_margin": dict(name="EBIT margin", cat="Profitability", unit="%", hib=True,
        formula="(EBITDA - Depreciation & amortisation) / Revenue x 100",
        meaning="Operating profitability after charging the capital base used."),
    "pbt_margin": dict(name="PBT margin", cat="Profitability", unit="%", hib=True,
        formula="Profit before tax / Revenue x 100",
        meaning="Reported pre-tax profitability (includes other income and exceptional items)."),
    "pbt_pre_exc_margin": dict(name="PBT margin (pre-exceptional)", cat="Profitability", unit="%", hib=True,
        formula="(PBT + exceptional expense) / Revenue x 100",
        meaning="Pre-tax margin stripped of one-offs - the cleanest read of sustainable earnings power."),
    "pat_margin": dict(name="PAT margin", cat="Profitability", unit="%", hib=True,
        formula="Profit after tax / Revenue x 100",
        meaning="Share of each rupee of revenue that reaches shareholders after all costs and tax."),
    "roe": dict(name="Return on equity (ROE)", cat="Profitability", unit="%", hib=True,
        formula="PAT / Average total equity x 100",
        meaning="Return generated on shareholders' funds; very high ROE can partly reflect a thin equity base after large payouts."),
    "roa": dict(name="Return on assets (ROA)", cat="Profitability", unit="%", hib=True,
        formula="PAT / Average total assets x 100",
        meaning="Profit generated per rupee of total assets, independent of financing mix."),
    "roce": dict(name="Return on capital employed (ROCE)", cat="Profitability", unit="%", hib=True,
        formula="(PBT + Finance costs) / Average capital employed x 100;  Capital employed = Total assets - Current liabilities",
        meaning="Return on long-term capital (equity + debt). Compare with cost of capital - Britannia comfortably exceeds it."),
    "eps": dict(name="Earnings per share (₹)", cat="Profitability", unit="₹", hib=True,
        formula="PAT attributable to owners / Weighted average shares (24.09 crore) - as reported",
        meaning="Per-share earnings available to equity holders."),
    "payout": dict(name="Dividend payout ratio", cat="Profitability", unit="%", hib=None,
        formula="Dividends recognised in equity / PAT x 100",
        meaning="Share of profit distributed. Sustained payout above ~80-90% leaves limited internal funding for growth."),
    "tax_rate": dict(name="Effective tax rate", cat="Profitability", unit="%", hib=None,
        formula="Total tax expense / PBT x 100",
        meaning="Tax burden on pre-tax profit; swings with exceptional items and deferred-tax movements."),
    "other_income_share": dict(name="Other income as % of PBT", cat="Profitability", unit="%", hib=False,
        formula="Other income / PBT x 100",
        meaning="Dependence on treasury/other income for profit; a low share means earnings are operating-led."),
    # ---------------- Liquidity ----------------
    "current_ratio": dict(name="Current ratio", cat="Liquidity", unit="x", hib=True,
        formula="Current assets / Current liabilities",
        meaning="Ability to meet 12-month obligations. FMCG firms with negative working capital often run near 1.0x."),
    "quick_ratio": dict(name="Quick ratio", cat="Liquidity", unit="x", hib=True,
        formula="(Current assets - Inventories) / Current liabilities",
        meaning="Liquidity excluding stock; tests reliance on inventory liquidation."),
    "cash_ratio": dict(name="Cash ratio (incl. current investments)", cat="Liquidity", unit="x", hib=True,
        formula="(Cash + Other bank balances + Current investments) / Current liabilities",
        meaning="Most conservative liquidity test - immediately deployable treasury versus short-term obligations."),
    "nwc": dict(name="Net working capital (₹ cr)", cat="Liquidity", unit="₹ cr", hib=True,
        formula="Current assets - Current liabilities",
        meaning="Surplus of short-term assets over short-term obligations."),
    "ocf_cl": dict(name="Operating cash flow ratio", cat="Liquidity", unit="x", hib=True,
        formula="Net cash from operations / Current liabilities",
        meaning="Share of current liabilities covered by a year's operating cash generation."),
    # ---------------- Solvency ----------------
    "debt_equity": dict(name="Debt-to-equity", cat="Solvency", unit="x", hib=False,
        formula="Total borrowings (current + non-current) / Total equity",
        meaning="Financial leverage. Below 0.5x is conservative for a stable-cash-flow consumer business."),
    "net_debt_ebitda": dict(name="Net debt / EBITDA", cat="Solvency", unit="x", hib=False,
        formula="(Borrowings - Cash - Bank balances - Current investments) / EBITDA",
        meaning="Years of EBITDA needed to repay net borrowings; negative = net cash."),
    "debt_ebitda": dict(name="Gross debt / EBITDA", cat="Solvency", unit="x", hib=False,
        formula="Total borrowings / EBITDA",
        meaning="Years of EBITDA to repay gross borrowings, ignoring treasury assets."),
    "interest_cover": dict(name="Interest coverage (EBIT / finance cost)", cat="Solvency", unit="x", hib=True,
        formula="Operating EBIT / Finance costs",
        meaning="Margin of safety on interest. Above ~5x is comfortable; Britannia is far above."),
    "pbit_cover": dict(name="Interest coverage (PBIT basis)", cat="Solvency", unit="x", hib=True,
        formula="(PBT + Finance costs) / Finance costs",
        meaning="Coverage including other income and exceptional items (reported basis)."),
    "liab_equity": dict(name="Total liabilities / equity", cat="Solvency", unit="x", hib=False,
        formula="Total liabilities / Total equity",
        meaning="All outside claims relative to owners' funds (includes trade creditors, so structurally higher for FMCG)."),
    "equity_ratio": dict(name="Equity ratio", cat="Solvency", unit="%", hib=True,
        formula="Total equity / Total assets x 100",
        meaning="Proportion of assets financed by shareholders."),
    "debt_assets": dict(name="Debt-to-assets", cat="Solvency", unit="%", hib=False,
        formula="Total borrowings / Total assets x 100",
        meaning="Share of the asset base financed by borrowings."),
    "st_debt_share": dict(name="Short-term debt share", cat="Solvency", unit="%", hib=False,
        formula="Current borrowings / Total borrowings x 100",
        meaning="Refinancing exposure; high shares are acceptable only if covered by liquid treasury."),
    # ---------------- Efficiency ----------------
    "asset_turnover": dict(name="Asset turnover", cat="Efficiency", unit="x", hib=True,
        formula="Revenue / Average total assets",
        meaning="Revenue generated per rupee of assets."),
    "fixed_asset_turnover": dict(name="Fixed asset turnover", cat="Efficiency", unit="x", hib=True,
        formula="Revenue / (PPE + Capital WIP)",
        meaning="Productivity of the manufacturing base; capex ahead of revenue depresses it temporarily."),
    "receivable_days": dict(name="Receivable days (DSO)", cat="Efficiency", unit="days", hib=False,
        formula="Average trade receivables / Revenue x 365",
        meaning="Credit period extended to trade; Britannia sells largely on short credit."),
    "inventory_days": dict(name="Inventory days (DIO)", cat="Efficiency", unit="days", hib=False,
        formula="Average inventories / COGS x 365",
        meaning="Days of stock held; rises with raw-material forward buying or slow-moving stock."),
    "payable_days": dict(name="Payable days (DPO)", cat="Efficiency", unit="days", hib=None,
        formula="Average trade payables / COGS x 365 (payables include service creditors, so DPO is overstated vs a pure materials measure)",
        meaning="Supplier credit enjoyed. Higher DPO funds working capital but should not stretch supplier relationships."),
    "ccc": dict(name="Cash conversion cycle", cat="Efficiency", unit="days", hib=False,
        formula="Inventory days + Receivable days - Payable days",
        meaning="Net days cash is tied up; negative means suppliers finance the operating cycle."),
    "equity_multiplier": dict(name="Equity multiplier (DuPont)", cat="Efficiency", unit="x", hib=None,
        formula="Average total assets / Average total equity",
        meaning="Leverage component of ROE under the DuPont decomposition."),
    # ---------------- Cash-flow quality ----------------
    "cgo_ebitda": dict(name="Pre-tax cash conversion (cash from ops / EBITDA)", cat="Cash Flow", unit="%", hib=True,
        formula="Cash generated from operations (before tax) / Operating EBITDA x 100",
        meaning="Share of EBITDA that turns into cash after working-capital movements but before tax. Near or above 90-100% indicates high earnings quality."),
    "ocf_ebitda": dict(name="Post-tax cash conversion (CFO / EBITDA)", cat="Cash Flow", unit="%", hib=True,
        formula="Net cash from operations (after tax) / Operating EBITDA x 100",
        meaning="Cash left after tax and working capital. With a ~25% tax burden, ~75% is 'par'; materially lower signals working-capital leakage."),
    "ocf_pat": dict(name="CFO / PAT", cat="Cash Flow", unit="%", hib=True,
        formula="Net cash from operations / PAT x 100",
        meaning="Are accounting profits backed by cash? Persistent values below 100% warrant scrutiny."),
    "fcf": dict(name="Free cash flow (₹ cr)", cat="Cash Flow", unit="₹ cr", hib=True,
        formula="Net cash from operations - Capital expenditure",
        meaning="Cash available to investors after sustaining and growing the asset base."),
    "fcf_margin": dict(name="FCF margin", cat="Cash Flow", unit="%", hib=True,
        formula="Free cash flow / Revenue x 100",
        meaning="Free cash generated per rupee of revenue."),
    "fcf_pat": dict(name="FCF / PAT", cat="Cash Flow", unit="%", hib=True,
        formula="Free cash flow / PAT x 100",
        meaning="Free-cash realisation of reported profit."),
    "capex_revenue": dict(name="Capex intensity", cat="Cash Flow", unit="%", hib=None,
        formula="Capital expenditure / Revenue x 100",
        meaning="Investment appetite relative to scale."),
    "capex_dep": dict(name="Capex / depreciation", cat="Cash Flow", unit="x", hib=None,
        formula="Capital expenditure / Depreciation & amortisation",
        meaning="Below 1.0x means the asset base is being consumed faster than replaced."),
    "fcf_div_cover": dict(name="Dividend cover by FCF", cat="Cash Flow", unit="x", hib=True,
        formula="Free cash flow / Dividends paid (cash flow statement)",
        meaning="Can internally generated cash fund the dividend? Below 1.0x requires treasury run-down or borrowing."),
}
CATEGORIES = ["Profitability", "Liquidity", "Solvency", "Efficiency", "Cash Flow"]

# Headline ratios shown in each category tab (order matters)
CATEGORY_KEYS: dict[str, list[str]] = {
    c: [k for k, m in RATIO_META.items() if m["cat"] == c] for c in CATEGORIES
}


# --------------------------------------------------------------------------------------
# FORMATTING
# --------------------------------------------------------------------------------------
def fmt_value(key: str, v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    u = RATIO_META[key]["unit"]
    if u == "%":
        return f"{v:,.1f}%"
    if u == "x":
        return f"{v:,.2f}x"
    if u == "days":
        return f"{v:,.0f} days"
    if u == "₹":
        return f"₹{v:,.2f}"
    return f"₹{v:,.0f} cr"


def trend_sentence(key: str, series: pd.Series) -> str:
    """Dynamic one-line reading of the last move + five-year range for a ratio."""
    m = RATIO_META[key]
    s = series.dropna()
    if len(s) < 2:
        return "Insufficient history."
    last, prev = s.iloc[-1], s.iloc[-2]
    delta = last - prev
    unit = m["unit"]
    if unit == "%":
        dtxt = f"{delta * 100:+,.0f} bps"
        small = abs(delta) < 0.25
    elif unit == "days":
        dtxt = f"{delta:+,.1f} days"
        small = abs(delta) < 1.0
    elif unit == "₹ cr":
        dtxt = f"{delta:+,.0f} cr"
        small = abs(delta) < 0.02 * max(abs(prev), 1)
    else:
        dtxt = f"{delta:+,.2f}"
        small = abs(delta) < 0.02 * max(abs(prev), 0.5)
    if small:
        verdict = "broadly stable"
    elif m["hib"] is None:
        verdict = "higher" if delta > 0 else "lower"
    else:
        improving = (delta > 0) == bool(m["hib"])
        verdict = "improving" if improving else "deteriorating"
    lo, hi = s.min(), s.max()
    return (f"{s.index[-1]}: {fmt_value(key, last)} ({dtxt} vs {s.index[-2]}) - {verdict}. "
            f"5-yr range {fmt_value(key, lo)} to {fmt_value(key, hi)}; average {fmt_value(key, s.mean())}.")


# --------------------------------------------------------------------------------------
# HEALTH-SCORE MODEL  (transparent, rule-based; NOT a credit rating)
# --------------------------------------------------------------------------------------
# key: (value that scores 0, value that scores 100). Linear in between, clipped to 0-100.
SCORE_RULES: dict[str, dict[str, tuple[float, float]]] = {
    "Profitability": {"ebitda_margin": (10, 20), "pat_margin": (6, 14), "roe": (10, 60), "roce": (15, 70)},
    "Liquidity":     {"current_ratio": (0.8, 1.3), "quick_ratio": (0.5, 1.0), "cash_ratio": (0.15, 0.5)},
    "Solvency":      {"debt_equity": (1.0, 0.2), "net_debt_ebitda": (2.0, 0.0), "interest_cover": (3, 20)},
    "Efficiency":    {"asset_turnover": (1.0, 2.0), "ccc": (45, 0), "inventory_days": (70, 30)},
    "Cash Flow":     {"cgo_ebitda": (70, 100), "fcf_margin": (0, 12), "fcf_div_cover": (0.5, 1.3), "ocf_pat": (70, 110)},
}
PILLAR_WEIGHTS = {"Profitability": 0.30, "Liquidity": 0.15, "Solvency": 0.20, "Efficiency": 0.15, "Cash Flow": 0.20}


def _score(v: float, zero: float, hundred: float) -> float:
    if v is None or np.isnan(v):
        return np.nan
    return float(np.clip((v - zero) / (hundred - zero) * 100.0, 0, 100))


def indicator_scores(r: pd.DataFrame) -> pd.DataFrame:
    """0-100 score for every indicator in SCORE_RULES (rows = FY)."""
    out = {}
    for pillar, rules in SCORE_RULES.items():
        for k, (z, h) in rules.items():
            out[k] = r[k].apply(lambda v, z=z, h=h: _score(v, z, h))
    return pd.DataFrame(out, index=r.index)


def health_scores(r: pd.DataFrame) -> pd.DataFrame:
    """Pillar scores + overall (weighted) score per year."""
    ind = indicator_scores(r)
    res = pd.DataFrame(index=r.index)
    for pillar, rules in SCORE_RULES.items():
        res[pillar] = ind[list(rules.keys())].mean(axis=1)
    res["Overall"] = sum(res[p] * w for p, w in PILLAR_WEIGHTS.items())
    return res


def rating_label(score: float) -> tuple[str, str]:
    """(label, colour-token) for an overall score."""
    if score >= 80:
        return "Excellent", "good"
    if score >= 65:
        return "Strong", "good"
    if score >= 50:
        return "Sound", "neutral"
    if score >= 35:
        return "Watchful", "warn"
    return "Stressed", "bad"


def band(key: str, v: float) -> str:
    """Strong / Adequate / Weak band for indicators that have scoring rules; else '-'."""
    for rules in SCORE_RULES.values():
        if key in rules:
            z, h = rules[key]
            s = _score(v, z, h)
            if np.isnan(s):
                return "-"
            return "Strong" if s >= 70 else ("Adequate" if s >= 40 else "Weak")
    return "-"


def interpret(key: str, r: pd.DataFrame, years: list[str]) -> str:
    """Full dynamic interpretation: meaning + trend + band for the latest selected year."""
    s = r.loc[years, key]
    b = band(key, s.iloc[-1])
    btxt = f" Assessment: {b}." if b != "-" else ""
    return f"{RATIO_META[key]['meaning']} {trend_sentence(key, s)}{btxt}"
