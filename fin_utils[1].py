"""Small formatting / maths helpers shared by the analytics layer and the Streamlit app."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def is_nan(x) -> bool:
    try:
        return x is None or (isinstance(x, float) and math.isnan(x)) or bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def cr(x: float, dec: int = 0) -> str:
    """Rs-crore formatting with Indian-style units, e.g. 19,152 -> '₹19,152 cr'."""
    if is_nan(x):
        return "n/a"
    sign = "-" if x < 0 else ""
    return f"{sign}₹{abs(x):,.{dec}f} cr"


def pct(x: float, dec: int = 1, signed: bool = False) -> str:
    if is_nan(x):
        return "n/a"
    return f"{x:+,.{dec}f}%" if signed else f"{x:,.{dec}f}%"


def mult(x: float, dec: int = 2) -> str:
    return "n/a" if is_nan(x) else f"{x:,.{dec}f}x"


def bps(delta_pct_points: float) -> str:
    return "n/a" if is_nan(delta_pct_points) else f"{delta_pct_points * 100:+,.0f} bps"


def cagr(first: float, last: float, periods: int) -> float:
    """Compound annual growth in %. Returns NaN when undefined (non-positive endpoints / zero periods)."""
    if periods <= 0 or is_nan(first) or is_nan(last) or first <= 0 or last <= 0:
        return float("nan")
    return ((last / first) ** (1.0 / periods) - 1.0) * 100.0


def growth(new: float, old: float) -> float:
    if is_nan(new) or is_nan(old) or old == 0:
        return float("nan")
    return (new / abs(old) - old / abs(old)) * 100.0 if old < 0 else (new / old - 1.0) * 100.0


def arrow(delta: float, eps: float = 1e-9) -> str:
    if is_nan(delta) or abs(delta) <= eps:
        return "▬"
    return "▲" if delta > 0 else "▼"
