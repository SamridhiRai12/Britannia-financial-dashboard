"""
Britannia Industries Limited - verified consolidated financial dataset (FY2021-22 to FY2025-26)
================================================================================================
All figures: ₹ crore, CONSOLIDATED, hand-extracted from the five annual reports supplied
(Annual Reports 2021-22, 2022-23, 2023-24, 2024-25, 2025-26). Nothing is estimated or fabricated.

Basis of preparation
--------------------
* Each year uses the MOST RECENT presentation of that year found in the supplied reports
  (i.e. the comparative column of the following year's report, where one exists).  This is the
  normal analyst convention because it gives like-for-like comparability.  Every place where
  the latest presentation differs from the figure originally published is listed in
  RESTATEMENT_LOG, and the original figures are retained there.
* FY2020-21 (BASE_FY21) is taken from the comparative column of the FY2021-22 report.  It is used
  ONLY as an opening balance / base year (FY22 growth rates and FY22 average-balance ratios).
  It is not charted as one of the five analysed years.
* Sign convention: expenses are stored as positive numbers; `exceptional_expense` is signed
  (negative = exceptional INCOME, e.g. FY23 gain on sale of investments).
"""
from __future__ import annotations

import pandas as pd

FY = ["FY22", "FY23", "FY24", "FY25", "FY26"]
FY_ALL = ["FY21"] + FY
FY_LONG = {
    "FY21": "FY2020-21", "FY22": "FY2021-22", "FY23": "FY2022-23",
    "FY24": "FY2023-24", "FY25": "FY2024-25", "FY26": "FY2025-26",
}
SHARES_OUTSTANDING = 240_868_296  # weighted average basic shares, identical in all five years

# --------------------------------------------------------------------------------------
# RAW EXTRACTED DATA  (order: FY22, FY23, FY24, FY25, FY26)
# --------------------------------------------------------------------------------------
RAW: dict[str, list[float]] = {
    # ---------------- Statement of Profit & Loss ----------------
    "sale_of_goods":        [13944.67, 15984.90, 16546.21, 17535.02, 18858.21],
    "other_operating_rev":  [191.59,    315.65,   223.06,   407.65,   293.38],
    "revenue":              [14136.26, 16300.55, 16769.27, 17942.67, 19151.59],
    "other_income":         [222.83,    215.86,   214.18,   227.09,   224.03],
    "total_income":         [14359.09, 16516.41, 16983.45, 18169.76, 19375.62],
    "cost_materials":       [7473.97,  8326.70,  8546.89,  9859.45,  10350.02],
    "purchases_sit":        [1361.59,  1337.13,   941.48,   809.35,    805.23],
    "change_inventories":   [-75.26,   -72.53,     3.66,   -64.75,    -22.37],
    "employee_cost":        [542.26,    658.38,   708.70,   704.59,    823.80],
    "finance_costs":        [144.29,    169.10,   164.00,   138.80,    112.76],
    "depreciation":         [200.54,    225.91,   300.46,   313.34,    336.83],
    "other_expenses":       [2632.19,  3219.96,  3398.70,  3446.88,   3650.48],
    "total_expenses":       [12279.58, 13864.65, 14063.89, 15207.66, 16056.75],
    "share_assoc":          [-0.20,       5.41,    -3.19,   -10.74,    -30.09],
    "exceptional_expense":  [0.98,     -375.60,     2.90,    24.79,      0.00],
    "pbt":                  [2078.33,  3032.77,  2913.47,  2926.57,   3288.78],
    "current_tax":          [612.24,    720.97,   765.69,   741.68,    758.37],
    "deferred_tax":         [-49.89,     -4.52,    13.56,     7.03,     -6.60],
    "total_tax":            [562.35,    716.45,   779.25,   748.71,    751.77],
    "pat":                  [1515.98,  2316.32,  2134.22,  2177.86,   2537.01],
    "pat_owners":           [1524.82,  2321.77,  2139.81,  2178.73,   2533.49],
    "eps":                  [63.31,      96.39,    88.84,    90.45,    105.18],
    # ---------------- Balance sheet : non-current assets ----------------
    "ppe":                  [1584.05,  2472.19,  2602.94,  2734.61,  2672.98],
    "cwip":                 [535.68,    105.00,   187.54,    89.20,    39.04],
    "investment_property":  [13.95,      40.63,    27.48,    28.90,    27.90],
    "goodwill":             [139.61,    128.16,   129.82,   132.78,   143.95],
    "other_intangibles":    [15.60,      14.24,    10.90,     7.51,     5.09],
    "associates_jv":        [2.09,      495.16,   494.36,   483.62,   453.53],
    "nc_investments":       [926.55,   1028.09,   575.85,  1270.17,  1517.71],
    "nc_loans":             [100.00,    150.00,     0.00,    25.00,    25.00],
    "nc_other_fin_assets":  [31.80,      23.57,    25.50,    28.19,    30.99],
    "deferred_tax_assets":  [51.67,      57.25,    43.88,    36.59,    43.01],
    "tax_assets_nc":        [44.93,      43.64,    67.95,    46.26,    69.31],
    "other_nca":            [99.18,      48.56,    58.68,    42.04,    25.77],
    "total_nca":            [3545.11,  4606.49,  4224.90,  4924.87,  5054.28],
    # ---------------- Balance sheet : current assets ----------------
    "inventories":          [1367.49,  1193.26,  1181.22,  1236.51,  1345.93],
    "c_investments":        [833.73,   1800.99,  1696.51,  1111.64,  1638.52],
    "trade_receivables":    [331.93,    328.94,   393.33,   448.61,   469.21],
    "cash":                 [117.99,    102.38,   322.80,   132.78,   220.00],
    "bank_balances":        [66.91,      95.60,   123.55,   179.70,   132.44],
    "c_loans":              [698.00,    560.00,   460.00,    50.00,    65.00],
    "c_other_fin_assets":   [428.03,    451.96,   531.13,   630.46,   664.53],
    "other_ca":             [138.22,    180.74,   133.71,   123.98,   142.03],
    "assets_held_for_sale": [0.00,       32.36,     6.41,     0.00,     0.00],
    "total_ca":             [3982.30,  4746.23,  4848.66,  3913.68,  4677.66],
    "total_assets":         [7527.41,  9352.72,  9073.56,  8838.55,  9731.94],
    # ---------------- Balance sheet : equity ----------------
    "share_capital":        [24.09, 24.09, 24.09, 24.09, 24.09],
    "other_equity":         [2534.01,  3510.18,  3917.43,  4331.63,  5082.47],
    "equity_parent":        [2558.10,  3534.27,  3941.52,  4355.72,  5106.56],
    "nci":                  [27.50,      30.23,    24.50,    25.60,    29.32],
    "total_equity":         [2585.60,  3564.50,  3966.02,  4381.32,  5135.88],
    # ---------------- Balance sheet : non-current liabilities ----------------
    "nc_borrowings":        [706.99,   1551.80,   904.72,   712.94,   286.11],
    "nc_lease":             [13.76,      14.36,    20.13,    19.45,    19.31],
    "nc_other_fin_liab":    [52.64,      60.15,    65.66,    72.21,    72.95],
    "deferred_tax_liab":    [0.81,        1.87,     2.06,     1.80,     1.62],
    "nc_provisions":        [20.47,      25.64,    30.56,    32.57,    36.08],
    "total_ncl":            [794.67,   1653.82,  1023.13,   838.97,   416.07],
    # ---------------- Balance sheet : current liabilities ----------------
    "c_borrowings":         [1758.55,  1428.71,  1136.49,   511.83,  1071.72],
    "c_lease":              [1.90,        2.50,     3.62,     2.29,     3.14],
    "tp_msme":              [62.76,      43.92,    30.83,    27.83,    21.41],
    "tp_other":             [1260.05,  1404.89,  1596.65,  1724.40,  1875.00],
    "c_other_fin_liab":     [393.96,    496.21,   497.40,   429.34,   442.81],
    "other_cl":             [130.73,    176.34,   167.29,   194.70,    88.67],
    "c_provisions":         [464.64,    513.39,   559.20,   604.66,   594.52],
    "tax_liab":             [74.55,      68.44,    92.93,   123.21,    82.72],
    "total_cl":             [4147.14,  4134.40,  4084.41,  3618.26,  4179.99],
    "total_liabilities":    [4941.81,  5788.22,  5107.54,  4457.23,  4596.06],
    # ---------------- Statement of Cash Flows ----------------
    "cash_gen_ops":         [1886.43,  3251.96,  3337.85,  3179.83,  3433.34],
    "tax_paid":             [586.91,    725.75,   764.87,   689.21,   821.74],
    "cfo":                  [1299.52,  2526.21,  2572.98,  2490.62,  2611.60],
    "cfi":                  [910.89,  -1517.06,   484.15,    66.43,   -757.27],
    "cff":                  [-2245.84, -1028.37, -2839.13, -2753.90, -1782.62],
    "capex":                [550.18,    711.46,   552.87,   374.85,   205.57],
    "ppe_sale_proceeds":    [3.16,       78.43,    64.52,     4.58,     2.12],
    "interest_paid":        [118.61,    195.66,   164.28,   170.62,   107.18],
    "dividends_paid":       [2484.88,  1359.24,  1732.47,  1767.54,  1803.95],
    "dividends_declared":   [1794.47,  1360.91,  1734.25,  1770.38,  1806.51],
    "chg_inventories_cf":   [-274.76,   177.15,    12.60,   -54.33,  -105.05],
    "chg_receivables_cf":   [-72.21,      1.29,   -63.65,   -53.44,   -12.95],
    "net_change_cash":      [-35.43,    -19.22,   218.00,  -196.85,    71.71],
    "fx_effect_cash":       [3.30,       10.06,     1.29,     2.64,    15.89],
    "closing_cash_net_od":  [109.32,    100.16,   319.45,   125.24,   212.84],
}
OPENING_CASH_FY22 = 141.45   # cash & equivalents (net of overdraft) at 1-Apr-2021, FY22 cash-flow statement

# FY2020-21 base year (comparative column of the FY2021-22 report) - used for FY22 growth & averages only.
BASE_FY21: dict[str, float] = {
    "sale_of_goods": 12883.04, "other_operating_rev": 253.10, "revenue": 13136.14,
    "other_income": 312.87, "cost_materials": 6502.33, "purchases_sit": 1160.89,
    "change_inventories": -37.12, "employee_cost": 527.38, "finance_costs": 110.90,
    "depreciation": 197.85, "other_expenses": 2473.37, "share_assoc": 0.81,
    "exceptional_expense": 0.61, "pbt": 2513.61, "total_tax": 663.02, "pat": 1850.59,
    "pat_owners": 1863.90,
    "ppe": 1634.30, "cwip": 116.52, "total_assets": 8008.78, "total_ca": 4419.46,
    "inventories": 1091.49, "c_investments": 1393.25, "nc_investments": 1385.37,
    "trade_receivables": 257.27, "cash": 142.74, "bank_balances": 68.60,
    "total_equity": 3584.00, "equity_parent": 3547.66,
    "nc_borrowings": 747.15, "c_borrowings": 1357.15,
    "tp_msme": 26.40, "tp_other": 1286.79, "total_cl": 3608.90,
}

# --------------------------------------------------------------------------------------
# METADATA - labels / grouping used by dropdowns, tables and exports
# --------------------------------------------------------------------------------------
LABELS: dict[str, str] = {
    "sale_of_goods": "Sale of goods", "other_operating_rev": "Other operating revenues",
    "revenue": "Revenue from operations", "other_income": "Other income", "total_income": "Total income",
    "cost_materials": "Cost of materials consumed", "purchases_sit": "Purchases of stock-in-trade",
    "change_inventories": "Changes in inventories (FG, WIP, SIT)", "employee_cost": "Employee benefits expense",
    "finance_costs": "Finance costs", "depreciation": "Depreciation & amortisation",
    "other_expenses": "Other expenses", "total_expenses": "Total expenses",
    "share_assoc": "Share of profit/(loss) of associates & JV", "exceptional_expense": "Exceptional items expense/(income)",
    "pbt": "Profit before tax (PBT)", "current_tax": "Current tax", "deferred_tax": "Deferred tax",
    "total_tax": "Total tax expense", "pat": "Profit after tax (PAT)", "pat_owners": "PAT attributable to owners",
    "eps": "Earnings per share (₹)",
    "ppe": "Property, plant & equipment", "cwip": "Capital work-in-progress", "investment_property": "Investment property",
    "goodwill": "Goodwill", "other_intangibles": "Other intangible assets", "associates_jv": "Investment in associates & JV",
    "nc_investments": "Non-current investments", "nc_loans": "Non-current loans", "nc_other_fin_assets": "Other non-current financial assets",
    "deferred_tax_assets": "Deferred tax assets (net)", "tax_assets_nc": "Non-current tax assets (net)",
    "other_nca": "Other non-current assets", "total_nca": "Total non-current assets",
    "inventories": "Inventories", "c_investments": "Current investments", "trade_receivables": "Trade receivables",
    "cash": "Cash & cash equivalents", "bank_balances": "Other bank balances", "c_loans": "Current loans (inter-corporate deposits)",
    "c_other_fin_assets": "Other current financial assets", "other_ca": "Other current assets",
    "assets_held_for_sale": "Assets held for sale", "total_ca": "Total current assets", "total_assets": "Total assets",
    "share_capital": "Equity share capital", "other_equity": "Other equity", "equity_parent": "Equity attributable to owners",
    "nci": "Non-controlling interests", "total_equity": "Total equity",
    "nc_borrowings": "Non-current borrowings", "nc_lease": "Non-current lease liabilities",
    "nc_other_fin_liab": "Other non-current financial liabilities", "deferred_tax_liab": "Deferred tax liabilities (net)",
    "nc_provisions": "Non-current provisions", "total_ncl": "Total non-current liabilities",
    "c_borrowings": "Current borrowings", "c_lease": "Current lease liabilities", "tp_msme": "Trade payables - MSME",
    "tp_other": "Trade payables - others", "c_other_fin_liab": "Other current financial liabilities",
    "other_cl": "Other current liabilities", "c_provisions": "Current provisions", "tax_liab": "Current tax liabilities (net)",
    "total_cl": "Total current liabilities", "total_liabilities": "Total liabilities",
    "cash_gen_ops": "Cash generated from operations (pre-tax)", "tax_paid": "Income tax paid (net)",
    "cfo": "Net cash from operating activities", "cfi": "Net cash from / (used in) investing activities",
    "cff": "Net cash used in financing activities", "capex": "Capital expenditure (PPE, CWIP & intangibles)",
    "ppe_sale_proceeds": "Proceeds from sale of PPE", "interest_paid": "Interest paid",
    "dividends_paid": "Dividends paid (cash flow statement)", "dividends_declared": "Dividends recognised in equity",
    "chg_inventories_cf": "Working-capital change: inventories", "chg_receivables_cf": "Working-capital change: trade receivables",
    "net_change_cash": "Net change in cash & equivalents", "fx_effect_cash": "FX effect on cash",
    "closing_cash_net_od": "Closing cash (net of overdraft)",
    # derived
    "cogs": "Cost of goods sold (materials + purchases + inventory change)", "gross_profit": "Gross profit",
    "ebitda": "EBITDA (operating)", "ebit": "EBIT (operating)", "total_debt": "Total borrowings (debt)",
    "debt_incl_leases": "Borrowings incl. lease liabilities", "lease_liab": "Lease liabilities",
    "liquid_treasury": "Liquid treasury (cash + bank + current investments)",
    "total_treasury": "Total treasury (liquid + non-current investments + ICDs/loans)",
    "net_debt": "Net debt / (net cash)", "trade_payables": "Trade payables (total)",
    "nwc": "Net working capital (CA - CL)", "op_wc": "Operating working capital (Inv + Rec - Payables)",
    "capital_employed": "Capital employed (Total assets - CL)", "fcf": "Free cash flow (CFO - capex)",
    "net_fixed_assets": "Net fixed assets & goodwill", "investments_total": "Investments (incl. associates/JV)",
    "other_assets_bucket": "Loans, other financial & other assets", "other_liab_bucket": "Other liabilities",
    "fcf_after_div": "FCF after interest & dividends",
}

STATEMENT_GROUPS: dict[str, list[str]] = {
    "Income Statement": ["sale_of_goods", "other_operating_rev", "revenue", "other_income", "total_income",
                         "cost_materials", "purchases_sit", "change_inventories", "employee_cost", "finance_costs",
                         "depreciation", "other_expenses", "total_expenses", "share_assoc", "exceptional_expense",
                         "pbt", "current_tax", "deferred_tax", "total_tax", "pat", "pat_owners", "eps",
                         "cogs", "gross_profit", "ebitda", "ebit"],
    "Balance Sheet": ["ppe", "cwip", "investment_property", "goodwill", "other_intangibles", "associates_jv",
                      "nc_investments", "nc_loans", "nc_other_fin_assets", "deferred_tax_assets", "tax_assets_nc",
                      "other_nca", "total_nca", "inventories", "c_investments", "trade_receivables", "cash",
                      "bank_balances", "c_loans", "c_other_fin_assets", "other_ca", "assets_held_for_sale",
                      "total_ca", "total_assets", "share_capital", "other_equity", "equity_parent", "nci",
                      "total_equity", "nc_borrowings", "nc_lease", "nc_other_fin_liab", "deferred_tax_liab",
                      "nc_provisions", "total_ncl", "c_borrowings", "c_lease", "tp_msme", "tp_other",
                      "c_other_fin_liab", "other_cl", "c_provisions", "tax_liab", "total_cl", "total_liabilities",
                      "total_debt", "debt_incl_leases", "liquid_treasury", "net_debt", "nwc", "op_wc", "capital_employed"],
    "Cash Flow": ["cash_gen_ops", "tax_paid", "cfo", "cfi", "cff", "capex", "ppe_sale_proceeds", "fcf",
                  "interest_paid", "dividends_paid", "dividends_declared", "fcf_after_div",
                  "chg_inventories_cf", "chg_receivables_cf", "net_change_cash", "fx_effect_cash", "closing_cash_net_od"],
}

# Metrics offered in the dashboard's "metric explorer" dropdowns
EXPLORER_PL = ["revenue", "sale_of_goods", "gross_profit", "ebitda", "ebit", "pbt", "pat", "pat_owners", "eps",
               "cogs", "employee_cost", "other_expenses", "depreciation", "finance_costs", "other_income", "total_tax"]
EXPLORER_BS = ["total_assets", "total_equity", "total_liabilities", "total_debt", "net_debt", "total_ca", "total_cl",
               "nwc", "inventories", "trade_receivables", "trade_payables", "cash", "liquid_treasury", "ppe", "cwip",
               "nc_investments", "c_investments", "capital_employed", "op_wc"]
EXPLORER_CF = ["cfo", "cfi", "cff", "capex", "fcf", "interest_paid", "dividends_paid", "dividends_declared",
               "tax_paid", "fcf_after_div", "net_change_cash", "closing_cash_net_od"]

# --------------------------------------------------------------------------------------
# SOURCES & RESTATEMENTS
# --------------------------------------------------------------------------------------
SOURCES = pd.DataFrame([
    ["FY22", "Annual Report 2021-22", "Balance Sheet p.176 | P&L p.177 | Cash Flow pp.179-180",
     "Annual Report 2022-23 (comparative column), Balance Sheet p.114",
     "Balance sheet re-classified in AR 2022-23 - latest presentation used"],
    ["FY23", "Annual Report 2022-23", "Balance Sheet & P&L p.114 | Cash Flow pp.115-116",
     "Annual Report 2023-24 (comparative column), pp.117-119", "No differences in totals"],
    ["FY24", "Annual Report 2023-24", "Balance Sheet & P&L p.117 | Cash Flow pp.118-119",
     "Annual Report 2024-25 (comparative column), pp.132-134",
     "Cash-flow classification and two BS lines re-presented - latest used"],
    ["FY25", "Annual Report 2024-25", "Balance Sheet & P&L p.132 | Cash Flow pp.133-134",
     "Annual Report 2025-26 (comparative column), pp.132-134",
     "Cash-flow classification re-presented - latest used"],
    ["FY26", "Annual Report 2025-26", "Balance Sheet & P&L p.132 | Cash Flow pp.133-134", "n/a (latest year)", "As published"],
], columns=["Year", "Primary source", "Consolidated statements (PDF page no.)", "Cross-checked / restated in", "Treatment"])

RESTATEMENT_LOG = pd.DataFrame([
    ["FY22", "Balance Sheet", "Total assets", 7515.53, 7527.41, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Total current assets", 3970.42, 3982.30, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Other current assets", 126.34, 138.22, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Non-current provisions (shown separately)", 0.00, 20.47, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Total non-current liabilities", 774.20, 794.67, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Trade payables - others", 1222.46, 1260.05, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Other current financial liabilities", 423.69, 393.96, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Other current liabilities", 126.71, 130.73, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Current provisions", 485.11, 464.64, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Total current liabilities", 4155.73, 4147.14, "AR 2022-23"],
    ["FY22", "Balance Sheet", "Total liabilities", 4929.93, 4941.81, "AR 2022-23"],
    ["FY24", "Balance Sheet", "Investment in associates & JV", 491.96, 494.36, "AR 2024-25"],
    ["FY24", "Balance Sheet", "Non-current investments", 578.25, 575.85, "AR 2024-25"],
    ["FY24", "Cash Flow", "Net cash from investing activities", 475.50, 484.15, "AR 2024-25"],
    ["FY24", "Cash Flow", "Net cash used in financing activities", -2830.48, -2839.13, "AR 2024-25"],
    ["FY24", "Cash Flow", "Capital expenditure", 561.52, 552.87, "AR 2024-25"],
    ["FY25", "Cash Flow", "Cash generated from operations", 3169.86, 3179.83, "AR 2025-26"],
    ["FY25", "Cash Flow", "Net cash from operating activities", 2480.65, 2490.62, "AR 2025-26"],
    ["FY25", "Cash Flow", "Net cash from investing activities", 84.36, 66.43, "AR 2025-26"],
    ["FY25", "Cash Flow", "Net cash used in financing activities", -2761.86, -2753.90, "AR 2025-26"],
], columns=["Year", "Statement", "Line item", "As originally reported (₹ cr)",
            "Latest presentation - USED (₹ cr)", "Restated in"])
RESTATEMENT_LOG["Difference (₹ cr)"] = (
    RESTATEMENT_LOG["Latest presentation - USED (₹ cr)"] - RESTATEMENT_LOG["As originally reported (₹ cr)"]
).round(2)

DATA_NOTES = [
    "FY22 'Dividends paid' (₹2,484.88 cr) is reported by the company INCLUDING bonus debentures; the equity statement shows "
    "dividends of ₹1,794.47 cr and a separate issue of bonus debentures of ₹698.52 cr. Payout ratios therefore use "
    "'dividends recognised in equity'.",
    "FY23 PBT/PAT include an exceptional GAIN of ₹375.60 cr (gain on sale of investments, incl. ₹191.56 cr fair-value gain on the "
    "retained 51% stake - Note 36, AR 2022-23). 'PBT before exceptional items' is therefore the cleaner profit trend.",
    "FY22, FY24 and FY25 exceptional items are voluntary-retirement costs (₹0.98 cr, ₹2.90 cr, ₹24.79 cr); FY26 has none.",
    "Debt = current + non-current borrowings (lease liabilities shown separately). Net debt deducts cash, other bank balances and current investments.",
    "EBITDA / EBIT are OPERATING measures computed from the P&L (revenue from operations less operating costs; other income excluded). "
    "They are analyst-derived, not company-reported. A bridge from EBIT to reported PBT is verified for every year.",
]


# --------------------------------------------------------------------------------------
# DATAFRAME BUILDERS
# --------------------------------------------------------------------------------------
def _derive(d: pd.DataFrame) -> pd.DataFrame:
    """Add derived line items (NaN-safe so that it also works for the FY21 base row)."""
    d["cogs"] = d["cost_materials"] + d["purchases_sit"] + d["change_inventories"]
    d["gross_profit"] = d["revenue"] - d["cogs"]
    d["ebitda"] = d["revenue"] - (d["cogs"] + d["employee_cost"] + d["other_expenses"])
    d["ebit"] = d["ebitda"] - d["depreciation"]
    d["total_debt"] = d["nc_borrowings"] + d["c_borrowings"]
    d["lease_liab"] = d["nc_lease"] + d["c_lease"]
    d["debt_incl_leases"] = d["total_debt"] + d["lease_liab"]
    d["trade_payables"] = d["tp_msme"] + d["tp_other"]
    d["liquid_treasury"] = d["cash"] + d["bank_balances"] + d["c_investments"]
    d["total_treasury"] = d["liquid_treasury"] + d["nc_investments"] + d["c_loans"] + d["nc_loans"]
    d["net_debt"] = d["total_debt"] - d["liquid_treasury"]
    d["nwc"] = d["total_ca"] - d["total_cl"]
    d["op_wc"] = d["inventories"] + d["trade_receivables"] - d["trade_payables"]
    d["capital_employed"] = d["total_assets"] - d["total_cl"]
    d["fcf"] = d["cfo"] - d["capex"]
    d["fcf_after_div"] = d["fcf"] - d["interest_paid"] - d["dividends_paid"]
    # presentation buckets (sum exactly to total assets / total liabilities)
    d["net_fixed_assets"] = d["ppe"] + d["cwip"] + d["investment_property"] + d["goodwill"] + d["other_intangibles"]
    d["investments_total"] = d["nc_investments"] + d["c_investments"] + d["associates_jv"]
    d["other_assets_bucket"] = (d["total_assets"] - d["net_fixed_assets"] - d["investments_total"] - d["inventories"]
                                - d["trade_receivables"] - d["cash"] - d["bank_balances"])
    d["other_liab_bucket"] = d["total_liabilities"] - d["total_debt"] - d["lease_liab"] - d["trade_payables"]
    return d


def load_financials(include_base: bool = False) -> pd.DataFrame:
    """Five-year consolidated dataset (index FY22..FY26). include_base=True prepends the FY21 base row."""
    df = pd.DataFrame(RAW, index=FY).astype(float)
    if include_base:
        base = pd.DataFrame([BASE_FY21], index=["FY21"]).reindex(columns=df.columns).astype(float)
        df = pd.concat([base, df])
    df.index.name = "Financial year"
    return _derive(df)


def long_format(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy dataset: Statement | Metric | Key | FY | Financial year | Value (₹ crore, EPS in Rs)."""
    rows = []
    for stmt, cols in STATEMENT_GROUPS.items():
        for c in cols:
            for y in df.index:
                if y in FY:
                    rows.append([stmt, LABELS.get(c, c), c, y, FY_LONG[y], float(df.loc[y, c])])
    return pd.DataFrame(rows, columns=["Statement", "Metric", "Key", "FY", "Financial year", "Value (₹ crore)"])


# --------------------------------------------------------------------------------------
# VERIFICATION  (internal-consistency tests on the extracted data)
# --------------------------------------------------------------------------------------
def run_verification(tol: float = 0.06) -> pd.DataFrame:
    df = load_financials()
    out = []

    def add(name, y, computed, reported):
        diff = round(float(computed) - float(reported), 2)
        out.append([name, y, round(float(computed), 2), round(float(reported), 2), diff,
                    "PASS" if abs(diff) <= tol else "FAIL"])

    for y in FY:
        r = df.loc[y]
        add("Revenue = sale of goods + other operating revenue", y, r.sale_of_goods + r.other_operating_rev, r.revenue)
        add("Total income = revenue + other income", y, r.revenue + r.other_income, r.total_income)
        add("Total expenses = sum of expense lines", y,
            r.cost_materials + r.purchases_sit + r.change_inventories + r.employee_cost + r.finance_costs
            + r.depreciation + r.other_expenses, r.total_expenses)
        add("PBT = income - expenses + associates - exceptional", y,
            r.total_income - r.total_expenses + r.share_assoc - r.exceptional_expense, r.pbt)
        add("Operating EBIT + other income - finance + associates - exceptional = PBT", y,
            r.ebit + r.other_income - r.finance_costs + r.share_assoc - r.exceptional_expense, r.pbt)
        add("Total tax = current + deferred", y, r.current_tax + r.deferred_tax, r.total_tax)
        add("PAT = PBT - tax", y, r.pbt - r.total_tax, r.pat)
        add("EPS = PAT to owners / weighted shares", y, r.pat_owners * 1e7 / SHARES_OUTSTANDING, r.eps)
        add("Non-current assets: sum of lines = total", y,
            r.ppe + r.cwip + r.investment_property + r.goodwill + r.other_intangibles + r.associates_jv + r.nc_investments
            + r.nc_loans + r.nc_other_fin_assets + r.deferred_tax_assets + r.tax_assets_nc + r.other_nca, r.total_nca)
        add("Current assets: sum of lines = total", y,
            r.inventories + r.c_investments + r.trade_receivables + r.cash + r.bank_balances + r.c_loans
            + r.c_other_fin_assets + r.other_ca + r.assets_held_for_sale, r.total_ca)
        add("Total assets = NCA + CA", y, r.total_nca + r.total_ca, r.total_assets)
        add("Total equity = share capital + other equity + NCI", y, r.share_capital + r.other_equity + r.nci, r.total_equity)
        add("Non-current liabilities: sum of lines = total", y,
            r.nc_borrowings + r.nc_lease + r.nc_other_fin_liab + r.deferred_tax_liab + r.nc_provisions, r.total_ncl)
        add("Current liabilities: sum of lines = total", y,
            r.c_borrowings + r.c_lease + r.tp_msme + r.tp_other + r.c_other_fin_liab + r.other_cl + r.c_provisions + r.tax_liab,
            r.total_cl)
        add("Total liabilities = NCL + CL", y, r.total_ncl + r.total_cl, r.total_liabilities)
        add("Balance sheet balances: Assets = Equity + Liabilities", y, r.total_equity + r.total_liabilities, r.total_assets)
        add("CFO = cash generated from operations - tax paid", y, r.cash_gen_ops - r.tax_paid, r.cfo)
        add("CFO + CFI + CFF = net change in cash", y, r.cfo + r.cfi + r.cff, r.net_change_cash)
    prev = OPENING_CASH_FY22
    for y in FY:
        r = df.loc[y]
        add("Opening cash + net change + FX = closing cash (net of OD)", y,
            prev + r.net_change_cash + r.fx_effect_cash, r.closing_cash_net_od)
        prev = r.closing_cash_net_od
    for y in FY:
        r = df.loc[y]
        add("Asset presentation buckets sum to total assets", y,
            r.net_fixed_assets + r.investments_total + r.inventories + r.trade_receivables + r.cash + r.bank_balances
            + r.other_assets_bucket, r.total_assets)
    b = BASE_FY21
    add("FY21 base: PBT = income - expenses + assoc - exceptional", "FY21",
        b["revenue"] + b["other_income"] - (b["cost_materials"] + b["purchases_sit"] + b["change_inventories"]
        + b["employee_cost"] + b["finance_costs"] + b["depreciation"] + b["other_expenses"])
        + b["share_assoc"] - b["exceptional_expense"], b["pbt"])
    return pd.DataFrame(out, columns=["Check", "Year", "Computed", "Reported", "Difference", "Result"])


if __name__ == "__main__":
    v = run_verification()
    print(v["Result"].value_counts())
    print(v[v.Result == "FAIL"].to_string())
