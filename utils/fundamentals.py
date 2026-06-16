"""Fundamentals: valuation, growth, and capital-allocation metrics.

Pure-Python, deterministic (no LLM) — same philosophy as utils/ratios.py.
These fill the three biggest gaps vs a professional equity-research report:
  * Valuation   — P/E, P/S, P/B, EV/EBITDA, FCF yield, dividend yield
  * Growth      — absolute revenue / net income / EPS / FCF + YoY and CAGR
  * Capital allocation — buybacks, dividends, total returned, payout, share count

All figures are REPORTED HISTORICAL values pulled from the statements; nothing
here is a forecast. Valuation multiples use the latest fiscal-year fundamentals
against the current market capitalization (a trailing approximation).
"""
from __future__ import annotations
import pandas as pd


def _safe_div(a, b):
    try:
        if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _val(df: pd.DataFrame, candidates: list[str], col) -> float | None:
    """Single value by trying several yfinance row names."""
    if df is None or df.empty:
        return None
    for name in candidates:
        if name in df.index:
            try:
                v = df.loc[name, col]
                return None if pd.isna(v) else float(v)
            except (KeyError, ValueError):
                continue
    return None


def _series(df: pd.DataFrame, candidates: list[str]):
    """Return (years_oldest_first, values_oldest_first) for the first matching row."""
    if df is None or df.empty:
        return [], []
    for name in candidates:
        if name in df.index:
            cols = list(df.columns)
            years, vals = [], []
            for c in cols:
                try:
                    v = df.loc[name, c]
                except (KeyError, ValueError):
                    v = None
                vals.append(None if (v is None or pd.isna(v)) else float(v))
                years.append(str(c.year) if hasattr(c, "year") else str(c))
            # yfinance columns are newest-first; flip to oldest-first
            return list(reversed(years)), list(reversed(vals))
    return [], []


def _cagr(first, last, n_periods):
    if first is None or last is None or first <= 0 or last <= 0 or n_periods < 1:
        return None
    return (last / first) ** (1.0 / n_periods) - 1.0


def _yoy(years, vals):
    """List of {year, value, yoy} with year-over-year % change."""
    out = []
    for i, (y, v) in enumerate(zip(years, vals)):
        yoy = None
        if i > 0 and vals[i - 1] not in (None, 0) and v is not None:
            yoy = (v - vals[i - 1]) / abs(vals[i - 1])
        out.append({"year": y, "value": v, "yoy": yoy})
    return out


# --- yfinance row-name candidates -----------------------------------------
_REV = ["Total Revenue", "TotalRevenue", "Revenue", "Operating Revenue"]
_NI = ["Net Income", "NetIncome", "Net Income Common Stockholders",
       "Net Income Continuous Operations"]
_OPINC = ["Operating Income", "OperatingIncome", "Total Operating Income As Reported"]
_EBITDA = ["EBITDA", "Normalized EBITDA"]
_DNA = ["Depreciation And Amortization", "Depreciation Amortization Depletion",
        "Reconciled Depreciation", "Depreciation"]
_DEPS = ["Diluted EPS", "Basic EPS"]
_DSHARES = ["Diluted Average Shares", "Basic Average Shares"]
_OSHARES = ["Ordinary Shares Number", "Share Issued"]
_EQUITY = ["Stockholders Equity", "Total Equity Gross Minority Interest",
           "Total Stockholder Equity"]
_TOTDEBT = ["Total Debt"]
_LTD = ["Long Term Debt", "LongTermDebt"]
_STD = ["Current Debt", "Short Long Term Debt", "Other Current Borrowings"]
_CASH = ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash"]
_OCF = ["Operating Cash Flow", "Total Cash From Operating Activities", "Cash Flow From Continuing Operating Activities"]
_CAPEX = ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"]
_FCF = ["Free Cash Flow"]
_BUYBACK = ["Repurchase Of Capital Stock", "Repurchase Of Common Stock",
            "Common Stock Payments"]
_DIV = ["Cash Dividends Paid", "Common Stock Dividend Paid",
        "Common Stock Dividends Paid", "Cash Dividend Paid"]


def _total_debt(balance, col):
    td = _val(balance, _TOTDEBT, col)
    if td is not None:
        return td
    ltd = _val(balance, _LTD, col)
    std = _val(balance, _STD, col)
    if ltd is None and std is None:
        return None
    return (ltd or 0) + (std or 0)


def compute_valuation(raw: dict, market_cap: float | None) -> dict:
    """Latest-year valuation multiples against current market cap."""
    income = raw.get("income_stmt")
    balance = raw.get("balance_sheet")
    cash = raw.get("cash_flow")
    if income is None or income.empty or not market_cap:
        return {}

    icol = income.columns[0]
    bcol = balance.columns[0] if (balance is not None and not balance.empty) else icol
    ccol = cash.columns[0] if (cash is not None and not cash.empty) else icol

    revenue = _val(income, _REV, icol)
    net_income = _val(income, _NI, icol)
    op_income = _val(income, _OPINC, icol)
    equity = _val(balance, _EQUITY, bcol)
    debt = _total_debt(balance, bcol)
    cash_eq = _val(balance, _CASH, bcol)

    ebitda = _val(income, _EBITDA, icol)
    if ebitda is None and op_income is not None:
        dna = _val(cash, _DNA, ccol)
        ebitda = op_income + (dna or 0)

    ocf = _val(cash, _OCF, ccol)
    capex = _val(cash, _CAPEX, ccol)
    fcf = _val(cash, _FCF, ccol)
    if fcf is None and ocf is not None and capex is not None:
        fcf = ocf + capex  # capex is negative in yfinance

    dividends = _val(cash, _DIV, ccol)
    dividends = abs(dividends) if dividends is not None else None

    ev = None
    if debt is not None or cash_eq is not None:
        ev = market_cap + (debt or 0) - (cash_eq or 0)

    return {
        "market_cap": market_cap,
        "enterprise_value": ev,
        "pe": _safe_div(market_cap, net_income) if (net_income or 0) > 0 else None,
        "ps": _safe_div(market_cap, revenue),
        "pb": _safe_div(market_cap, equity) if (equity or 0) > 0 else None,
        "ev_ebitda": _safe_div(ev, ebitda) if (ebitda or 0) > 0 else None,
        "fcf_yield": _safe_div(fcf, market_cap),
        "earnings_yield": _safe_div(net_income, market_cap),
        "dividend_yield": _safe_div(dividends, market_cap),
    }


def compute_growth(raw: dict) -> dict:
    """Absolute figures + YoY + CAGR for revenue, net income, EPS, FCF."""
    income = raw.get("income_stmt")
    cash = raw.get("cash_flow")
    if income is None or income.empty:
        return {}

    metrics = {}

    def _pack(years, vals, label):
        clean = [(y, v) for y, v in zip(years, vals) if v is not None]
        if len(clean) < 2:
            return None
        ys = [c[0] for c in clean]
        vs = [c[1] for c in clean]
        return {
            "label": label,
            "series": _yoy(ys, vs),
            "first_year": ys[0], "first": vs[0],
            "last_year": ys[-1], "last": vs[-1],
            "cagr": _cagr(vs[0], vs[-1], len(vs) - 1),
        }

    ry, rv = _series(income, _REV)
    metrics["revenue"] = _pack(ry, rv, "Revenue")

    ny, nv = _series(income, _NI)
    metrics["net_income"] = _pack(ny, nv, "Net Income")

    # EPS: prefer the reported diluted EPS row; else net income / diluted shares
    ey, ev = _series(income, _DEPS)
    if not ev or all(v is None for v in ev):
        sy, sv = _series(income, _DSHARES)
        if sv and ny:
            ev = [(_safe_div(n, s) if (n is not None and s) else None)
                  for n, s in zip(nv, sv)]
            ey = ny
    metrics["eps"] = _pack(ey, ev, "Diluted EPS")

    # FCF
    fy, fv = _series(cash, _FCF)
    if not fv or all(v is None for v in fv):
        oy, ov = _series(cash, _OCF)
        cy, cv = _series(cash, _CAPEX)
        if ov and cv and len(ov) == len(cv):
            fv = [(o + c if (o is not None and c is not None) else None)
                  for o, c in zip(ov, cv)]
            fy = oy
    metrics["fcf"] = _pack(fy, fv, "Free Cash Flow")

    return metrics


def compute_capital_allocation(raw: dict, market_cap: float | None) -> dict:
    """Buybacks, dividends, total returned, payout ratio, share-count change."""
    income = raw.get("income_stmt")
    cash = raw.get("cash_flow")
    balance = raw.get("balance_sheet")
    if cash is None or cash.empty:
        return {}

    ccol = cash.columns[0]
    icol = income.columns[0] if (income is not None and not income.empty) else ccol

    buyback = _val(cash, _BUYBACK, ccol)
    buyback = abs(buyback) if buyback is not None else None
    dividend = _val(cash, _DIV, ccol)
    dividend = abs(dividend) if dividend is not None else None
    net_income = _val(income, _NI, icol)

    total_returned = None
    if buyback is not None or dividend is not None:
        total_returned = (buyback or 0) + (dividend or 0)

    # Share-count trend (diluted avg shares, oldest -> newest)
    sy, sv = _series(income, _DSHARES)
    if not sv or all(v is None for v in sv):
        sy, sv = _series(balance, _OSHARES)
    share_first = share_last = share_change = None
    clean_shares = [(y, v) for y, v in zip(sy, sv) if v]
    if len(clean_shares) >= 2:
        share_first = clean_shares[0][1]
        share_last = clean_shares[-1][1]
        share_change = _safe_div(share_last - share_first, share_first)

    return {
        "buybacks": buyback,
        "dividends": dividend,
        "total_returned": total_returned,
        "payout_ratio": _safe_div(dividend, net_income) if (net_income or 0) > 0 else None,
        "total_payout_ratio": _safe_div(total_returned, net_income) if (net_income or 0) > 0 else None,
        "buyback_yield": _safe_div(buyback, market_cap),
        "dividend_yield": _safe_div(dividend, market_cap),
        "shareholder_yield": _safe_div(total_returned, market_cap),
        "shares_first": share_first,
        "shares_last": share_last,
        "share_count_change": share_change,
    }


# Labels for the valuation peer-comparison table (higher-is-better flags)
VALUATION_METRICS = {
    "pe": ("P / E", False),
    "ps": ("P / S", False),
    "pb": ("P / B", False),
    "ev_ebitda": ("EV / EBITDA", False),
    "fcf_yield": ("FCF Yield", True),
    "dividend_yield": ("Dividend Yield", True),
}
