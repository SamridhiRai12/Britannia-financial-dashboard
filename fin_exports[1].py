"""Excel (OpenPyXL) and CSV exports. All numbers are ₹ crore unless the row says otherwise."""
from __future__ import annotations

import io
from datetime import date

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from fin_data import (DATA_NOTES, FY_LONG, LABELS, RESTATEMENT_LOG, SOURCES, STATEMENT_GROUPS, run_verification)
from fin_ratios import CATEGORIES, RATIO_META, fmt_value, health_scores, interpret

NAVY, GOLD, LIGHT, GREY = "0B1F3F", "C8A44D", "EEF2F8", "F5F7FA"
HDR_FILL = PatternFill("solid", fgColor=NAVY)
GOLD_FILL = PatternFill("solid", fgColor=GOLD)
LIGHT_FILL = PatternFill("solid", fgColor=LIGHT)
HDR_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
TITLE_FONT = Font(bold=True, color=NAVY, name="Calibri", size=16)
BOLD = Font(bold=True, name="Calibri")
THIN = Side(style="thin", color="D5DBE6")
BORDER = Border(bottom=THIN)
STATUS_FILL = {"Risk": "F4B8B0", "Watch": "FBE7B5", "Healthy": "CFE8DA"}

TOTAL_KEYS = {"revenue", "total_income", "total_expenses", "pbt", "pat", "ebitda", "ebit", "gross_profit", "total_nca", "total_ca",
              "total_assets", "total_equity", "total_ncl", "total_cl", "total_liabilities", "cfo", "cfi", "cff", "fcf", "net_change_cash"}


def _title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = TITLE_FONT
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="5B6B82")
    ws.sheet_view.showGridLines = False


def _header(ws, row, values, start_col=1):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=start_col + i, value=v)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(horizontal="center" if i else "left", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 22


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _statement_sheet(wb, name, df, years, keys):
    ws = wb.create_sheet(name)
    _title(ws, f"Britannia Industries Ltd - {name} (Consolidated)", "₹ crore unless stated | Source: Annual Reports FY2021-22 to FY2025-26")
    _header(ws, 4, ["Line item"] + [FY_LONG[y] for y in years])
    r = 5
    for k in keys:
        ws.cell(row=r, column=1, value=LABELS.get(k, k))
        for j, y in enumerate(years, start=2):
            v = df.loc[y, k]
            c = ws.cell(row=r, column=j, value=None if pd.isna(v) else round(float(v), 2))
            c.number_format = '#,##0.00;[Red](#,##0.00)'
            c.border = BORDER
        if k in TOTAL_KEYS:
            for j in range(1, len(years) + 2):
                ws.cell(row=r, column=j).font = BOLD
                ws.cell(row=r, column=j).fill = LIGHT_FILL
        r += 1
    ws.freeze_panes = "B5"
    _widths(ws, [52] + [16] * len(years))
    return ws


def build_excel(df: pd.DataFrame, ratios: pd.DataFrame, flags_detail: pd.DataFrame, years: list[str]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cover"
    _title(ws, "Britannia Industries Limited - Financial Intelligence Report", f"Generated {date.today():%d %b %Y} | Consolidated | ₹ crore")
    rows = [
        ("Period covered", f"{FY_LONG[years[0]]} to {FY_LONG[years[-1]]}"),
        ("Source", "Britannia Industries Ltd Annual Reports 2021-22, 2022-23, 2023-24, 2024-25, 2025-26 (consolidated statements)"),
        ("Basis", "Latest presentation of each year (comparative columns of the following report); originals logged in 'Restatements'"),
        ("Derived measures", "EBITDA/EBIT are operating, analyst-derived. Debt excludes lease liabilities. See 'Ratios' for formulas."),
        ("Sheets", "Income Statement | Balance Sheet | Cash Flow | Ratios | Health Score | Red Flags | Verification | Restatements | Sources"),
    ]
    for i, (a, b) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=a).font = BOLD
        ws.cell(row=i, column=2, value=b).alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(row=10, column=1, value="Data notes").font = BOLD
    for i, n in enumerate(DATA_NOTES, start=11):
        ws.cell(row=i, column=1, value=f"{i - 10}.")
        ws.cell(row=i, column=2, value=n).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 48
    _widths(ws, [24, 120])

    for sheet, keys in STATEMENT_GROUPS.items():
        _statement_sheet(wb, sheet, df, years, keys)

    # Ratios with formula + interpretation
    ws = wb.create_sheet("Ratios")
    _title(ws, "Financial ratio analysis", "Formulae use average balances where stated. Interpretation reflects the selected period.")
    _header(ws, 4, ["Category", "Ratio", "Unit", "Formula"] + [FY_LONG[y] for y in years] + ["Interpretation"])
    r = 5
    for cat in CATEGORIES:
        for k, m in RATIO_META.items():
            if m["cat"] != cat:
                continue
            ws.cell(row=r, column=1, value=cat)
            ws.cell(row=r, column=2, value=m["name"]).font = BOLD
            ws.cell(row=r, column=3, value=m["unit"])
            ws.cell(row=r, column=4, value=m["formula"]).alignment = Alignment(wrap_text=True, vertical="top")
            for j, y in enumerate(years, start=5):
                v = ratios.loc[y, k]
                c = ws.cell(row=r, column=j, value=None if pd.isna(v) else round(float(v), 4))
                c.number_format = "#,##0.00"
            ws.cell(row=r, column=5 + len(years), value=interpret(k, ratios, years)).alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[r].height = 62
            r += 1
    ws.freeze_panes = "E5"
    _widths(ws, [14, 36, 8, 52] + [12] * len(years) + [90])

    ws = wb.create_sheet("Health Score")
    _title(ws, "Rule-based financial health scorecard (0-100)", "Illustrative analytical screen - not a credit rating. Rules documented in the dashboard methodology.")
    hs = health_scores(ratios).loc[years]
    _header(ws, 4, ["Pillar"] + [FY_LONG[y] for y in years])
    for i, col in enumerate(hs.columns, start=5):
        ws.cell(row=i, column=1, value=col).font = BOLD if col == "Overall" else Font()
        for j, y in enumerate(years, start=2):
            ws.cell(row=i, column=j, value=round(float(hs.loc[y, col]), 1)).number_format = "0.0"
    _widths(ws, [20] + [16] * len(years))

    ws = wb.create_sheet("Red Flags")
    _title(ws, "Red-flag analysis", "Status: Risk / Watch / Healthy. Rules shown per test.")
    fd = flags_detail[flags_detail["Year"].isin(years)].sort_values(["Year", "Severity", "Category"], ascending=[True, False, True])
    _header(ws, 4, ["Year", "Category", "Test", "Status", "Metric", "Rule", "Assessment"])
    for i, row in enumerate(fd.itertuples(index=False), start=5):
        vals = [row.Year, row.Category, row.Test, row.Status, row.Metric, row.Rule, row.Assessment]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=i, column=j, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=i, column=4).fill = PatternFill("solid", fgColor=STATUS_FILL[row.Status])
    ws.freeze_panes = "A5"
    _widths(ws, [8, 20, 40, 10, 30, 42, 100])

    v = run_verification()
    ws = wb.create_sheet("Verification")
    _title(ws, f"Data integrity checks - {int((v.Result == 'PASS').sum())} of {len(v)} passed", "Every subtotal, balance-sheet identity, cash-flow reconciliation and EPS re-computed from line items")
    _header(ws, 4, list(v.columns))
    for i, row in enumerate(v.itertuples(index=False), start=5):
        for j, val in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=val)
        ws.cell(row=i, column=6).fill = PatternFill("solid", fgColor="CFE8DA" if row.Result == "PASS" else "F4B8B0")
    _widths(ws, [70, 8, 14, 14, 12, 10])

    for name, frame, title in [("Restatements", RESTATEMENT_LOG, "Differences between original and latest presentation (latest used)"),
                               ("Sources", SOURCES, "Source documents and PDF page references")]:
        ws = wb.create_sheet(name)
        _title(ws, title)
        _header(ws, 4, list(frame.columns))
        for i, row in enumerate(frame.itertuples(index=False), start=5):
            for j, val in enumerate(row, start=1):
                ws.cell(row=i, column=j, value=val).alignment = Alignment(wrap_text=True, vertical="top")
        _widths(ws, [10, 16, 40, 22, 22, 16, 16] if name == "Restatements" else [8, 24, 52, 52, 56])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def statements_csv(df: pd.DataFrame, years: list[str]) -> bytes:
    rows = []
    for stmt, keys in STATEMENT_GROUPS.items():
        for k in keys:
            rows.append([stmt, LABELS.get(k, k)] + [round(float(df.loc[y, k]), 2) for y in years])
    out = pd.DataFrame(rows, columns=["Statement", "Line item (₹ crore)"] + [FY_LONG[y] for y in years])
    return out.to_csv(index=False).encode("utf-8-sig")


def ratios_csv(ratios: pd.DataFrame, years: list[str]) -> bytes:
    rows = []
    for k, m in RATIO_META.items():
        rows.append([m["cat"], m["name"], m["unit"], m["formula"]] + [round(float(ratios.loc[y, k]), 4) for y in years])
    out = pd.DataFrame(rows, columns=["Category", "Ratio", "Unit", "Formula"] + [FY_LONG[y] for y in years])
    return out.to_csv(index=False).encode("utf-8-sig")


def flags_csv(flags_detail: pd.DataFrame, years: list[str]) -> bytes:
    return flags_detail[flags_detail["Year"].isin(years)].drop(columns=["Severity"]).to_csv(index=False).encode("utf-8-sig")
